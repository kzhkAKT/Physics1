#!/usr/bin/env python3
"""Add referrerpolicy="strict-origin-when-cross-origin" to every YouTube
<iframe> that lacks it, editing .ipynb (or .html / .md) files in place.

Why: since 2025 YouTube's embedded player requires an HTTP Referer and
shows "Error 153" without one. Colab renders cell output in a sandboxed
frame that sends no Referer unless the <iframe> itself sets referrerpolicy.

Usage:
    python3 add_referrerpolicy.py .                  # all *.ipynb under the current dir (recursive)
    python3 add_referrerpolicy.py notebooks/ a.ipynb # directories and/or files
    python3 add_referrerpolicy.py -n .               # dry run: report only, write nothing

Behaviour:
  * Only <iframe> tags whose src is youtube.com/embed/... or
    youtube-nocookie.com/embed/... are touched; src itself is never changed.
  * Tags that already have a referrerpolicy attribute are left as they are.
  * The attribute is inserted right before `allowfullscreen` (official
    embed-code order), or at the end of the tag if there is none.
  * A stray quote right after </iframe> is removed.
  * The file text is patched directly; the notebook JSON is NOT
    re-serialized, so formatting is preserved and git diffs stay minimal.
  * For .ipynb/.json the patched text is checked to still be valid JSON
    before it is written. Directories named .git and .ipynb_checkpoints
    are skipped.
Exit status is 0 on success, 1 if any file could not be processed.
"""
import json
import re
import sys
from pathlib import Path

POLICY = "strict-origin-when-cross-origin"
SKIP_DIRS = {".git", ".ipynb_checkpoints", "node_modules"}

# One <iframe ...> start tag whose src is a YouTube embed URL.
# Inside .ipynb JSON the quotes appear as \" and "/" may appear as "\/",
# so the pattern tolerates both forms.
IFRAME = re.compile(
    r'<iframe\b[^>]*?youtube(?:-nocookie)?\.com\\?/embed\\?/[^>]*?>',
    re.IGNORECASE,
)
HAS_POLICY = re.compile(r'\breferrerpolicy\s*=', re.IGNORECASE)
ALLOWFULLSCREEN = re.compile(r'(\s)(allowfullscreen\b)', re.IGNORECASE)

# </iframe>\" followed by the end of the JSON string (optionally after \n)
STRAY_QUOTE_JSON = re.compile(r'</iframe>\\"(?=(?:\\n)?")')
# </iframe>" at the end of a line in a plain HTML / Markdown file
STRAY_QUOTE_TEXT = re.compile(r'</iframe>"(?=[ \t]*$)', re.MULTILINE)


def add_policy(m: "re.Match[str]") -> str:
    tag = m.group(0)
    if HAS_POLICY.search(tag):
        return tag  # already present: leave untouched
    q = '\\"' if '\\"' in tag else '"'  # JSON-escaped or plain HTML
    attr = f'referrerpolicy={q}{POLICY}{q}'
    if ALLOWFULLSCREEN.search(tag):
        return ALLOWFULLSCREEN.sub(lambda mm: f'{mm.group(1)}{attr} {mm.group(2)}', tag, count=1)
    return tag[:-1].rstrip() + ' ' + attr + '>'


def patch(text: str, is_json: bool) -> str:
    text = IFRAME.sub(add_policy, text)
    if is_json:
        text = STRAY_QUOTE_JSON.sub('</iframe>', text)
    else:
        text = STRAY_QUOTE_TEXT.sub('</iframe>', text)
    return text


def collect(args):
    """Expand directories into their *.ipynb files; keep files as given."""
    for a in args:
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob('*.ipynb')):
                if not (SKIP_DIRS & set(f.parts)):
                    yield f
        elif p.is_file():
            yield p
        else:
            print(f'{p}: not found, skipped', file=sys.stderr)


def main(argv):
    dry_run = '-n' in argv or '--dry-run' in argv
    targets = [a for a in argv if a not in ('-n', '--dry-run')]
    if not targets:
        print(__doc__)
        return 1

    updated = unchanged = failed = 0
    for p in collect(targets):
        is_json = p.suffix.lower() in ('.ipynb', '.json')
        original = p.read_text(encoding='utf-8')
        patched = patch(original, is_json)
        if patched == original:
            unchanged += 1
            continue
        if is_json:
            try:
                json.loads(patched)
            except json.JSONDecodeError as e:
                print(f'{p}: SKIPPED, result would not be valid JSON ({e})', file=sys.stderr)
                failed += 1
                continue
        n = len(IFRAME.findall(original))
        if dry_run:
            print(f'{p}: would update ({n} YouTube iframe(s))')
        else:
            with open(p, 'w', encoding='utf-8', newline='') as f:
                f.write(patched)
            print(f'{p}: updated ({n} YouTube iframe(s))')
        updated += 1

    verb = 'would be updated' if dry_run else 'updated'
    print(f'Summary: {updated} file(s) {verb}, {unchanged} unchanged, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

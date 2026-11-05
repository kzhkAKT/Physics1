#!/usr/bin/env python3
"""Convert Colab code cells that embed an <iframe> through the %%html magic
into cells that use IPython.display.IFrame, keeping #@title / #@markdown /
#@param lines (and ordinary # comments) in place.

A cell like

    #@title 実験: 慣性の法則
    #@markdown note
    %%html
    <iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/ID?si=xxx"
            title="YouTube video player" frameborder="0" allow="..." allowfullscreen></iframe>

becomes

    #@title 実験: 慣性の法則
    #@markdown note
    from IPython.display import IFrame
    IFrame("https://www.youtube-nocookie.com/embed/ID", 560, 315,
           extras=['allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"',
                   'referrerpolicy="strict-origin-when-cross-origin"'])

Usage:
    python3 html2iframe.py .            # all *.ipynb under the current dir (recursive)
    python3 html2iframe.py -n .         # dry run: report only, write nothing
    python3 html2iframe.py --keep-si .  # keep YouTube's ?si=... share-tracking parameter

Rules:
  * Only code cells containing a %%html line are considered. Lines starting
    with "#" (#@title, #@markdown, #@param, comments) are kept, in their
    original order, with #@title moved to the first line as Colab expects;
    %%html itself is removed; the remaining HTML must consist of <iframe>
    elements only. Cells with other HTML (<img>, <video>, text, ...) are
    left unchanged and reported.
  * YouTube iframes (youtube.com / youtube-nocookie.com) get the fixed
    extras shown above, which is what the YouTube embedded player needs
    (referrerpolicy avoids "Error 153"). The host and any query parameters
    other than si (e.g. start=28) are kept. HTML entities such as &amp;
    in the URL are decoded.
  * Other iframes (e.g. PhET simulations) keep their own attributes as
    extras, except src/width/height/frameborder/allowfullscreen, which the
    IFrame template already provides.
  * Width and height come from the tag (integers when numeric). YouTube
    iframes without them default to 560 x 315; other iframes are skipped.
  * A cell with several iframes becomes one display(IFrame(...)) per iframe.
  * The notebook JSON is re-serialized with the original file's indentation,
    so a Colab- or Jupyter-saved notebook keeps its formatting (a note is
    printed if it would not). Cell metadata (e.g. cellView: "form") is
    untouched. Directories named .git and .ipynb_checkpoints are skipped.
Exit status is 0 on success, 1 if any file could not be processed.
"""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

YOUTUBE_EXTRAS = [
    'allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"',
    'referrerpolicy="strict-origin-when-cross-origin"',
]
YOUTUBE_HOSTS = ('youtube.com', 'youtube-nocookie.com')
TEMPLATE_ATTRS = {'src', 'width', 'height', 'frameborder', 'allowfullscreen'}
SKIP_DIRS = {'.git', '.ipynb_checkpoints', 'node_modules'}

IFRAME = re.compile(r'<iframe\b(?P<attrs>[^>]*)>\s*</iframe\s*>', re.IGNORECASE)
ATTR = re.compile(r'''([A-Za-z_][\w-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?''')
HTML_MAGIC = re.compile(r'^\s*%%html\b')


def parse_attrs(text):
    """Return an ordered dict of attribute -> value (None for boolean attributes). First wins."""
    attrs = {}
    for m in ATTR.finditer(text):
        name = m.group(1).lower()
        value = next((g for g in m.groups()[1:] if g is not None), None)
        attrs.setdefault(name, value)
    return attrs


def is_youtube(url):
    host = (urlsplit(url).hostname or '').lower()
    return any(host == h or host.endswith('.' + h) for h in YOUTUBE_HOSTS)


def strip_si(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'si']
    return urlunsplit(parts._replace(query=urlencode(query)))


def size(value):
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isdigit() else value


def py_str(s):
    """A double-quoted Python literal for a URL or attribute string."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def iframe_call(attrs, keep_si):
    """Build the IFrame(...) call text (without indentation) for one parsed tag, or raise ValueError."""
    if 'src' not in attrs or attrs['src'] is None:
        raise ValueError('iframe without src')
    url = html.unescape(attrs['src']).strip()
    youtube = is_youtube(url)
    if youtube and not keep_si:
        url = strip_si(url)
    width, height = size(attrs.get('width')), size(attrs.get('height'))
    if width is None or height is None:
        if youtube:
            width, height = width or 560, height or 315
        else:
            raise ValueError('iframe without width/height')
    if youtube:
        extras = list(YOUTUBE_EXTRAS)
    else:
        extras = []
        for name, value in attrs.items():
            if name in TEMPLATE_ATTRS:
                continue
            extras.append(name if value is None else f'{name}="{html.unescape(value)}"')
    w = width if isinstance(width, int) else py_str(width)
    h = height if isinstance(height, int) else py_str(height)
    head = f'IFrame({py_str(url)}, {w}, {h}'
    if not extras:
        return head + ')', youtube
    pad = ' ' * len('IFrame(')
    items = ',\n'.join((pad + ' ' * len('extras=[') if i else '') + repr(e) for i, e in enumerate(extras))
    return f'{head},\n{pad}extras=[{items}])', youtube


def convert_cell(src, keep_si):
    """Return (new_source_text, info) for a %%html iframe cell, or (None, reason)."""
    lines = src.split('\n')
    if not any(HTML_MAGIC.match(l) for l in lines):
        return None, None  # not a %%html cell: not our business
    comments, body = [], []
    for line in lines:
        if HTML_MAGIC.match(line):
            continue
        if line.lstrip().startswith('#'):
            comments.append(line.strip())
        else:
            body.append(line)
    html_text = '\n'.join(body)
    tags = list(IFRAME.finditer(html_text))
    if not tags:
        return None, 'no <iframe> (left as %%html)'
    rest = IFRAME.sub('', html_text).replace('"', '').strip()
    if rest:
        return None, f'other HTML besides <iframe> (left as %%html): {rest[:40]!r}'
    calls, hosts = [], []
    for t in tags:
        attrs = parse_attrs(t.group('attrs'))
        try:
            call, youtube = iframe_call(attrs, keep_si)
        except ValueError as e:
            return None, f'{e} (left as %%html)'
        calls.append(call)
        hosts.append('youtube' if youtube else (urlsplit(html.unescape(attrs['src'])).hostname or '?'))
    # #@title first, then the other #-lines in their original order
    titles = [c for c in comments if c.startswith('#@title')]
    others = [c for c in comments if not c.startswith('#@title')]
    out = titles + others
    if len(calls) == 1:
        out += ['from IPython.display import IFrame', calls[0]]
    else:
        out.append('from IPython.display import IFrame, display')
        pad = ' ' * len('display(')
        for call in calls:
            out.append('display(' + call.replace('\n', '\n' + pad) + ')')
    new = '\n'.join(out)
    if src.endswith('\n'):
        new += '\n'
    return new, f'{len(calls)} iframe(s): ' + ', '.join(hosts)


def dumps_like(obj, original):
    """Serialize obj as JSON using the indentation and trailing newline of the original text."""
    m = re.search(r'\n( +)"', original)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(obj, ensure_ascii=False, indent=indent)
    return out + ('\n' if original.endswith('\n') else '')


def process(path, keep_si, dry_run):
    """Convert one notebook. Returns (n_converted, n_skipped) or None on failure."""
    text = path.read_text(encoding='utf-8')
    nb = json.loads(text)
    converted = skipped = 0
    for i, cell in enumerate(nb.get('cells', [])):
        if cell.get('cell_type') != 'code':
            continue
        source = cell.get('source', '')
        src = ''.join(source) if isinstance(source, list) else source
        new, info = convert_cell(src, keep_si)
        if new is None:
            if info:
                skipped += 1
                print(f'{path} cell {i}: SKIP {info}')
            continue
        cell['source'] = new.splitlines(keepends=True) if isinstance(source, list) else new
        converted += 1
        title = next((l for l in src.split('\n') if l.lstrip().startswith('#@title')), '').strip()
        print(f'{path} cell {i}: {info}   {title[:60]}')
    if converted:
        if dumps_like(json.loads(text), text) != text:
            print(f'{path}: note: JSON formatting will be normalized', file=sys.stderr)
        out = dumps_like(nb, text)
        json.loads(out)  # must still be valid JSON
        if not dry_run:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(out)
    return converted, skipped


def collect(args):
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
    keep_si = '--keep-si' in argv
    targets = [a for a in argv if a not in ('-n', '--dry-run', '--keep-si')]
    if not targets:
        print(__doc__)
        return 1
    files = cells = skipped = failed = 0
    for p in collect(targets):
        try:
            c, s = process(p, keep_si, dry_run)
        except Exception as e:  # unreadable / invalid notebook
            print(f'{p}: FAILED ({e})', file=sys.stderr)
            failed += 1
            continue
        files += bool(c)
        cells += c
        skipped += s
    verb = 'would be converted' if dry_run else 'converted'
    print(f'Summary: {cells} cell(s) in {files} file(s) {verb}, {skipped} %%html cell(s) left unchanged, {failed} file(s) failed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

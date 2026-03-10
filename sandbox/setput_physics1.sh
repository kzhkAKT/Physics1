#!/bin/bash

# --- 設定：ここを変更してください ---
#ROOT_DIR="physics1" # ここを "" にすると、実行した場所に直接 01-lectures 等が作られます
ROOT_DIR= # ここを "" にすると、実行した場所に直接 01-lectures 等が作られます
DIR_LEC="01-lectures"
DIR_EXP="02-experiments"
DIR_EXE="03-exercises"

# プレフィックスの自動構築（ROOT_DIRが空なら空、あれば末尾に/を付与）
P="${ROOT_DIR:+$ROOT_DIR/}"

# セクション名（ディレクトリ名）
S01="s01-01-motion"
S02="s01-02-laws"
S03="s01-03-various-motions"
S04="s01-04-momentum"
S05="s01-05-energy"
S06="s01-06-2d-3d-motion"
S07="s01-07-rigid-body-fluid"

# --- 実行処理：ディレクトリ作成 ---
mkdir -p "${P}${DIR_LEC}" "${P}${DIR_EXP}" "${P}${DIR_EXE}"

# --- 関数：ファイル作成 ---
create_lec() {
    local sect_dir=$1
    shift
    local target_dir="${P}${DIR_LEC}/${sect_dir}"
    mkdir -p "$target_dir"
    for file in "$@"; do
        # 最小限のipynb構造を書き込み
        echo '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}' > "${target_dir}/${file}.ipynb"
    done
}

# --- データ流し込み ---
create_lec "$S01" 010101_speed 010102_velocity_displacement 010103_average_velocity 010104_instantaneous_velocity 010105_acceleration 010106_uniform_linear_motion 010107_uniform_accel_motion
create_lec "$S02" 010201_force 010202_mass 010203_law_of_inertia 010204_equation_of_motion 010205_action_reaction 010206_gravity_universal_grav 010207_elastic_force 010208_normal_friction_force
create_lec "$S03" 010301_two_body_systems 010302_free_fall 010303_vertical_projection 010304_motion_with_friction
create_lec "$S04" 010401_impulse 010402_momentum 010403_impulse_momentum_change 010404_conservation_of_momentum 010405_restitution_coefficient
create_lec "$S05" 010501_work 010502_work_and_energy 010503_kinetic_energy 010504_potential_energy 010505_conservation_of_energy
create_lec "$S06" 010601_eom_in_2d_3d 010602_force_vectors 010603_vector_composition 010604_vector_resolution 010605_velocity_composition 010606_relative_velocity 010607_momentum_cons_in_2d 010608_principle_of_work 010609_horizontal_projection 010610_oblique_projection 010611_motion_on_incline 010612_circular_motion 010613_keplers_laws 010614_simple_harmonic_motion 010615_simple_pendulum 010616_inertial_force
create_lec "$S07" 010701_moment_of_force 010702_fluid_mechanics

# 02/03 のディレクトリも同様に作成
mkdir -p "${P}${DIR_EXP}/exp01-intro" "${P}${DIR_EXE}/ex01-kinematics"

echo "Done. Structure created successfully."

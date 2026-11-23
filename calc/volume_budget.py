#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构光体积测量参数计算器（仅标准库）。

用法示例：
    python volume_budget.py --all
    python volume_budget.py --delta 0.42 --radius 50
    python volume_budget.py --voxel 0.5 --extent 200
    python volume_budget.py --views 6 --frames 13 --retry-views 1
"""

import argparse
import math


def volume_error_ratio(delta_mm, radius_mm):
    """一阶近似 ΔV/V ≈ 3δ/R（δ 与 R 同单位）。"""
    if radius_mm <= 0:
        raise ValueError("radius 必须为正")
    return 3.0 * delta_mm / radius_mm


def delta_rms(components_mm):
    """按方和根合成表面点定位误差。"""
    return math.sqrt(sum(c * c for c in components_mm))


def voxel_memory(voxel_mm, extent_mm, bytes_per_voxel=(4, 4, 12)):
    """返回 (每轴体素数, 各字段内存 MB)。bytes_per_voxel = (距离场, 权重, 法向)。"""
    n = int(round(extent_mm / voxel_mm))
    total = n ** 3
    dist_mb = total * bytes_per_voxel[0] / 1024 ** 2
    with_weight = dist_mb + total * bytes_per_voxel[1] / 1024 ** 2
    with_normal = with_weight + total * bytes_per_voxel[2] / 1024 ** 2
    return n, total, dist_mb, with_weight, with_normal


def wall_limits(voxel_mm):
    """TSDF 截断 τ = 3 体素；可信计入体积的壁厚下限 = 6 体素。"""
    return 3.0 * voxel_mm, 6.0 * voxel_mm


def timing_budget(views=6, frames=7, per_frame_s=0.114, phase_per_view_s=0.6,
                  completion_s=1.8, rotate_s=0.25, fusion_s=0.2,
                  classify_s=0.3, volume_s=3.5, io_s=3.7, retry_views=0):
    """在线单件时序预算，口径与方案表 7 一致。"""
    items = [
        ("条纹投射与采集", views * frames * per_frame_s),
        ("一级分类散斑帧", classify_s),
        ("相位解算与三角化", views * phase_per_view_s),
        ("双目补全", completion_s),
        ("转台旋转定位", views * rotate_s),
        ("点云融合", fusion_s),
        ("在线分类复核", classify_s),
        ("体素融合与符号积分", volume_s),
        ("系统调度与 IO", io_s),
    ]
    if retry_views > 0:
        items.append(("重采 %d 个视角" % retry_views,
                      retry_views * (frames * per_frame_s + rotate_s + phase_per_view_s)))
    return items, sum(v for _, v in items)


def _hr(title):
    print("\n" + title)
    print("-" * len(title))


def report_all(delta=0.42, radius=50, voxel=0.5, extent=200, views=6, frames=7):
    _hr("1. 体积误差（ΔV/V ≈ 3δ/R）")
    print("δ = %.2f mm, R = %.1f mm" % (delta, radius))
    print("ΔV/V = %.2f%%" % (volume_error_ratio(delta, radius) * 100))
    print("\nδ 敏感性：")
    for d in (0.30, 0.42, 0.60, 0.80):
        print("  δ=%.2f mm -> R=5cm: %.2f%%    R=10cm: %.2f%%"
              % (d, volume_error_ratio(d, 50) * 100, volume_error_ratio(d, 100) * 100))

    _hr("2. 体素与内存")
    for v in (0.5, 0.3):
        n, total, dist_mb, ww, wn = voxel_memory(v, extent)
        print("体素 %.2f mm: %d³ = %.1f M 体素" % (v, n, total / 1e6))
        print("  距离场 %.0f MB / 含权重 %.0f MB / 含法向 %.0f MB" % (dist_mb, ww, wn))
        tau, wall = wall_limits(v)
        print("  τ = %.2f mm, 壁厚下限 = %.1f mm" % (tau, wall))

    _hr("3. 时序预算")
    items, total = timing_budget(views=views, frames=frames)
    for name, sec in items:
        print("  %-18s %5.1f s" % (name, sec))
    print("  合计              %5.1f s" % total)
    _, total13 = timing_budget(views=views, frames=13)
    _, total13r = timing_budget(views=views, frames=13, retry_views=1)
    print("\n  7 幅：%.1f s ／ 13 幅：%.1f s ／ 13 幅+重采1视角：%.1f s"
          % (total, total13, total13r))
    print("  余量（对 60 s）：7 幅 %.1f s，13 幅+重采 %.1f s"
          % (60 - total, 60 - total13r))


def main():
    ap = argparse.ArgumentParser(description="结构光体积测量参数计算器")
    ap.add_argument("--all", action="store_true", help="输出全部报告")
    ap.add_argument("--delta", type=float, default=0.42, help="表面点定位误差 δ (mm)")
    ap.add_argument("--radius", type=float, default=50, help="等效半径 R (mm)")
    ap.add_argument("--voxel", type=float, default=0.5, help="体素尺寸 (mm)")
    ap.add_argument("--extent", type=float, default=200, help="包围盒边长 (mm)")
    ap.add_argument("--views", type=int, default=6, help="视角数")
    ap.add_argument("--frames", type=int, default=7, help="每视角幅数")
    ap.add_argument("--retry-views", type=int, default=0, help="重采视角数")
    ap.add_argument("--wall", action="store_true", help="输出壁厚与 τ")
    args = ap.parse_args()

    if args.all:
        report_all(args.delta, args.radius, args.voxel, args.extent, args.views, args.frames)
        return

    if args.wall:
        tau, wall = wall_limits(args.voxel)
        print("体素 %.2f mm -> τ = %.2f mm, 壁厚下限 = %.1f mm"
              % (args.voxel, tau, wall))
        n, total, *_ = voxel_memory(args.voxel, args.extent)
        print("网格 %d³ = %.1f M 体素" % (n, total / 1e6))
        return

    print("ΔV/V = %.2f%%（δ=%.2f mm, R=%.1f mm）"
          % (volume_error_ratio(args.delta, args.radius) * 100, args.delta, args.radius))
    items, total = timing_budget(args.views, args.frames, retry_views=args.retry_views)
    print("时序合计 %.1f s" % total)


if __name__ == "__main__":
    main()

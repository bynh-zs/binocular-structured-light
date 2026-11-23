#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标准件复核记录统计（仅标准库）。

读取 CSV（字段见 standard_parts_template.csv），按零件输出：
均值、标准差、最大绝对相对误差、P95 绝对相对误差、漂移（极差）、平均偏差，
并按类别设计目标给出是否超限的提示。

用法：
    python analyze_validation.py standard_parts_template.csv
    python analyze_validation.py 记录.csv --min-runs 10 --out 报告.md
"""

import argparse
import csv
import math
from collections import OrderedDict

# 类别 -> 设计目标相对误差上限（%），见 docs/03-误差与验收.md
TARGETS = {"类Ⅰ": 0.3, "类Ⅱ": 1.0, "类Ⅲ": 0.3}
PROMISE = 5.0   # 对外承诺


def p95(values):
    """线性插值分位数（与 numpy 默认 linear 方法等价）。"""
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = 0.95 * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r.get("part_id"):
                continue
            try:
                true_v = float(r["true_volume_ml"])
                meas_v = float(r["measured_ml"])
            except (TypeError, ValueError):
                continue
            if true_v <= 0:
                continue
            rows.append({
                "part_id": r["part_id"].strip(),
                "category": (r.get("category") or "未标注").strip(),
                "true": true_v,
                "meas": meas_v,
                "run": int(float(r["run_index"])) if str(r.get("run_index", "")).strip() else 0,
                "at": (r.get("measured_at") or "").strip(),
                "note": (r.get("note") or "").strip(),
            })
    return rows


def summarize(rows):
    groups = OrderedDict()
    for r in rows:
        groups.setdefault(r["part_id"], []).append(r)

    out = []
    for pid, rs in groups.items():
        rs = sorted(rs, key=lambda x: x["run"])
        errs = [(x["meas"] - x["true"]) / x["true"] * 100.0 for x in rs]
        abs_errs = [abs(e) for e in errs]
        n = len(rs)
        mean_v = sum(x["meas"] for x in rs) / n
        sd_v = math.sqrt(sum((x["meas"] - mean_v) ** 2 for x in rs) / (n - 1)) if n > 1 else 0.0
        cat = rs[0]["category"]
        out.append({
            "part_id": pid,
            "category": cat,
            "n": n,
            "true": rs[0]["true"],
            "mean": mean_v,
            "sd": sd_v,
            "max_abs_pct": max(abs_errs),
            "p95_abs_pct": p95(abs_errs),
            "drift_pct": (max(errs) - min(errs)),
            "bias_pct": sum(errs) / n,
            "target": TARGETS.get(cat),
        })
    return out


def render(stats, min_runs):
    lines = []
    lines.append("| 零件 | 类别 | 次数 | 真值(mL) | 均值(mL) | 标准差(mL) | 最大误差 | P95误差 | 漂移 | 平均偏差 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in stats:
        verdict = "—"
        if s["target"] is not None:
            if s["max_abs_pct"] <= s["target"]:
                verdict = "达标"
            elif s["max_abs_pct"] <= PROMISE:
                verdict = "超设计目标"
            else:
                verdict = "超对外承诺"
        lines.append("| %s | %s | %d | %.2f | %.2f | %.3f | %.2f%% | %.2f%% | %.2f%% | %+.2f%% | %s |"
                     % (s["part_id"], s["category"], s["n"], s["true"], s["mean"], s["sd"],
                        s["max_abs_pct"], s["p95_abs_pct"], s["drift_pct"], s["bias_pct"], verdict))
    return "\n".join(lines)


def warnings(stats, min_runs):
    msgs = []
    for s in stats:
        if s["n"] < min_runs:
            msgs.append("[次数不足] %s 仅 %d 次（要求 ≥%d），统计量不可用于答辩。"
                        % (s["part_id"], s["n"], min_runs))
        if s["target"] is not None and s["max_abs_pct"] > s["target"]:
            msgs.append("[超目标] %s 最大误差 %.2f%% 超设计目标 %.2f%%，须回溯δ分项与姿态。"
                        % (s["part_id"], s["max_abs_pct"], s["target"]))
        if s["drift_pct"] > (s["target"] or PROMISE) * 1.5:
            msgs.append("[漂移偏大] %s 极差 %.2f%%，疑似标定漂移或环境变化。"
                        % (s["part_id"], s["drift_pct"]))
    return msgs


def main():
    ap = argparse.ArgumentParser(description="标准件复核统计")
    ap.add_argument("csv_path")
    ap.add_argument("--min-runs", type=int, default=10, help="每件最少测量次数")
    ap.add_argument("--out", default=None, help="输出 Markdown 文件")
    args = ap.parse_args()

    rows = load(args.csv_path)
    if not rows:
        print("未读到有效数据（检查表头与数值列）")
        return 1

    stats = summarize(rows)
    md = render(stats, args.min_runs)
    warn = warnings(stats, args.min_runs)
    text = md + "\n\n" + ("\n".join("- " + w for w in warn) if warn else "无异常提示。")

    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\n已写入 %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

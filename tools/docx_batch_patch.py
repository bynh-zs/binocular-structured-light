#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Word 批量文本替换工具（python-docx）。

特点：
1. 替换清单用 JSON 描述，可带期望命中数（expect），命中不符即报错；
2. 支持正文段落与表格单元格（含嵌套表格）；
3. 段落内文字被拆散在多个 run 时，优先逐个 run 替换以保留局部格式；
4. 目标文件被 Word 打开（Windows 占用）时，改为写临时文件后按字节回写。

已知限制：超链接内的文字（w:hyperlink）不在 paragraph.runs 中，不会被替换。

用法：
    python docx_batch_patch.py 方案.docx --map fix.json --dry-run
    python docx_batch_patch.py 方案.docx --map fix.json --backup report.md
"""

import argparse
import json
import os
import shutil
import tempfile
import time

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def iter_paragraphs(doc):
    """遍历正文与所有表格单元格内的段落（含嵌套表格）。"""
    def walk_paras(container):
        for p in container.paragraphs:
            yield p
        for t in container.tables:
            for row in t.rows:
                for cell in row.cells:
                    yield from walk_paras(cell)
    yield from walk_paras(doc)


def replace_in_paragraph(p, find, repl):
    runs = p.runs
    if not runs:
        return 0
    joined = "".join(r.text for r in runs)
    if find not in joined:
        return 0
    count = joined.count(find)
    target = joined.replace(find, repl)
    per_run = "".join(r.text.replace(find, repl) for r in runs)
    if per_run == target:
        for r in runs:
            if find in r.text:
                r.text = r.text.replace(find, repl)
    else:
        # 跨 run：整段重写进首个 run，保留段落级格式，段内局部格式会损失
        runs[0].text = target
        for r in runs[1:]:
            r.text = ""
    return count


def safe_save(doc, target_path):
    """先存临时文件，再按字节回写目标；用于目标被占用时仍能落盘尝试。"""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx", dir=os.path.dirname(target_path) or ".")
    os.close(tmp_fd)
    try:
        doc.save(tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
        with open(target_path, "wb") as f:
            f.write(data)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser(description="Word 批量替换")
    ap.add_argument("doc_path")
    ap.add_argument("--map", required=True, help="JSON 替换清单")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写入")
    ap.add_argument("--backup", default=None, help="改前备份文件名（同目录）")
    ap.add_argument("--allow-missing", action="store_true", help="允许命中数少于 expect")
    args = ap.parse_args()

    with open(args.map, "r", encoding="utf-8") as f:
        spec = json.load(f)
    pairs = spec["pairs"] if isinstance(spec, dict) else spec

    if args.backup and not args.dry_run:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = args.backup.replace("{ts}", stamp)
        shutil.copy2(args.doc_path, bak)
        print("备份：%s" % bak)

    doc = Document(args.doc_path)
    report = []
    total = 0
    failed = False

    for item in pairs:
        find = item["find"]
        repl = item.get("replace", "")
        expect = item.get("expect")
        hits = 0
        for p in iter_paragraphs(doc):
            hits += replace_in_paragraph(p, find, repl)
        total += hits
        ok = True
        if expect is not None and hits < expect and not args.allow_missing:
            ok = False
            failed = True
        report.append((find, hits, expect, ok))
        print("[%s] 命中 %d 次%s | %s" % ("OK" if ok else "FAIL", hits,
                                         "" if expect is None else " (期望 ≥%d)" % expect,
                                         find[:40].replace("\n", " ")))

    print("\n总命中 %d 处" % total)

    if args.dry_run:
        print("dry-run：未写入")
        return 1 if failed else 0

    safe_save(doc, args.doc_path)
    print("已写入：%s" % args.doc_path)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

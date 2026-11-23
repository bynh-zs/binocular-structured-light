#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 docx 的标题结构与表格清单，用于同步文档摘要。

用法：
    python doc_outline.py 方案.docx
    python doc_outline.py 方案.docx --out outline.md
"""

import argparse

from docx import Document


def main():
    ap = argparse.ArgumentParser(description="docx 大纲导出")
    ap.add_argument("doc_path")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    doc = Document(args.doc_path)
    lines = ["# 文档大纲", "",
             "段落总数：%d　表格总数：%d" % (len(doc.paragraphs), len(doc.tables)), "",
             "## 标题结构", ""]

    n_head = 0
    for p in doc.paragraphs:
        style = p.style.name if p.style is not None else ""
        text = p.text.strip()
        if not text:
            continue
        if style.lower().startswith("heading") or style == "Title":
            level = 0 if style == "Title" else int(style.split()[-1]) if style[-1].isdigit() else 1
            lines.append("%s%s（%s）" % ("  " * max(level - 1, 0) + "- ", text, style))
            n_head += 1

    lines += ["", "## 表格清单", ""]
    for i, t in enumerate(doc.tables):
        try:
            head = " / ".join(c.text.strip() for c in t.rows[0].cells)[:80]
        except IndexError:
            head = "(空表)"
        lines.append("- 表%d：%d 行 × %d 列｜首行：%s" % (i + 1, len(t.rows), len(t.columns), head))

    text = "\n".join(lines)
    print(text)
    print("\n共识别 %d 个标题" % n_head)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("已写入 %s" % args.out)


if __name__ == "__main__":
    main()

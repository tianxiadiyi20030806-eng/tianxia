#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown → HTML → PDF

把 docs/ 下的 markdown 文档转成排版好的 PDF，方便阅读和打印。

【用法】
    cd ~/rag-project
    source .venv/bin/activate
    python3 docs/md2pdf.py docs/学习手册.md

【原理】
    ① markdown 库：md → HTML 片段
    ② 套上 CSS（中文字体、A4 页面、表格样式）
    ③ soffice 命令行：HTML → PDF
"""

import os
import subprocess
import sys

import markdown

CSS = """
@page { size: A4; margin: 1.6cm 1.8cm; }
body {
    font-family: "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
    font-size: 10pt;
    line-height: 1.65;
    color: #1c1c1c;
    margin: 0;
}
h1 {
    font-size: 20pt; color: #14508a; margin: 0 0 6px 0;
    border-bottom: 3px solid #2c6fb5; padding-bottom: 8px;
}
h2 {
    font-size: 14pt; color: #14508a;
    margin: 20px 0 8px 0; padding: 4px 0 4px 9px;
    border-left: 5px solid #2c6fb5;
    border-bottom: 1px solid #dce7f2;
    page-break-after: avoid;
}
h3 {
    font-size: 11.5pt; color: #1a6bb0;
    margin: 14px 0 6px 0;
    page-break-after: avoid;
}
h4 { font-size: 10.5pt; color: #333; margin: 10px 0 4px 0; }
p { margin: 5px 0; }
ul, ol { margin: 5px 0 5px 0; padding-left: 20px; }
li { margin-bottom: 3px; }

/* 代码 */
code {
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 9pt;
    background: #f4f6f8;
    padding: 1px 4px;
    border-radius: 3px;
    color: #b03030;
}
pre {
    background: #f7f9fb;
    border: 1px solid #dce7f2;
    border-left: 4px solid #2c6fb5;
    padding: 8px 10px;
    margin: 7px 0;
    font-size: 8.6pt;
    line-height: 1.45;
    white-space: pre-wrap;
    word-wrap: break-word;
    page-break-inside: avoid;
}
pre code { background: none; padding: 0; color: #1c1c1c; }

/* 表格 */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
    font-size: 9pt;
    page-break-inside: avoid;
    table-layout: fixed;
}
th, td { word-wrap: break-word; }
th {
    background: #eaf2fa;
    color: #14508a;
    font-weight: bold;
    text-align: left;
    white-space: nowrap;      /* 表头不换行 → 撑宽整列 */
}
th, td { border: 1px solid #cfe0ef; padding: 5px 8px; }

/* 引用块 */
blockquote {
    margin: 8px 0;
    padding: 6px 12px;
    background: #fdf8e8;
    border-left: 4px solid #e0b040;
    color: #5a4a20;
}
blockquote p { margin: 3px 0; }

/* 分隔线 */
hr { border: none; border-top: 1px solid #dce7f2; margin: 18px 0; }

a { color: #2c6fb5; text-decoration: none; }
strong { color: #0f3f70; }
"""


def main():
    if len(sys.argv) < 2:
        print("用法：python3 md2pdf.py <markdown 文件>")
        raise SystemExit(1)

    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print("❌ 文件不存在：" + md_path)
        raise SystemExit(1)

    base = os.path.splitext(md_path)[0]
    html_path = base + ".html"
    pdf_path = base + ".pdf"

    # ── ① markdown → HTML ──
    with open(md_path, encoding="utf-8") as f:
        text = f.read()

    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )

    title = os.path.basename(base)
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8">\n<title>' + title + '</title>\n'
        '<style>' + CSS + '</style>\n</head>\n<body>\n'
        + body + '\n</body>\n</html>\n'
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("① HTML 已生成：" + html_path)

    # ── ② HTML → PDF（用 LibreOffice）──
    outdir = os.path.dirname(os.path.abspath(html_path))
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf",
         "--outdir", outdir, os.path.abspath(html_path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path) // 1024
        print("② PDF 已生成：" + pdf_path + "  (" + str(size) + " KB)")
    else:
        print("❌ PDF 生成失败")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目第一步：把资料变成纯文本

为什么需要这一步？
    程序读不懂 PDF 和 docx，只认识纯文本。
    所以要把它们全部转成 .txt —— 这是所有 RAG 系统的第一道工序。

两种格式怎么处理？
    PDF   -> 用系统的 pdftotext 命令（已经装好了）
    docx  -> 用 Python 标准库。因为 .docx 本质上就是个 zip 压缩包，
             里面的 word/document.xml 就是正文

【运行】
    python3 build_corpus.py

【产出】
    ~/xiangmu/corpus/*.txt
"""

import os
import subprocess
import zipfile
from xml.etree import ElementTree as ET

SRC = os.path.expanduser("~/xiangmu/xuexi")
OUT = os.path.expanduser("~/xiangmu/corpus")

# docx 内部的 XML 命名空间，解析时必须带上
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def pdf_to_text(pdf_path, txt_path):
    """PDF 转文字。-layout 参数保留原有排版（表格、缩进会好看很多）"""
    subprocess.run(
        ["pdftotext", "-layout", pdf_path, txt_path],
        check=True,
    )


def docx_to_text(docx_path, txt_path):
    """docx 转文字。docx = zip 包，正文在 word/document.xml 里"""
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")

    root = ET.fromstring(xml_bytes)

    # 一个 <w:p> 就是一段；一段里的多个 <w:t> 拼起来才是完整文字
    paras = []
    for p in root.iter(W + "p"):
        text = "".join(t.text or "" for t in p.iter(W + "t"))
        if text.strip():
            paras.append(text.strip())

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(paras))

    return len(paras)


def main():
    os.makedirs(OUT, exist_ok=True)

    names = sorted(os.listdir(SRC))
    print("资料目录：" + SRC)
    print("找到 " + str(len(names)) + " 个文件")
    print("=" * 60)

    ok = 0
    total_chars = 0

    for name in names:
        src = os.path.join(SRC, name)
        if not os.path.isfile(src):
            continue

        base = os.path.splitext(name)[0]
        dst = os.path.join(OUT, base + ".txt")
        lower = name.lower()

        try:
            if lower.endswith(".pdf"):
                pdf_to_text(src, dst)
                note = ""

            elif lower.endswith(".docx"):
                n = docx_to_text(src, dst)
                note = "（" + str(n) + " 段）"

            else:
                print("⏭  跳过  " + name + "   ← 暂不支持的格式")
                continue

        except Exception as e:
            print("❌ 失败  " + name)
            print("       " + str(e))
            continue

        chars = len(open(dst, encoding="utf-8").read())
        total_chars += chars
        ok += 1

        print("✅ 成功  " + name + " " + note)
        print("        → " + os.path.basename(dst) + "   " + str(chars) + " 字")

    print("=" * 60)
    print("转换成功 " + str(ok) + " 个文件，共 " + str(total_chars) + " 字")
    print("输出目录：" + OUT)
    print()
    print("下一步：把这些文本切成小块（chunk）")


if __name__ == "__main__":
    main()

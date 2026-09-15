#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目第三步：切块（chunking）

【为什么必须切？】

整篇 4 万字塞给模型会出三个问题：
    ① 上下文爆炸（前面已经学过：超过窗口直接报 400）
    ② 又贵又慢（每次请求都发 4 万字）
    ③ 模型抓不到重点（信息太多反而答不准）

切成小块，每次只送【最相关的 2~3 块】—— 这才是 RAG 的核心思想。

【怎么切才对？】

❌ 按固定字数硬切   → 会把一条配置说明从中间劈断
✅ 按标题层级切     → 每块语义完整

【面包屑】

光切还不够。一块内容如果脱离了上下文，检索到了也没用。
所以每块前面要带上"我在哪一章"：

    面包屑：模块B-服务部署 › （一）DCserver 配置任务 › 4．DHCP SERVICE
    正文：  安装及配置 DHCP 服务；创建一个名为"ChinaSkills.cn"的 DHCP 作用域...

【运行】
    python3 chunk_docs.py
"""

import json
import os
import re

CLEAN_DIR = os.path.expanduser("~/xiangmu/clean")
OUT_FILE = os.path.expanduser("~/xiangmu/chunks.json")

# 一条块的最小 / 最大字数。太小没信息量，太大检索不准。
MIN_CHARS = 120
MAX_CHARS = 700

# ────────────────────────────────────────────────────────────
# 标题识别：不同层级，不同正则
# ────────────────────────────────────────────────────────────
PATTERNS = [
    (0, re.compile(r"^\s*(模块\s*[A-Za-z].*|附录\s*[0-9].*)$")),           # 模块A-网络构建
    (1, re.compile(r"^\s*([一二三四五六七八九十]+)\s*、\s*(.+)$")),         # 一、基础配置
    (2, re.compile(r"^\s*[（(]([一二三四五六七八九十]+)[）)]\s*(.+)$")),     # （一）DCserver
    (3, re.compile(r"^\s*([0-9]+)\s*[．、]\s*(.+)$")),                    # 1．系统基础环境配置
    (4, re.compile(r"^\s*[（(]([0-9]+)[）)]\s*(.+)$")),                    # （1）请根据...
]


def detect_heading(line):
    """判断这一行是不是标题。返回 (层级, 标题文字) 或 (None, None)"""
    for level, pat in PATTERNS:
        m = pat.match(line)
        if m:
            title = m.group(m.lastindex).strip() if m.lastindex else line.strip()
            return level, title
    return None, None


def split_into_sections(text):
    """按标题把文本切成小节，每节带上所属的章节路径（面包屑）"""
    sections = []
    crumb = {}          # 层级 -> 标题
    buf = []

    def flush():
        if not buf:
            return
        body = "\n".join(buf).strip()
        if not body:
            return
        # 面包屑只保留"像标题"的部分：
        #   · 过长的说明它其实是正文，截断
        #   · 只留最后 3 层，更深的层级对检索没帮助、只添噪音
        parts = []
        for k in sorted(crumb):
            t = crumb[k].strip()
            if not t:
                continue
            if len(t) > 30:
                t = t[:30] + "…"
            parts.append(t)
        parts = parts[-3:]
        path = " › ".join(parts)
        sections.append((path, body))
        buf.clear()

    for line in text.split("\n"):
        level, title = detect_heading(line)

        if level is not None:
            flush()
            crumb[level] = title
            # 清掉比它更深的层级（同级换了，子级作废）
            for k in list(crumb):
                if k > level:
                    del crumb[k]
            buf.append(line.strip())
        else:
            buf.append(line)

    flush()
    return sections


def merge_small(sections):
    """把太小的节合并到一起，避免产生一堆没信息量的碎片"""
    out = []
    for path, body in sections:
        if out and len(body) < MIN_CHARS and out[-1][0] == path:
            out[-1] = (out[-1][0], out[-1][1] + "\n" + body)
        elif out and len(out[-1][1]) < MIN_CHARS and out[-1][0] == path:
            out[-1] = (out[-1][0], out[-1][1] + "\n" + body)
        else:
            out.append((path, body))
    return out


def cut_long(path, body):
    """太长的节，切开。

    ⚠️ 第一版只按句末标点切，结果表格类内容（一个句号都没有）完全切不动，
       出现了 3767 字的巨型块。

    现在分两级：
       第一级：按句末标点（。；！？）切    → 适合正文
       第二级：还是太长就按【行】切        → 兜住表格这类"无标点"内容
    """
    if len(body) <= MAX_CHARS:
        return [(path, body)]

    # 第一级：按句子切
    sentences = re.split(r"(?<=[。；！？])", body)

    # 第二级：句子还是太长（表格）→ 退化成按行切
    units = []
    for s in sentences:
        if len(s) > MAX_CHARS:
            units.extend(s.split("\n"))
        else:
            units.append(s)

    # 贪心合并到接近 MAX_CHARS
    pieces = []
    cur = ""
    for u in units:
        if len(cur) + len(u) > MAX_CHARS and cur.strip():
            pieces.append((path, cur.strip()))
            cur = u
        else:
            cur += u
    if cur.strip():
        pieces.append((path, cur.strip()))

    return pieces


def main():
    files = [f for f in sorted(os.listdir(CLEAN_DIR)) if f.endswith(".txt")]

    chunks = []
    cid = 0

    print("输入目录：" + CLEAN_DIR)
    print("=" * 66)

    for name in files:
        text = open(os.path.join(CLEAN_DIR, name), encoding="utf-8").read()
        sections = split_into_sections(text)
        sections = merge_small(sections)

        final = []
        for path, body in sections:
            final.extend(cut_long(path, body))

        print("📄 " + name)
        print("   切成 " + str(len(final)) + " 块")

        for path, body in final:
            if len(body.strip()) < 30:      # 扔掉纯标题的空壳
                continue
            cid += 1
            chunks.append({
                "id": cid,
                "source": name,
                "path": path,
                "text": body,
                "chars": len(body),
            })

        print()

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)

    sizes = [c["chars"] for c in chunks]
    print("=" * 66)
    print("总块数：" + str(len(chunks)))
    print("平均块长：" + str(sum(sizes) // len(sizes)) + " 字")
    print("最短：" + str(min(sizes)) + " 字   最长：" + str(max(sizes)) + " 字")
    print("输出：" + OUT_FILE)


if __name__ == "__main__":
    main()

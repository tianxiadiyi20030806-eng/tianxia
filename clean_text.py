#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目第二步：清洗修复

【要解决什么问题？】

pdftotext 把一批二级标题"吞"进了上一段的末尾，例如：

    修复前： 注：本题目中没特别说明的密码皆为：ChinaSkills23。1．DCserver 系统基础环境配置

    修复后： 注：本题目中没特别说明的密码皆为：ChinaSkills23。
            1．DCserver 系统基础环境配置

如果不修，按标题切块时边界会全部错位 —— 上一条任务的结尾会和下一条
任务的标题被切进同一块，检索出来全是乱的。

【难点在哪？】

语料里到处都是 IP 地址：172.16.100.221、8.8.8.8、193.1.10.254
如果正则写糙了，会把 IP 里的点当成分隔符，把 IP 切成两半。

所以规则必须同时满足三个条件才认为是"被吞的标题"：
    ① 前面必须是句号或分号（。；）
    ② 跟着的是 数字 + 全角点/顿号（．、）
    ③ 那个点后面【不能是数字】   ← 这一条专门用来排除 IP

【运行】
    python3 clean_text.py

【产出】
    ~/xiangmu/clean/*.txt
"""

import os
import re

IN_DIR = os.path.expanduser("~/xiangmu/corpus")
OUT_DIR = os.path.expanduser("~/xiangmu/clean")

# ────────────────────────────────────────────────────────────
# 核心正则：找出"被吞的标题"边界
#
#   ([。；])          第1组：前面的句号或分号
#   \s*               中间可能有空白
#   ([0-9]+[．、])    第2组：序号 + 全角点或顿号
#   (?=[^\d])         后面【不能是数字】—— 排除了 8.8.8.8 这类 IP
#
# 替换成：\1\n\2     即"句号" + 换行 + "序号"
# ────────────────────────────────────────────────────────────
BURIED_HEADING = re.compile(r"([。；])\s*([0-9]+[．、.](?=[^\d]))")

# ────────────────────────────────────────────────────────────
# 判断"这一行是不是新条目的开头"
# 用来决定：换行处到底该"接上去"还是"断开"
# ────────────────────────────────────────────────────────────
HEADING_START = re.compile(
    r"^\s*("
    r"模块\s*[A-Za-z]"                          # 模块A / 模块B
    r"|附录\s*[0-9]"                            # 附录1
    r"|[一二三四五六七八九十]+\s*、"             # 一、 二、
    r"|[（(][一二三四五六七八九十0-9]+[）)]"      # （一） （1）
    r"|[0-9]+\s*[．、]"                         # 1． 2、
    r")"
)

# 句子已经结束的标点。以这些结尾的行，视为"写完了"
END_PUNCT = "。；！？："

# 一行里有 3 个以上连续空格 → 认为是表格行，不参与拼接
TABLE_LIKE = re.compile(r"\S {3,}\S")

# ────────────────────────────────────────────────────────────
# 目录识别
#
# 为什么必须去掉目录？
#     目录里包含【所有】标题文字。做检索时，任何查询都会命中目录块，
#     产生大量假阳性，而且目录里根本没有实际内容。
#
# 两种目录长得不一样：
#     PDF ：  一、基础配置 ..................... 3      （点线 + 页码）
#     docx：  一、Windows初始化环境1                  （页码直接贴着）
# ────────────────────────────────────────────────────────────
TOC_MARKER = re.compile(r"目\s*录")
TOC_ENTRY = re.compile(r"(\.{4,}\s*[0-9]+\s*$)|(^.{1,40}[0-9]\s*$)")


def join_wrapped_lines(text):
    """只做一件很保守的事：把被换行截断的【标题】接回去。

    ⚠️ 第一版我是按"上一行没以句号结尾 → 就接上下一行"来拼的。
       结果把【标题】和后面的【正文段落】拼成了一整行 ——
       面包屑变成了几百字的段落，彻底坏掉。

    现在的规则（保守得多）：
       只有当【当前行是标题】且【下一行是缩进的短行】时才拼接。
       其余一律不动 —— 中文正文里夹杂换行不影响模型阅读，不用管。
    """
    lines = text.split("\n")
    out = []
    i = 0

    while i < len(lines):
        cur = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""

        cont = nxt.strip()
        indented = (len(nxt) - len(nxt.lstrip())) >= 2

        # 标题 + 后面跟着一个缩进的短行 → 标题被换行截断了，接上
        if HEADING_START.match(cur) and cont and indented and len(cont) <= 15:
            out.append(cur.rstrip() + cont)
            i += 2
            continue

        out.append(cur)
        i += 1

    return "\n".join(out)


def strip_toc(lines):
    """去掉目录区。

    做法：找到"目 录"这一行之后，连续跳过所有"标题+页码"格式的行。
    要求至少跳过 3 条才认定为目录，避免误删正常内容。
    """
    out = []
    i = 0
    n = len(lines)
    removed = 0

    while i < n:
        line = lines[i]

        # 找到目录标记（"目 录"这一行本身很短）
        if TOC_MARKER.search(line) and len(line.strip()) < 20:
            j = i + 1
            skipped = 0
            while j < n:
                s = lines[j].strip()
                if not s:                      # 目录里夹杂空行，跳过
                    j += 1
                    continue
                if TOC_ENTRY.search(lines[j]):
                    skipped += 1
                    j += 1
                    continue
                break                          # 遇到正文，停

            if skipped >= 3:                   # 至少 3 条才算目录
                removed = skipped
                i = j
                continue

        out.append(line)
        i += 1

    return out, removed


def clean(text):
    """返回 (清洗后的文本, 修复记录列表)"""
    fixes = []

    # ── 修复 0：去掉 pdftotext 插入的换页符（\f, 0x0c）──
    # ⚠️ 这个不可见字符会伪装成"缩进"：
    #    一行原本是 "\f 一、Windows初始化环境"（换页符 + 1个空格）
    #    缩进检测 len(L)-len(L.lstrip()) 会算成 2，误判成"缩进较深的续行"
    #    结果把上一行的标题和它拼接成了一整行，面包屑彻底坏掉。
    #    这个 bug 花了 3 轮才找出来，因为它【肉眼看不见】。
    text = text.replace("\f", "\n")

    # ── 修复 1：把被吞的标题拆出来 ──
    def repl(m):
        before = m.group(1)
        after = m.group(2)
        # 记下上下文，方便人工核对
        start = max(0, m.start() - 20)
        fixes.append((text[start:m.start() + 1] + after,
                      before + " ⏎ " + after))
        return before + "\n" + after

    text = BURIED_HEADING.sub(repl, text)

    # ── 修复 2：把被 PDF 换行截断的行接回去 ──
    text = join_wrapped_lines(text)

    # ── 修复 3：统一换行符 ──
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ── 修复 4：去掉每行末尾的空格 ──
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # ── 修复 5：把连续 3 个以上空行压成 1 个 ──
    text = re.sub(r"\n{3,}", "\n\n", text)

    # ── 修复 6：全角空格统一成半角（PDF 里常见）──
    text = text.replace("\u3000", " ")

    # ── 修复 7：去掉目录区（它包含所有标题，会污染检索）──
    lines, toc_removed = strip_toc(text.split("\n"))
    text = "\n".join(lines)
    fixes.append(("(目录区)", "删除了 " + str(toc_removed) + " 行目录条目"))

    return text, fixes


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    files = [f for f in sorted(os.listdir(IN_DIR)) if f.endswith(".txt")]
    print("输入目录：" + IN_DIR)
    print("找到 " + str(len(files)) + " 个文本文件")
    print()

    grand_total = 0

    for name in files:
        src = os.path.join(IN_DIR, name)
        dst = os.path.join(OUT_DIR, name)

        raw = open(src, encoding="utf-8").read()
        fixed, fixes = clean(raw)

        open(dst, "w", encoding="utf-8").write(fixed)

        print("=" * 66)
        print("📄 " + name)
        print("   " + str(len(raw)) + " 字  →  " + str(len(fixed)) + " 字")
        print("   修复被吞标题：" + str(len(fixes)) + " 处")

        if fixes:
            for old, new in fixes[:5]:
                print("     · …" + old[-30:].strip())
                print("       → " + new)
            if len(fixes) > 5:
                print("     · …还有 " + str(len(fixes) - 5) + " 处，详见输出文件")

        grand_total += len(fixes)
        print()

    print("=" * 66)
    print("全部完成，共修复 " + str(grand_total) + " 处标题")
    print("输出目录：" + OUT_DIR)
    print()
    print("下一步：切块")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库问答助手（RAG 完整版）

流程：问题 → 分词 → 检索 Top-3 → 拼成提示词 → 交给 AI → 基于资料回答

用法：
    export DEEPSEEK_API_KEY=sk-你的key
    python3 rag.py
"""

import json
import os
import urllib.error
import urllib.request

# ═══════════════════════════════════════════════════════
# 第一部分：中文分词
# ═══════════════════════════════════════════════════════

def char_type(ch):
    if '\u4e00' <= ch <= '\u9fff':
        return "cn"
    if ch.isascii() and (ch.isalnum() or ch == "."):
        return "ascii"
    return "other"


def group_by_type(text):
    groups = []
    cur = ""
    cur_type = None
    for ch in text:
        t = char_type(ch)
        if t == "other":
            if cur:
                groups.append((cur_type, cur))
            cur = ""
            cur_type = None
            continue
        if t != cur_type:
            if cur:
                groups.append((cur_type, cur))
            cur = ch
            cur_type = t
        else:
            cur += ch
    if cur:
        groups.append((cur_type, cur))
    return groups


def cut_cn(s):
    words = []
    prev = None
    for ch in s:
        if prev is not None:
            words.append(prev + ch)
        prev = ch
    return words


def tokenize(text):
    result = []
    for t, g in group_by_type(text):
        if t == "ascii":
            result.append(g)
        else:
            if len(g) == 1:
                result.append(g)
            else:
                for w in cut_cn(g):
                    result.append(w)
    return result


# ═══════════════════════════════════════════════════════
# 第二部分：建索引 + 算权重
# ═══════════════════════════════════════════════════════

# 读取本文件所在目录下的 chunks.json
# ⚠️ 不要写死 /home/zhang/... 这种绝对路径 —— 别人 clone 下来会直接报错
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.json")

chunks = json.load(open(CHUNKS_PATH, encoding="utf-8"))

index = []
for c in chunks:
    index.append({
        "id": c["id"],
        "path": c["path"],
        "text": c["text"],
        "words": tokenize(c["text"]),
    })

df = {}
for item in index:
    for w in set(item["words"]):
        df[w] = df.get(w, 0) + 1


def weight(w):
    if w not in df:
        return 0
    return len(index) / df[w]


# ═══════════════════════════════════════════════════════
# 第三部分：检索
# ═══════════════════════════════════════════════════════

def search(query, top_k=3):
    qwords = tokenize(query)
    results = []
    for item in index:
        s = 0
        for w in qwords:
            if w in item["words"]:
                s = s + weight(w)
        results.append((s, item["id"], item))
    results.sort(reverse=True)
    return results[:top_k]


# ═══════════════════════════════════════════════════════
# 第四部分：调用 AI
# ═══════════════════════════════════════════════════════

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 没找到 API key，请先执行：export DEEPSEEK_API_KEY=sk-你的key")
    raise SystemExit(1)

# ── key 自检：提前发现问题，别等报错 ──
_bad = [c for c in API_KEY if not c.isascii()]
if _bad:
    print("❌ key 里有非 ASCII 字符：" + repr(_bad))
    print("   多半是复制时带进了中文符号或全角字符，请重新复制")
    raise SystemExit(1)

URL = "https://api.deepseek.com/chat/completions"


def ask_ai(prompt):
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        return "❌ HTTP " + str(e.code) + "：" + str(e.reason) + "\n" + detail
    except urllib.error.URLError as e:
        return "❌ 连不上服务器：" + str(e.reason)
    except Exception as e:
        # 兜底：任何没预料到的错误，都显示类型和原因，不再甩出一屏红字
        return "❌ 请求失败：" + type(e).__name__ + " — " + str(e)

    return json.loads(raw)["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════
# 第五部分：RAG 问答
# ═══════════════════════════════════════════════════════

def answer(question):
    # ① 检索出最相关的 3 块
    hits = search(question, top_k=3)

    # ② 把它们拼成"资料"文本
    context = ""
    n = 0
    for s, cid, item in hits:
        n = n + 1
        context = context + "\n【资料" + str(n) + "（块#" + str(cid) + "）】\n" + item["text"] + "\n"

    # ③ 拼提示词 —— 三条硬规则，防止 AI 瞎编
    prompt = (
        "请严格依据下面提供的资料回答问题。\n"
        "规则：\n"
        "1. 只能使用资料中的内容，不要使用你自己的知识\n"
        "2. 如果资料中没有答案，直接回答「资料里没有找到相关内容」\n"
        "3. 回答末尾标注依据的是哪几条资料\n\n"
        "===== 资料开始 =====\n"
        + context +
        "\n===== 资料结束 =====\n\n"
        "问题：" + question
    )

    return ask_ai(prompt)


# ═══════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════

print("📚 知识库问答助手")
print("   知识库：" + str(len(index)) + " 个知识块")
print("   输入问题回车；输入 exit 退出")
print("=" * 60)

while True:
    q = input("\n❓ ")
    if q.strip() == "exit":
        print("再见！")
        break
    if not q.strip():
        continue
    print("\n🤖 " + answer(q))

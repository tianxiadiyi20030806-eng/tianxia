#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库问答助手 —— RAG 问答主程序

流程：问题 → 检索 Top-3（调用 retrieval.py）→ 拼提示词 → 交给 AI → 基于资料回答

用法：
    export DEEPSEEK_API_KEY=sk-你的key
    python3 rag.py
"""

import json
import os
import urllib.error
import urllib.request

from retrieval import Retriever

# ═══════════════════════════════════════════════════════
# 一、检索器（分词 / 索引 / TF-IDF 检索都在 retrieval.py）
# ═══════════════════════════════════════════════════════

retriever = Retriever()

# ═══════════════════════════════════════════════════════
# 二、调用大模型
# ═══════════════════════════════════════════════════════

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 没找到 API key，请先执行：export DEEPSEEK_API_KEY=sk-你的key")
    raise SystemExit(1)

# key 自检：复制时带进中文/全角字符会导致 UnicodeEncodeError
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
        return "❌ 请求失败：" + type(e).__name__ + " — " + str(e)

    return json.loads(raw)["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════
# 三、RAG 问答
# ═══════════════════════════════════════════════════════

def answer(question):
    # ① 检索出最相关的 3 块
    hits = retriever.search(question, top_k=3)

    # ② 拼成"资料"文本
    context = ""
    n = 0
    for score, cid, item in hits:
        n = n + 1
        context = context + "\n【资料" + str(n) + "（块#" + str(cid) + "）】\n" + item["text"] + "\n"

    # ③ 拼提示词 —— 三条硬规则，防止模型瞎编
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
# 四、主程序
# ═══════════════════════════════════════════════════════

print("📚 知识库问答助手")
print("   知识库：" + str(len(retriever)) + " 个知识块")
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

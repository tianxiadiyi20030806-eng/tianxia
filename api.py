#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库 API —— 检索 + AI 问答

【接口列表】

    GET  /          服务状态
    GET  /search    检索（只返回相关段落，不调用大模型）
    GET  /stats     知识库统计
    POST /ask       完整问答（检索 + 调大模型生成回答）★ 新增

【运行】

    cd ~/rag-project
    source .venv/bin/activate
    export DEEPSEEK_API_KEY=sk-你的key
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

    然后浏览器打开 http://127.0.0.1:8000/docs
"""

import json
import os
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from retrieval import Retriever

# ═══════════════════════════════════════════════════════
# 一、创建应用 + 加载检索器
# ═══════════════════════════════════════════════════════

app = FastAPI(
    title="知识库 API",
    description="基于 TF-IDF 检索 + 大模型生成的 RAG 服务",
    version="2.0.0",
)

retriever = Retriever()


# ═══════════════════════════════════════════════════════
# 二、调用大模型
#
#    ⚠️ 关键：API key 从【环境变量】读，不能写在代码里
#        - 写死在代码里 → 提交到 GitHub 就泄露了
#        - 从环境变量读 → 部署时再设置，代码可以公开
# ═══════════════════════════════════════════════════════

LLM_URL = "https://api.deepseek.com/chat/completions"


def call_llm(prompt):
    """把提示词发给大模型，返回回答文字"""

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("服务端没有配置 DEEPSEEK_API_KEY 环境变量")

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        LLM_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")

    return json.loads(raw)["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════
# 三、请求体模型（Pydantic）
#
#    【新概念】用 Python 类来定义"客户端该发什么格式的 JSON"
#
#    好处：
#      ① 自动校验 —— 缺字段 / 类型不对，FastAPI 自动返回 422 错误
#      ② 自动文档 —— /docs 页面会显示请求体的结构
#      ③ 代码提示 —— 用 req.question 访问，拼错编辑器会提示
# ═══════════════════════════════════════════════════════

class AskRequest(BaseModel):
    """POST /ask 的请求体格式"""
    question: str                      # 必填：问题
    top_k: int = 3                     # 选填：检索几条资料，默认 3


# ═══════════════════════════════════════════════════════
# 四、接口定义
# ═══════════════════════════════════════════════════════

@app.get("/")
def root():
    """根路径：返回服务状态"""
    return {
        "service": "知识库 API",
        "version": "2.0.0",
        "status": "running",
        "chunks": len(retriever),
        "endpoints": ["/search", "/ask", "/stats", "/docs"],
    }


@app.get("/search")
def search(
    q: str = Query(..., description="检索关键词，例如：DHCP中继怎么配"),
    top_k: int = Query(3, description="返回条数"),
):
    """检索接口：只返回相关段落，不调用大模型"""
    hits = retriever.search(q, top_k=top_k)

    results = []
    for score, cid, item in hits:
        results.append({
            "score": round(score, 1),
            "id": cid,
            "path": item["path"],
            "text": item["text"],
        })

    return {"query": q, "count": len(results), "results": results}


@app.get("/stats")
def stats():
    """统计接口：返回知识库规模"""
    n = len(retriever)
    total = sum(len(item["text"]) for item in retriever.index)
    return {"chunks": n, "total_chars": total, "avg_chars": total // n}


@app.post("/ask")
def ask(req: AskRequest):
    """问答接口：RAG 完整流程（检索 → 拼提示词 → 调大模型 → 返回带来源的回答）

    注意这里是 POST 而不是 GET：
        参数放在【请求体】里，而不是 URL 里。
        因为问题可能很长，放 URL 里会超长度限制，也会被服务器日志记录。
    """

    # ── ① 检索 ──
    hits = retriever.search(req.question, top_k=req.top_k)

    if not hits:
        return {
            "question": req.question,
            "answer": "知识库中没有找到相关内容。",
            "sources": [],
        }

    # ── ② 把检索结果拼成"资料"文本 ──
    context = ""
    n = 0
    for score, cid, item in hits:
        n = n + 1
        context = context + "\n【资料" + str(n) + "（块#" + str(cid) + "）】\n" + item["text"] + "\n"

    # ── ③ 拼提示词（三条硬规则，防止模型瞎编）──
    prompt = (
        "请严格依据下面提供的资料回答问题。\n"
        "规则：\n"
        "1. 只能使用资料中的内容，不要使用你自己的知识\n"
        "2. 如果资料中没有答案，直接回答「资料里没有找到相关内容」\n"
        "3. 回答末尾标注依据的是哪几条资料\n\n"
        "===== 资料开始 =====\n"
        + context +
        "\n===== 资料结束 =====\n\n"
        "问题：" + req.question
    )

    # ── ④ 调大模型 ──
    try:
        answer = call_llm(prompt)
    except Exception as e:
        # HTTPException 会让 FastAPI 返回一个规范化的错误响应（不是 500 崩溃）
        raise HTTPException(status_code=502, detail="调用大模型失败：" + str(e))

    # ── ⑤ 返回回答 + 来源 ──
    sources = []
    for score, cid, item in hits:
        sources.append({
            "id": cid,
            "score": round(score, 1),
            "path": item["path"],
        })

    return {
        "question": req.question,
        "answer": answer,
        "sources": sources,
    }

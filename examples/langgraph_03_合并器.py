#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三个 LangGraph —— 理解"合并器（reducer）"

两个字段，用两种合并规则：
    name     → 默认规则：覆盖
    history  → 自定义规则：追加

跑一遍就能看清差别，也就明白了为什么 LangGraph 的 agent 例子里
messages 字段要写成 Annotated[list, add_messages]。

【运行】
    cd ~/rag-project
    source .venv/bin/activate
    python3 langgraph_demo3.py
"""

from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


# ═══════════════════════════════════════════════════════
# 自定义合并器（reducer）
#
#    签名固定：接收 (旧值, 新值)，返回合并后的值
#    这里实现的是"追加"——把新值接在旧值后面，而不是覆盖
# ═══════════════════════════════════════════════════════

def append_list(old, new):
    return old + new


class State(TypedDict):
    name: str                                  # 不指定合并器 → 默认 = 覆盖
    history: Annotated[list, append_list]      # 指定了 → 用 append_list 合并


def node_a(state):
    print("  进入 node_a，看到：", dict(state))
    result = {"name": "小明", "history": ["A 说了一句话"]}
    print("  node_a 返回：  ", result)
    return result


def node_b(state):
    print("  进入 node_b，看到：", dict(state))
    result = {"name": "小红", "history": ["B 说了一句话"]}
    print("  node_b 返回：  ", result)
    return result


def main():
    graph = StateGraph(State)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)

    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)

    app = graph.compile()

    init = {"name": "无名", "history": ["初始消息"]}
    print("=" * 60)
    print("初始状态：", init)
    print("=" * 60)

    result = app.invoke(init)

    print("=" * 60)
    print("最终状态：", result)
    print("=" * 60)
    print()
    print("对比两个字段的表现：")
    print()
    print("  name（默认规则 = 覆盖）：")
    print("     无名  →  小明  →  小红")
    print("     每一次都被【替换】，只剩最后一个 →", repr(result["name"]))
    print()
    print("  history（自定义规则 = 追加）：")
    print("     ['初始消息']  +  ['A 说了一句话']  +  ['B 说了一句话']")
    print("     每一次都【接在后面】 →", result["history"])
    print()
    print("─" * 60)
    print("这就解释了：为什么对话历史 messages 必须指定合并器")
    print("因为如果默认覆盖，新一轮对话会把前面的历史全部冲掉。")


if __name__ == "__main__":
    main()

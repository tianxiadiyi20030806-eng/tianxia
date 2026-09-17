#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二个 LangGraph —— 验证"状态是怎么累积的"

图的流程：
    START → node_1 → node_2 → node_3 → END

三个节点分别改不同的字段，最后打印每一步的状态，
让你看清"节点拿到的是最新状态"这件事。

【运行】
    cd ~/rag-project
    source .venv/bin/activate
    python3 langgraph_demo2.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    name: str
    score: int


def node_1(state):
    print("  进入 node_1，看到：", dict(state))
    result = {"name": "小明"}                     # 只改 name（覆盖掉"无名"）
    print("  node_1 返回：  ", result)
    return result


def node_2(state):
    print("  进入 node_2，看到：", dict(state))     # ← 注意它看到的 name
    result = {"score": state["score"] + 10}       # 只改 score
    print("  node_2 返回：  ", result)
    return result


def node_3(state):
    print("  进入 node_3，看到：", dict(state))     # ← 注意它看到的 name 已经是"小明"
    result = {"name": state["name"] + "同学"}      # 在最新值的基础上追加
    print("  node_3 返回：  ", result)
    return result


def main():
    graph = StateGraph(State)
    graph.add_node("n1", node_1)
    graph.add_node("n2", node_2)
    graph.add_node("n3", node_3)

    graph.add_edge(START, "n1")
    graph.add_edge("n1", "n2")
    graph.add_edge("n2", "n3")
    graph.add_edge("n3", END)

    app = graph.compile()

    print("=" * 56)
    print("初始状态：{'name': '无名', 'score': 50}")
    print("=" * 56)

    result = app.invoke({"name": "无名", "score": 50})

    print("=" * 56)
    print("最终状态：", result)
    print("=" * 56)
    print()
    print("对照你的预测：")
    print("  name  你猜的是「小明同学无名」，实际是", repr(result["name"]))
    print("  score 你猜的是「60」，实际是", result["score"], "✅")
    print()
    print("关键：node_3 里 state['name'] 已经是 '小明'（node_1 改过的），")
    print("      所以 '小明' + '同学' = '小明同学'，'无名' 早就不在了。")


if __name__ == "__main__":
    main()

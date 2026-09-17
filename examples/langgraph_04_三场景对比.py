#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph 合并规则 —— 三种情况一次跑完

这个文件把三个场景放在一起，跑一次就能全部看到：

    场景 1：不指定合并器   → 默认是【覆盖】
    场景 2：指定 append    → 改成【追加】
    场景 3：节点返回空字典 → 【什么都不改】

【运行】
    cd ~/rag-project
    source .venv/bin/activate
    python3 langgraph_demo4.py
"""

from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


def append_list(old, new):
    """自定义合并器：追加，而不是覆盖"""
    return old + new


def 跑一个图(标题, state类, 节点列表, 边列表, 初始状态):
    """通用的跑图函数，省得重复写"""
    print()
    print("█" * 62)
    print("█ " + 标题)
    print("█" * 62)
    print("初始状态：", 初始状态)

    graph = StateGraph(state类)
    for 名字, 函数 in 节点列表:
        graph.add_node(名字, 函数)
    for 起点, 终点 in 边列表:
        graph.add_edge(起点, 终点)

    app = graph.compile()
    result = app.invoke(初始状态)

    print("─" * 62)
    print("最终状态：", result)
    return result


# ═══════════════════════════════════════════════════════
# 场景 1：不指定合并器 → 默认【覆盖】
# ═══════════════════════════════════════════════════════

class State1(TypedDict):
    name: str


def s1_node_a(state):
    r = {"name": "小明"}
    print("    node_a 返回：", r)
    return r


def s1_node_b(state):
    r = {"name": "小红"}
    print("    node_b 返回：", r)
    return r


# ═══════════════════════════════════════════════════════
# 场景 2：指定 append_list → 【追加】
# ═══════════════════════════════════════════════════════

class State2(TypedDict):
    history: Annotated[list, append_list]


def s2_node_a(state):
    r = {"history": ["A 说了一句话"]}
    print("    node_a 返回：", r)
    return r


def s2_node_b(state):
    r = {"history": ["B 说了一句话"]}
    print("    node_b 返回：", r)
    return r


# ═══════════════════════════════════════════════════════
# 场景 3：节点返回空字典 → 【什么都不改】
# ═══════════════════════════════════════════════════════

class State3(TypedDict):
    name: str
    score: int


def s3_node_a(state):
    r = {"score": 100}
    print("    node_a 返回：", r)
    return r


def s3_node_b(state):
    r = {}                      # ← 空字典 = 不改任何字段
    print("    node_b 返回：", r, "（空字典）")
    return r


def main():
    # 场景 1
    跑一个图(
        "场景 1：不指定合并器 → 默认【覆盖】",
        State1,
        [("a", s1_node_a), ("b", s1_node_b)],
        [(START, "a"), ("a", "b"), ("b", END)],
        {"name": "无名"},
    )
    print()
    print("  说明：name 被改了两次 → 无名 → 小明 → 小红，只剩最后一个")

    # 场景 2
    跑一个图(
        "场景 2：指定 append_list → 【追加】",
        State2,
        [("a", s2_node_a), ("b", s2_node_b)],
        [(START, "a"), ("a", "b"), ("b", END)],
        {"history": ["初始消息"]},
    )
    print()
    print("  说明：history 每次都接在后面，全部保留")

    # 场景 3
    跑一个图(
        "场景 3：节点返回空字典 → 【什么都不改】",
        State3,
        [("a", s3_node_a), ("b", s3_node_b)],
        [(START, "a"), ("a", "b"), ("b", END)],
        {"name": "小明", "score": 50},
    )
    print()
    print("  说明：node_b 返回空字典，所以状态一点没变")

    print()
    print("█" * 62)
    print("█ 总结")
    print("█" * 62)
    print()
    print("  节点返回的字典 = 一张「改动清单」")
    print()
    print("  ┌──────────────────┬──────────────────────────┐")
    print("  │ 清单里写了什么    │ 框架怎么处理              │")
    print("  ├──────────────────┼──────────────────────────┤")
    print("  │ 某个字段有新值    │ 按该字段的合并器合并      │")
    print("  │ 没提某个字段      │ 保持原样，不动            │")
    print("  │ 是个空字典 {}     │ 什么都不改                │")
    print("  └──────────────────┴──────────────────────────┘")
    print()
    print("  而「合并器」决定了「有新值」时是覆盖还是追加：")
    print("    不指定       → 覆盖（新的替换旧的）")
    print("    append_list  → 追加（新的接在后面）")


if __name__ == "__main__":
    main()

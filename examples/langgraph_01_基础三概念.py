#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一个 LangGraph —— 理解 State / Node / Edge 三个概念

【这个例子做什么】

不调用大模型，只搭一个最小的图：
    开始 → 节点A → 节点B → 结束
每个节点往状态里加一句话，最后打印完整结果。

目的是让你看清"图"是怎么跑的，而不是被大模型干扰。

【运行】
    cd ~/rag-project
    source .venv/bin/activate
    python3 langgraph_demo.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

# ═══════════════════════════════════════════════════════
# 一、State（状态）—— 声明"流程里要传递哪些数据"
#
#    对比你的 agent.py：
#        messages = []                 ← 只装对话
#
#    这里用类来声明，LangGraph 才知道有哪些字段
# ═══════════════════════════════════════════════════════

class State(TypedDict):
    log: str          # 用来记录每一步做了什么


# ═══════════════════════════════════════════════════════
# 二、Node（节点）—— 就是函数：接收状态，返回要更新的字段
#
#    ⚠️ 注意：返回的是一个字典，里面只写"我要改哪些字段"
#        不写的字段会保持不变（框架自动帮你合并）
# ═══════════════════════════════════════════════════════

def node_a(state):
    print("  [节点A] 收到 log =", state["log"])
    return {"log": state["log"] + " → 经过A"}


def node_b(state):
    print("  [节点B] 收到 log =", state["log"])
    return {"log": state["log"] + " → 经过B"}


# ═══════════════════════════════════════════════════════
# 三、Edge（边）—— 决定"下一步去哪个节点"
#
#    START / END 是 LangGraph 内置的两个特殊节点
# ═══════════════════════════════════════════════════════

def main():
    # ① 创建图，告诉它用哪个 State
    graph = StateGraph(State)

    # ② 把节点加进去，起个名字
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)

    # ③ 连边：定好执行顺序
    graph.add_edge(START, "a")     # 开始 → A
    graph.add_edge("a", "b")       # A → B
    graph.add_edge("b", END)       # B → 结束

    # ④ 编译成可执行的对象（这一步会检查图有没有问题）
    app = graph.compile()

    # ⑤ 运行：传入初始状态
    print("=" * 50)
    print("开始执行")
    print("=" * 50)

    result = app.invoke({"log": "起点"})

    print("=" * 50)
    print("最终状态：", result)
    print("=" * 50)


if __name__ == "__main__":
    main()

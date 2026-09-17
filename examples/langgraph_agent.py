#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 LangGraph 重写 agent —— 最后一个新概念：条件边

【和你的 agent.py 对照】

    你的 agent.py                        LangGraph 版
    ────────────────────────────────────────────────────
    messages = []                        State 里的 messages 字段
    while True:                          图的循环（自动的，不用你写）
    msg = call_ai(messages)              节点 call_model
    if msg.get("tool_calls"):            ★ 条件边 should_continue
        执行工具                          节点 call_tools
        continue                          一条边指向回 call_model
    else:                                ★ 条件边回到 END
        break

【唯一的两个新东西】

    1. add_conditional_edges —— 条件边：根据函数返回值决定下一步去哪
    2. graph.add_edge("tools", "model") —— 执行完工具，回到模型（形成循环）

【运行】
    cd ~/rag-project
    source .venv/bin/activate
    export DEEPSEEK_API_KEY=sk-你的key
    python3 examples/langgraph_agent.py
"""

import datetime
import json
import os
import urllib.error
import urllib.request
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

# ═══════════════════════════════════════════════════════
# 一、工具（和 agent.py 里一模一样）
# ═══════════════════════════════════════════════════════

def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate(expr):
    allowed = set("0123456789+-*/(). ")
    if not set(expr) <= allowed:
        return "错误：表达式里只能有数字和 + - * / ( )"
    return str(eval(expr, {"__builtins__": {}}, {}))


TOOLS = {
    "get_time": get_time,
    "calculate": calculate,
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前的日期和时间。当用户问现在几点、今天几号时使用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "精确计算数学表达式。任何算术都应该用它，不要自己心算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expr": {"type": "string", "description": "要计算的表达式，例如 1234*5678"}
                },
                "required": ["expr"],
            },
        },
    },
]


# ═══════════════════════════════════════════════════════
# 二、状态
#
#    用【自定义合并器】告诉框架：messages 要"追加"，不要"覆盖"
#    （因为对话历史必须累积）
#
#    实际项目里通常用 LangGraph 内置的 add_messages，
#    这里用自己写的，是为了让你看清"合并器"到底是什么。
# ═══════════════════════════════════════════════════════

def 追加消息(old, new):
    return old + new


class State(TypedDict):
    messages: Annotated[list, 追加消息]


# ═══════════════════════════════════════════════════════
# 三、调用大模型（复用你 agent.py 里的写法）
# ═══════════════════════════════════════════════════════

LLM_URL = "https://api.deepseek.com/chat/completions"


def 调模型(messages):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("请先设置 DEEPSEEK_API_KEY 环境变量")

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "tools": TOOLS_SCHEMA,
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
    return json.loads(raw)["choices"][0]["message"]


# ═══════════════════════════════════════════════════════
# 四、节点（读状态 → 返回补丁）
# ═══════════════════════════════════════════════════════

def node_model(state):
    """节点1：把整段消息发给模型，把它的回复加进状态"""
    print("  [节点] 调用模型...")
    reply = 调模型(state["messages"])

    if reply.get("tool_calls"):
        names = [c["function"]["name"] for c in reply["tool_calls"]]
        print("  [节点] 模型要求调用：", ", ".join(names))
    else:
        print("  [节点] 模型给出了最终回答")

    return {"messages": [reply]}


def node_tools(state):
    """节点2：执行模型要求的工具，把结果加进状态"""
    last = state["messages"][-1]
    results = []

    for call in last["tool_calls"]:
        name = call["function"]["name"]
        args_json = call["function"]["arguments"]

        try:
            args = json.loads(args_json) if args_json else {}
            result = str(TOOLS[name](**args))
        except Exception as e:
            result = "工具执行失败：" + str(e)

        print("  [节点] 执行工具 " + name + " → " + result[:50])

        results.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })

    return {"messages": results}


# ═══════════════════════════════════════════════════════
# 五、★ 条件边 —— 唯一的新概念
#
#    这是一个普通函数：
#        读状态 → 返回一个"字符串标签"
#    框架根据这个标签，决定下一步去哪个节点。
#
#    对比你 agent.py 里的：
#        if msg.get("tool_calls"):  continue     ← 回到循环开头
#        else:                      break        ← 跳出
# ═══════════════════════════════════════════════════════

def 判断下一步(state):
    """返回 'tools' 表示去执行工具；返回 'end' 表示结束"""
    last = state["messages"][-1]
    if last.get("tool_calls"):
        return "tools"
    return "end"


# ═══════════════════════════════════════════════════════
# 六、搭图
# ═══════════════════════════════════════════════════════

def 建图():
    graph = StateGraph(State)

    graph.add_node("model", node_model)
    graph.add_node("tools", node_tools)

    graph.add_edge(START, "model")

    # ★ 条件边：从 model 出来，看判断函数的返回值决定去哪
    graph.add_conditional_edges(
        "model",
        判断下一步,
        {
            "tools": "tools",     # 返回 "tools" → 去 tools 节点
            "end": END,           # 返回 "end"   → 去终点
        },
    )

    # 执行完工具，回到模型（这一步形成循环）
    graph.add_edge("tools", "model")

    return graph.compile()


# ═══════════════════════════════════════════════════════
# 七、主程序
# ═══════════════════════════════════════════════════════

def main():
    app = 建图()

    print("🤖 LangGraph 版 Agent（输入 exit 退出）")
    print("   试试问：现在几点了？")
    print("=" * 56)

    while True:
        question = input("\n👤 你：")
        if question.strip() == "exit":
            print("再见！")
            break
        if not question.strip():
            continue

        print()
        print("  ── 开始执行图 ──")
        result = app.invoke({"messages": [{"role": "user", "content": question}]})
        print("  ── 图执行完毕 ──")

        final = result["messages"][-1]
        print("\n🤖 AI：" + (final.get("content") or "(无回复)"))
        print("   （本次共 " + str(len(result["messages"])) + " 条消息）")


if __name__ == "__main__":
    main()

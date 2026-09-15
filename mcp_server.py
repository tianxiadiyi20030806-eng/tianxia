#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server —— 把本地知识库检索封装成标准 MCP 工具

【什么是 MCP】

MCP（Model Context Protocol）是一个开放协议，让 AI 应用（Claude Desktop、
Cursor、Cline 等）能够调用外部工具和数据源。

它看起来复杂，但拆开只有两样东西：

    传输层：stdio —— 从标准输入读消息，往标准输出写消息
    消息格式：JSON-RPC 2.0

【为什么不用 pip install mcp】

因为协议本身很简单，用 Python 标准库（sys / json）就能实现。
本项目全程零第三方依赖，这也是它的核心特色之一。

【MCP 的三个核心方法】

    initialize    握手 —— 客户端问"你支持什么"，服务器答"我支持这些"
    tools/list    列出 —— 客户端问"你有哪些工具"
    tools/call    调用 —— 客户端说"帮我调用 XX 工具，参数是 YY"

【消息格式（JSON-RPC 2.0）】

客户端发来：
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

服务器回：
    {"jsonrpc": "2.0", "id": 1, "result": {...}}

注意：有些消息没有 id（叫"通知"，notification），服务器不需要回复。

【怎么用】

这个 server 通过 stdio 通信，所以要由 MCP 客户端启动，而不是手动运行。
想手动测试请用：python3 test_mcp.py
"""

import json
import sys

from retrieval import Retriever

# ═══════════════════════════════════════════════════════
# 一、知识库检索器（复用 retrieval.py）
# ═══════════════════════════════════════════════════════

retriever = Retriever()

# ═══════════════════════════════════════════════════════
# 二、工具定义
#
#    这是暴露给 AI 客户端的「工具清单」——
#    和 Function Calling 里的 tools 参数是同一个东西，
#    只是换成了 MCP 的 schema 格式（注意是 inputSchema，不是 parameters）
# ═══════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "在「网络系统管理赛项」知识库中检索相关内容。"
            "知识库包含网络设备配置、Windows Server 与 Linux 服务部署等资料，"
            "共 131 个知识块。当用户询问 DHCP、DNS、VLAN、AD 域、"
            "证书服务等配置方法时使用本工具。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，例如「DHCP中继怎么配」",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回条数，默认 3",
                },
            },
            "required": ["query"],
        },
    },
]


# ═══════════════════════════════════════════════════════
# 三、工具实现
# ═══════════════════════════════════════════════════════

def call_search_knowledge_base(args):
    """执行检索，返回文本结果"""
    query = args.get("query", "")
    top_k = args.get("top_k", 3)

    if not query:
        return "错误：缺少参数 query"

    hits = retriever.search(query, top_k=top_k)

    if not hits:
        return "知识库中没有找到相关内容。"

    lines = []
    for i, (score, cid, item) in enumerate(hits, 1):
        lines.append(
            "【结果" + str(i) + "】 相关度 " + str(round(score, 1))
            + "  来源：块 #" + str(cid)
        )
        if item["path"]:
            lines.append("  章节：" + item["path"])
        lines.append("  " + item["text"].strip().replace("\n", " "))
        lines.append("")

    return "\n".join(lines)


TOOL_HANDLERS = {
    "search_knowledge_base": call_search_knowledge_base,
}


# ═══════════════════════════════════════════════════════
# 四、MCP 协议实现
# ═══════════════════════════════════════════════════════

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "knowledge-base-server", "version": "1.0.0"}


def send(msg):
    """往 stdout 写一条 JSON-RPC 消息（每条一行，这是 stdio 传输的约定）"""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_result(req_id, result):
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def send_error(req_id, code, message):
    send({"jsonrpc": "2.0", "id": req_id,
          "error": {"code": code, "message": message}})


def handle(req):
    """处理一条请求。返回 True 表示继续，False 表示退出"""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    # ── 通知（没有 id）：不需要回复 ──
    if req_id is None:
        return True

    # ── initialize：握手 ──
    if method == "initialize":
        # 客户端会带它支持的协议版本，能对上就回同一个
        client_version = params.get("protocolVersion")
        version = client_version or PROTOCOL_VERSION

        send_result(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {}},     # 声明：我提供 tools 能力
            "serverInfo": SERVER_INFO,
        })

    # ── tools/list：列出所有工具 ──
    elif method == "tools/list":
        send_result(req_id, {"tools": TOOLS})

    # ── tools/call：调用工具 ──
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            send_error(req_id, -32602, "未知工具：" + str(name))
            return True

        try:
            text = handler(args)
            # MCP 规定：工具结果放在 content 数组里
            send_result(req_id, {"content": [{"type": "text", "text": text}]})
        except Exception as e:
            send_result(req_id, {
                "content": [{"type": "text", "text": "工具执行失败：" + str(e)}],
                "isError": True,
            })

    # ── 未知方法 ──
    else:
        send_error(req_id, -32601, "不支持的方法：" + str(method))

    return True


def main():
    """主循环：从 stdin 逐行读请求，处理后写回 stdout"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            # 解析失败时无法得知 id，只能忽略
            continue

        if not handle(req):
            break


if __name__ == "__main__":
    main()

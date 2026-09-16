#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server 最小实现 —— 看懂 MCP 的本质

完整的 mcp_server.py 有 245 行，但剥掉所有细节，核心只有三件事：

    ① 从 stdin 读一行 JSON
    ② 看 method 字段，决定回什么
    ③ 往 stdout 回一行 JSON

其他代码（错误处理、通知跳过、工具分发）都只是细节。

【测试方法】

    echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 mcp_mini.py
"""

import json
import sys

while True:

    # ═══ ① 读一行 ═══
    # MCP 用 stdio 传输：客户端往我们的标准输入写消息，一行一条
    line = sys.stdin.readline()
    if not line:
        break                      # 输入结束（客户端关闭了），退出

    req = json.loads(line)         # JSON 文字 → Python 字典

    method = req.get("method")
    req_id = req.get("id")

    # 没有 id 的是"通知"，按协议不需要回复
    if req_id is None:
        continue

    # ═══ ② 看 method 决定回什么 ═══
    if method == "initialize":
        # 握手：告诉客户端我的协议版本、支持的能力、我是谁
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "mini-server", "version": "1.0"},
        }

    elif method == "tools/list":
        # 列出我有哪些工具
        result = {
            "tools": [
                {
                    "name": "get_time",
                    "description": "获取当前时间",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                },
            ]
        }

    elif method == "tools/call":
        params = req.get("params") or {}
        tool_name = params.get("name")

        if tool_name == "get_time":
            import datetime
            text = "当前时间：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            text = "未知工具：" + str(tool_name)

        # MCP 规定：工具结果放在 content 数组里
        result = {"content": [{"type": "text", "text": text}]}
    # ═══ ③ 回一行 JSON ═══
    # 格式是 JSON-RPC 2.0：jsonrpc / id / result
    # id 必须和请求里的 id 一致，客户端靠它配对
    print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result},
                 ensure_ascii=False))

    # ⚠️ 必须 flush！否则消息会卡在缓冲区里，客户端一直等不到回复
    sys.stdout.flush()

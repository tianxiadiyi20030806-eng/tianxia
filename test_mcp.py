#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server 测试客户端

【为什么需要这个】

MCP Server 是通过 stdio 通信的，正常由 Claude Desktop / Cursor 这类
客户端启动。手动跑它只会看到一个卡住的终端。

所以写一个测试客户端：启动 server → 发请求 → 打印响应，
这样就能验证协议实现是否正确。

【运行】
    python3 test_mcp.py
"""

import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    proc = subprocess.Popen(
        [sys.executable, "mcp_server.py"],
        cwd=BASE,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def send(obj, title):
        print("→ 发送 " + title)
        print("  " + json.dumps(obj, ensure_ascii=False))
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def recv(title):
        line = proc.stdout.readline()
        if not line:
            print("✗ 服务器没有响应（可能崩了）")
            err = proc.stderr.read()
            if err:
                print(err)
            return None
        data = json.loads(line)
        print("← 收到 " + title)
        text = json.dumps(data, ensure_ascii=False)
        print("  " + (text[:400] + " ..." if len(text) > 400 else text))
        print()
        return data

    print("=" * 68)
    print("MCP Server 测试")
    print("=" * 68)
    print()

    # ── 第 1 步：initialize 握手 ──
    send({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }, "initialize（握手）")
    init = recv("initialize 响应")
    if init:
        info = init.get("result", {}).get("serverInfo", {})
        print("  ✅ 握手成功，服务器：" + info.get("name", "?")
              + " v" + info.get("version", "?"))
        print()

    # ── 第 2 步：通知（无需响应）──
    print("→ 发送 notifications/initialized（通知，不需要回复）")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized"
    }) + "\n")
    proc.stdin.flush()
    print()

    # ── 第 3 步：tools/list ──
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
         "tools/list（列出工具）")
    tools = recv("tools/list 响应")
    if tools:
        names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        print("  ✅ 服务器提供 " + str(len(names)) + " 个工具：" + ", ".join(names))
        print()

    # ── 第 4 步：tools/call ──
    send({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {
            "name": "search_knowledge_base",
            "arguments": {"query": "DHCP中继怎么配", "top_k": 2},
        },
    }, "tools/call（调用检索工具）")
    call = recv("tools/call 响应")

    print("=" * 68)
    if call and "result" in call:
        content = call["result"].get("content", [])
        if content:
            print("✅ 检索结果：")
            print()
            print(content[0]["text"])
    else:
        print("❌ 调用失败")

    print("=" * 68)

    proc.stdin.close()
    proc.wait(timeout=5)


if __name__ == "__main__":
    main()

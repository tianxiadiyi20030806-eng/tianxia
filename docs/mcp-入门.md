 # MCP 从零讲透：用 150 行标准库代码理解 Model Context Protocol

> 本文配套代码：[`mcp_server.py`](../mcp_server.py) 与 [`test_mcp.py`](../test_mcp.py)
> 全程只用 Python 标准库，未引入 `mcp` SDK。

---

## 目录

1. [为什么需要 MCP](#一为什么需要-mcp)
2. [MCP 和 Function Calling 的区别](#二mcp-和-function-calling-的区别)
3. [MCP 怎么通信](#三mcp-怎么通信)
4. [一次完整对话的全过程](#四一次完整对话的全过程)
5. [MCP Server 的代码结构](#五mcp-server-的代码结构)
6. [怎么加一个新工具](#六怎么加一个新工具)
7. [面试常见问题与回答](#七面试常见问题与回答)

---

## 一、为什么需要 MCP

### 1.1 一个真实的麻烦

假设你做了一个很好用的知识库检索工具，希望各种 AI 应用都能用上它。

**没有 MCP 的时候：**

```
Claude Desktop 想用  →  你得专门为它写一套对接代码
Cursor 想用          →  再写一套
Cline 想用           →  再写一套
```

**3 个客户端 × 1 个工具 = 3 套对接代码。**

如果工具多了呢？

```
10 个工具 × 10 个客户端 = 100 套对接代码
```

**这就是所谓的 M×N 问题** —— 每多一个工具或客户端，工作量成倍增长。

### 1.2 MCP 的解法：把接口标准化

```
把工具做成「符合 MCP 标准的 Server」
              ↓
任何支持 MCP 的客户端，都能直接调用
              ↓
10 个工具 + 10 个客户端 = 只需各写一次（10 + 10）
```

**从 M×N 变成 M+N。**

### 1.3 类比：插座标准

| | 比喻 |
|---|---|
| **没有 MCP** | 每个电器配一种专用插头，换电器就得换插座 |
| **有 MCP** | 大家都用标准插座，插上就能用 |

**MCP 就是 AI 工具界的"插座标准"。**

MCP 官方文档里那句话说的就是这个意思：**一次开发，多处复用。**

---

## 二、MCP 和 Function Calling 的区别

**这是面试必问题，必须分清。**

### 2.1 它们在不同的层

| | Function Calling | MCP |
|---|---|---|
| **属于哪一层** | **模型的能力** | **应用之间的协议** |
| **解决什么** | 模型如何**表达**"我要调工具" | AI 应用如何**发现和连上**外部工具 |
| **谁定的** | 各模型厂商自己的格式 | 开放的公共协议 |
| **类比** | 你说的**语言** | 电话线的**接口标准** |

### 2.2 完整链路

把它们串起来看：

```
Claude Desktop（MCP 客户端）
      │
      │ ① 通过 MCP 协议问你的 Server：你有哪些工具？
      ▼
你的 mcp_server.py  ──→  返回：search_knowledge_base、get_stats
      │
      │ ② 客户端把工具清单转成模型能理解的格式
      ▼
   大模型
      │
      │ ③ 模型用 Function Calling 决定："我要调 search_knowledge_base"
      ▼
Claude Desktop
      │
      │ ④ 通过 MCP 协议调用你的 Server
      ▼
你的 mcp_server.py  ──→  执行检索，返回结果
```

### 2.3 一句话总结

> **MCP 负责"把工具接进来"，Function Calling 负责"让模型决定用哪个"。**
>
> **MCP 是 Function Calling 的上游。**

---

## 三、MCP 怎么通信

### 3.1 传输层：stdio

**stdio = standard input/output，也就是标准输入输出。**

```
客户端启动你的 mcp_server.py
        ↓
客户端往它的 stdin 写消息
        ↓
它从 stdin 读 → 处理 → 往 stdout 写回复
        ↓
客户端从它的 stdout 读
```

**没有网络、没有端口、没有 HTTP——就是进程间通过管道传文本。**

**为什么用 stdio？**

| 原因 | 说明 |
|---|---|
| 简单 | 不用处理端口、防火墙、网络配置 |
| 安全 | 进程隔离，工具跑在本地 |
| 快 | 进程间通信，没有网络开销 |

> MCP 也支持 HTTP + SSE 模式（用于远程 Server），但 stdio 是最常用的。

### 3.2 消息格式：JSON-RPC 2.0

**JSON-RPC 2.0 是一个很老的、很简单的远程调用格式。规则就三条：**

1. **每条消息是一行 JSON**（不能格式化、不能换行）
2. **必须带 `"jsonrpc": "2.0"`**
3. **请求带 `id`，响应回同一个 `id`**

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
```

### 3.3 三种消息类型

| 类型 | 有 `id` 吗 | 要不要回复 |
|---|---|---|
| **请求**（Request） | ✅ 有 | 必须回 |
| **响应**（Response） | ✅ 回同一个 id | — |
| **通知**（Notification） | ❌ 没有 | **不回复** |

**代码里就是这样区分的：**

```python
if req_id is None:      # 没有 id = 通知，直接跳过，不回复
    return True
```

---

## 四、一次完整对话的全过程

**这是 `test_mcp.py` 跑出来的真实流程，只有四条消息。**

### ① 客户端发起握手

**客户端 → Server：**

```json
{
  "jsonrpc": "2.0", "id": 1, "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1.0"}
  }
}
```

**Server → 客户端：**

```json
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "knowledge-base-server", "version": "1.0.0"}
  }
}
```

**这一步在干什么？**

双方交换"能力清单"：

- 客户端告诉 Server：我支持什么（比如是否支持 roots、sampling）
- Server 告诉客户端：**我提供什么**（这里声明了 `tools`）

**`capabilities` 为什么重要？**

因为 MCP 除了 `tools`，还支持 `prompts`、`resources`、`sampling` 等能力。
客户端需要提前知道 Server 提供什么，才知道后续该问哪些方法。

**你的 Server 只声明了 `tools`，所以客户端只会问 `tools/list`。**

### ② 客户端发一个通知

```json
{"jsonrpc": "2.0", "method": "notifications/initialized"}
```

**注意：没有 `id`。这是"通知"，Server 不需要回复。**

含义是"我准备好了，可以开始干活了"。

### ③ 客户端问有哪些工具

**客户端 → Server：**

```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
```

**Server → 客户端：**

```json
{
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "tools": [
      {
        "name": "search_knowledge_base",
        "description": "在「网络系统管理赛项」知识库中检索相关内容...",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "检索关键词"},
            "top_k": {"type": "integer", "description": "返回条数"}
          },
          "required": ["query"]
        }
      },
      {
        "name": "get_stats",
        "description": "获取知识库的统计信息...",
        "inputSchema": {"type": "object", "properties": {}}
      }
    ]
  }
}
```

**注意两个细节：**

1. **字段叫 `inputSchema`**，不是 OpenAI Function Calling 里的 `parameters`
2. **`description` 极其重要** —— 客户端会把它转给模型，**模型靠这段描述决定要不要用这个工具**

### ④ 客户端调用工具

**客户端 → Server：**

```json
{
  "jsonrpc": "2.0", "id": 3, "method": "tools/call",
  "params": {
    "name": "search_knowledge_base",
    "arguments": {"query": "DHCP中继怎么配", "top_k": 2}
  }
}
```

**Server → 客户端：**

```json
{
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [
      {"type": "text", "text": "【结果1】 相关度 84.2  来源：块 #20\n..."}
    ]
  }
}
```

**注意返回格式：结果必须放在 `content` 数组里。**

而且 `content` 是个数组，意味着**可以返回多条内容**（比如一条文字 + 一张图片）。

### 完整流程图

```
客户端                          你的 Server
  │                                │
  │──── initialize ───────────────>│   ① 握手，交换能力
  │<─── capabilities + serverInfo ─│
  │                                │
  │──── notifications/initialized ─>│   ② 通知（无需回复）
  │                                │
  │──── tools/list ───────────────>│   ③ 问有哪些工具
  │<─── tools: [两个工具] ──────────│
  │                                │
  │──── tools/call ───────────────>│   ④ 调用工具
  │<─── content: [结果] ────────────│
```

**整个 MCP 协议，就这四条消息。**

---

## 五、MCP Server 的代码结构

### 5.1 用「工具箱」来理解

**你的 `mcp_server.py` 就是一个工具箱。**

| 文件里的部分 | 比喻 |
|---|---|
| `TOOLS = [...]` | **贴在每个工具上的标签**（叫什么、干什么、怎么用） |
| `call_xxx(args)` 函数 | **工具本身**（真正干活的代码） |
| `TOOL_HANDLERS = {...}` | **工具箱的索引**（按名字找到对应工具） |
| `handle(req)` | **工具箱的接待员**（接收请求，分发到对应工具） |
| `main()` | **工具箱的门**（不停从 stdin 读请求） |

### 5.2 代码结构总览

```python
# ─── 第一部分：检索器 ───
retriever = Retriever()          # 复用 retrieval.py 的检索能力

# ─── 第二部分：工具标签 ───  ★ 加工具第 ① 处
TOOLS = [ {...}, {...} ]

# ─── 第三部分：工具本体 ───  ★ 加工具第 ② 处
def call_search_knowledge_base(args): ...
def call_get_stats(args): ...

TOOL_HANDLERS = {...}            # ★ 加工具第 ③ 处

# ─── 第四部分：MCP 协议 ───
def send(msg): ...               # 往 stdout 写一行 JSON
def handle(req): ...             # 处理 initialize / tools/list / tools/call
def main(): ...                  # 主循环
```

**真正跟"协议"有关的代码只有 `send` / `handle` / `main` 三个函数，
加起来不到 60 行。**

---

## 六、怎么加一个新工具

**记住——永远改三个地方。**

### 第 ① 处：写标签（加进 `TOOLS`）

```python
{
    "name": "get_stats",
    "description": "获取知识库的统计信息，包括知识块数量、总字数、平均块长。",
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
},
```

**三个字段的含义：**

| 字段 | 作用 | 注意 |
|---|---|---|
| `name` | 工具名 | 客户端调用时用它 |
| `description` | **给模型看的说明** | **最重要**——模型靠它决定要不要用这个工具 |
| `inputSchema` | 参数定义（JSON Schema） | 无参数就写 `{"type": "object", "properties": {}}` |

### 第 ② 处：造工具（写处理函数）

```python
def call_get_stats(args):
    """返回知识库统计信息"""
    n = len(retriever)
    total = sum(len(item["text"]) for item in retriever.index)
    return "知识块数量：" + str(n) + "  平均块长：" + str(total // n) + " 字"
```

**约定：输入是参数字典，输出是字符串。**

### 第 ③ 处：放进工具箱（注册）

```python
TOOL_HANDLERS = {
    "search_knowledge_base": call_search_knowledge_base,
    "get_stats": call_get_stats,          # ← 加这一行
}
```

### 这个模式和 Function Calling 完全一样

**回想你在 `agent.py` 里加 `read_file` 工具时：**

| | Function Calling（agent.py） | MCP（mcp_server.py） |
|---|---|---|
| 写标签 | `TOOLS_SCHEMA` | `TOOLS` |
| 造工具 | `def read_file(path)` | `def call_xxx(args)` |
| 注册 | `TOOLS = {...}` | `TOOL_HANDLERS = {...}` |

**同一个模式，换了个协议。**

---

## 七、面试常见问题与回答

### Q1：MCP 是什么？

> MCP（Model Context Protocol）是让 AI 应用调用外部工具和数据源的开放协议。
> 它把工具的实现和 AI 应用解耦，做到"一次开发，多处复用"。

### Q2：为什么需要 MCP？不用行不行？

> 不用的话会变成 M×N 问题：N 个 AI 应用要对接 M 个工具，就得写 N×M 套代码。
> 有了 MCP，客户端和工具各自实现一次协议就行，变成 M+N。

### Q3：MCP 和 Function Calling 什么关系？

> 它们在不同层。Function Calling 是模型能力，解决"模型怎么表达我要调工具"；
> MCP 是应用协议，解决"AI 应用怎么发现和调用外部工具"。
> MCP 是上游——MCP 把工具接进来，转成工具定义给模型，模型再用 Function Calling 决定调哪个。

### Q4：MCP 怎么传输？

> 最常用的是 stdio——客户端启动 Server 进程，通过标准输入输出传消息。
> 消息格式是 JSON-RPC 2.0，一行一条。也支持 HTTP + SSE 用于远程 Server。

### Q5：MCP 有哪几个核心方法？

> 三个：`initialize` 握手并交换能力、`tools/list` 列出工具、
> `tools/call` 调用工具。另外还有 `notifications/initialized` 这类通知，不需要回复。

### Q6：你写过 MCP Server 吗？

> 写过。我用 Python 标准库从零实现了一个，没有用 `mcp` SDK。
> 实现了 `initialize` / `tools/list` / `tools/call` 三个方法，
> 把自研的知识库检索暴露成 MCP 工具，可以被 Claude Desktop、Cursor 等客户端调用。
>
> 因为不用 SDK，我对协议细节比较清楚——比如 `inputSchema` 和 Function Calling
> 的 `parameters` 字段名不同，工具结果要放在 `content` 数组里，
> 还有通知消息没有 `id`、服务端不能回复。

---

## 附：为什么可以不用 SDK

**因为 MCP 的协议层非常简单：**

| 组成 | 复杂度 |
|---|---|
| 传输 | `sys.stdin` / `sys.stdout`，一行一条消息 |
| 格式 | `json.dumps` / `json.loads` |
| 方法 | 只有 3 个 |

**SDK 的价值在于**：类型提示、连接管理、多种传输方式（HTTP/SSE）、
自动重连、OAuth 等生产级功能。

**但协议本身的核心，用标准库 150 行就够了。**

**理解协议之后再去看 SDK，会非常清楚它在替你做什么。**

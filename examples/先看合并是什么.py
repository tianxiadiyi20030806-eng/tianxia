#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
先别看 LangGraph —— 用纯 Python 理解"合并"到底是什么

LangGraph 的"状态合并"听起来很玄，但它干的其实就是一行代码：

    state.update(补丁)

Python 字典自带的 update 方法，就是"合并"。

这个文件完全不用 LangGraph，只用你最熟悉的字典和函数。

【运行】
    python3 examples/合并是什么.py
"""

print("=" * 60)
print("第一部分：什么是「合并」")
print("=" * 60)
print()

# ── ① 状态就是一个字典 ──
state = {"name": "无名", "score": 50}
print("① 初始状态：", state)
print()

# ── ② 节点A 返回一个"补丁" ──
patch_a = {"name": "小明"}
print("② 节点A 的补丁：", patch_a)
print("   （它只说了一件事：name 要改成小明）")
print()

# ── ③ 合并 ──
state.update(patch_a)
print("③ 合并后：", state)
print("   ↑ name 变成了「小明」")
print("   ↑ score 还是 50 —— 因为补丁里没提它")
print()

# ── ④ 节点B 的补丁 ──
patch_b = {"score": state["score"] + 10}
print("④ 节点B 的补丁：", patch_b)
print("   （它拿到的是合并后的状态，所以 score 是 50，加 10 = 60）")
print()

state.update(patch_b)
print("⑤ 合并后：", state)
print("   ↑ score 变成 60")
print("   ↑ name 还是「小明」—— 补丁里没提它")
print()

print("-" * 60)
print("所以「覆盖」是怎么来的？")
print()
print("    Python 字典的 update 规则就是：")
print("        同名的 key → 新值【覆盖】旧值")
print("        没提到的 key → 保持不变")
print()
print("    LangGraph 合并状态，用的就是同一个规则。")
print("-" * 60)
print()
print()

print("=" * 60)
print("第二部分：如果不想覆盖，想「追加」呢？")
print("=" * 60)
print()

# ── 换一个状态 ──
state2 = {"history": ["初始消息"]}
print("① 初始状态：", state2)
print()


# ── 自己写一个"合并函数" ──
def 追加(old, new):
    """合并规则：把新值接在旧值后面，而不是覆盖"""
    return old + new


print("② 我们写一个合并函数：")
print("       def 追加(old, new):")
print("           return old + new")
print()

# ── 手动用这个规则合并 ──
state2["history"] = 追加(state2["history"], ["A 说了一句话"])
print("③ 用「追加」规则合并 A 的补丁：", state2)
print()

state2["history"] = 追加(state2["history"], ["B 说了一句话"])
print("④ 再用「追加」规则合并 B 的补丁：", state2)
print("   ↑ 注意：旧的没被冲掉，全都在")
print()
print()

print("=" * 60)
print("总结")
print("=" * 60)
print()
print("  合并 = 把「补丁」应用到「状态」上")
print()
print("  ┌────────────────────┬────────────────────────┐")
print("  │ 用什么规则合并      │ 结果                    │")
print("  ├────────────────────┼────────────────────────┤")
print("  │ state.update(补丁) │ 覆盖（字典的默认行为）    │")
print("  │ 追加(旧, 新)       │ 追加（自己写的规则）      │")
print("  └────────────────────┴────────────────────────┘")
print()
print("  LangGraph 里，你说「这个字段用哪个规则」，")
print("  它就自动帮你做上面这件事——不用你手写 state.update()。")
print()
print("  就这么点东西。")
print()

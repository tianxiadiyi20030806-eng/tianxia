#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检索效果评测 —— Top-1 / Top-3 召回率

【为什么要做这个】

简历上写「实现了 TF-IDF 检索」，面试官一定会问：
    "你怎么知道检索准不准？"

没有数字，这个问题就答不上来。

【方法】

两组测试集，对比「直接提问」和「改写提问」的表现：

  A 组：直接提问 —— 问题里出现原文术语（如"DHCP中继怎么配"）
  B 组：改写提问 —— 用同义表达，不出现原文术语（如"怎么让客户端自动获取IP"）

每组每题标注「正确答案应包含的关键词」，
检索 Top-3 里只要有一块包含该关键词就算命中。

【运行】
    python3 eval_retrieval.py
"""

from retrieval import Retriever

# ═══════════════════════════════════════════════════════
# A 组：直接提问（问题里用了原文术语）
# ═══════════════════════════════════════════════════════
SET_DIRECT = [
    ("DHCP中继怎么配",          ["DHCP中继"]),
    ("VLAN修剪怎么做",          ["VLAN 修剪"]),
    ("WSUS更新服务怎么配",       ["WSUS更新服务"]),
    ("软RAID5怎么配置",         ["RAID5"]),
    ("活动目录域服务怎么部署",    ["活动目录域服务"]),
    ("证书颁发机构怎么配置",      ["证书颁发机构"]),
    ("Windows防火墙怎么设置",    ["Windows防火墙"]),
    ("SDN流表怎么下发",         ["流表"]),
    ("NAT怎么配置",             ["NAT 配置"]),
    ("漫游配置文件放在哪",       ["漫游"]),
    ("DHCP作用域怎么创建",      ["作用域"]),
    ("LDAP怎么配置",            ["LDAP"]),
    ("squid代理怎么安装",       ["squid"]),
    ("NFS共享怎么配置",         ["NFS"]),
    ("chrony时间同步怎么配",     ["chrony"]),
    ("组策略怎么配置",           ["组策略"]),
    ("VRRP的虚拟IP是多少",      ["193.1.10.254"]),
    ("OSPF进程号是多少",        ["OSPF"]),
    ("DFS分布式文件系统怎么用",   ["DFS"]),
    ("SAMBA怎么配置共享",       ["SAMBA"]),
]

# ═══════════════════════════════════════════════════════
# B 组：改写提问（同义表达，不出现原文术语）
# ═══════════════════════════════════════════════════════
SET_PARAPHRASE = [
    ("怎么让客户端自动获取IP地址",    ["DHCP"]),
    ("怎么防止网络出现环路",          ["MSTP", "环路"]),
    ("怎么给两块磁盘做冗余",          ["RAID"]),
    ("怎么限制员工上班时间玩游戏",     ["P2P"]),
    ("怎么统一设置部门电脑的桌面",     ["组策略", "桌面"]),
    ("怎么自动给电脑打系统补丁",       ["WSUS"]),
    ("怎么让外网能访问内网服务",       ["NAT", "网络地址转换"]),
    ("怎么共享文件夹给同部门同事",     ["共享", "文件夹"]),
]


def first_hit(results, keywords):
    """返回命中的名次（1/2/3），没命中返回 None"""
    for rank, (score, cid, item) in enumerate(results, 1):
        for kw in keywords:
            if kw in item["text"]:
                return rank
    return None


def run_set(r, name, tests):
    print()
    print("=" * 68)
    print(name + "（" + str(len(tests)) + " 题）")
    print("=" * 68)

    t1 = t3 = 0
    fails = []

    for q, kws in tests:
        rank = first_hit(r.search(q, top_k=3), kws)

        if rank == 1:
            t1 += 1
            t3 += 1
            mark = "✅ Top-1"
        elif rank in (2, 3):
            t3 += 1
            mark = "🟡 Top-" + str(rank)
        else:
            mark = "❌ 未命中"
            fails.append(q)

        print(f"  {mark:<10} {q}")

    n = len(tests)
    print()
    print(f"  Top-1 命中率：{t1}/{n} = {t1 / n * 100:.0f}%")
    print(f"  Top-3 命中率：{t3}/{n} = {t3 / n * 100:.0f}%")

    return t1, t3, n, fails


def main():
    r = Retriever()
    print("=" * 68)
    print("检索效果评测")
    print("  知识库：" + str(len(r)) + " 个知识块")
    print("=" * 68)

    a1, a3, an, afail = run_set(r, "A 组：直接提问（使用原文术语）", SET_DIRECT)
    b1, b3, bn, bfail = run_set(r, "B 组：改写提问（同义表达）", SET_PARAPHRASE)

    print()
    print("=" * 68)
    print("汇总")
    print("=" * 68)
    print(f"  直接提问   Top-1 {a1 / an * 100:.0f}%   Top-3 {a3 / an * 100:.0f}%")
    print(f"  改写提问   Top-1 {b1 / bn * 100:.0f}%   Top-3 {b3 / bn * 100:.0f}%")

    if bfail:
        print()
        print("  改写提问未命中的问题（暴露关键词检索的固有短板）：")
        for q in bfail:
            print("    · " + q)

    print()
    print("─" * 68)
    print("可直接写进简历：")
    print(f"  构建 {an + bn} 题人工标注测试集，直接提问 Top-3 召回率 "
          f"{a3 / an * 100:.0f}%，并定位出改写提问场景下的检索短板")
    print("─" * 68)


if __name__ == "__main__":
    main()

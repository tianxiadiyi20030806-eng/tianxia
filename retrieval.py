#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检索模块 —— 中文分词 + 建索引 + TF-IDF 检索

单独抽出来的原因：
    rag.py（问答）和 eval_retrieval.py（评测）都要用检索功能。
    如果代码写在 rag.py 里，评测脚本一 import 就会触发它的 API key 检查。
    所以把「检索」和「问答」分开成两个模块。

依赖：仅 Python 标准库
"""

import json
import os

# ═══════════════════════════════════════════════════════
# 一、中文分词
# ═══════════════════════════════════════════════════════

def char_type(ch):
    """判断单个字符的类型：cn（中文）/ ascii（字母数字点）/ other（其他）"""
    if '\u4e00' <= ch <= '\u9fff':
        return "cn"
    if ch.isascii() and (ch.isalnum() or ch == "."):
        return "ascii"
    return "other"


def group_by_type(text):
    """把文本按字符类型分组，返回 [(类型, 内容), ...]"""
    groups = []
    cur = ""
    cur_type = None

    for ch in text:
        t = char_type(ch)

        if t == "other":
            if cur:
                groups.append((cur_type, cur))
            cur = ""
            cur_type = None
            continue

        if t != cur_type:
            if cur:
                groups.append((cur_type, cur))
            cur = ch
            cur_type = t
        else:
            cur += ch

    if cur:
        groups.append((cur_type, cur))

    return groups


def cut_cn(s):
    """中文段切分：相邻两字组成一个词（bigram）"""
    words = []
    prev = None
    for ch in s:
        if prev is not None:
            words.append(prev + ch)
        prev = ch
    return words


def tokenize(text):
    """把文本切成词列表"""
    result = []
    for t, g in group_by_type(text):
        if t == "ascii":
            result.append(g)
        else:
            if len(g) == 1:
                result.append(g)
            else:
                for w in cut_cn(g):
                    result.append(w)
    return result


# ═══════════════════════════════════════════════════════
# 二、建索引
# ═══════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.json")


def build_index(path=None):
    """读入知识块并建索引，返回 (index, df)"""
    if path is None:
        path = CHUNKS_PATH

    chunks = json.load(open(path, encoding="utf-8"))

    index = []
    for c in chunks:
        index.append({
            "id": c["id"],
            "path": c["path"],
            "text": c["text"],
            "words": tokenize(c["text"]),
        })

    # 统计：每个词出现在多少个块里
    df = {}
    for item in index:
        for w in set(item["words"]):
            df[w] = df.get(w, 0) + 1

    return index, df


def make_weight_func(index, df):
    """返回一个权重函数：词越稀有，权重越高（IDF）"""
    n = len(index)

    def weight(w):
        if w not in df:
            return 0.0
        return n / df[w]

    return weight


# ═══════════════════════════════════════════════════════
# 三、检索
# ═══════════════════════════════════════════════════════

def search(query, index, weight, top_k=3):
    """TF-IDF 加权关键词检索，返回 [(分数, id, item), ...]"""
    qwords = tokenize(query)

    results = []
    for item in index:
        s = 0.0
        for w in qwords:
            if w in item["words"]:
                s += weight(w)
        results.append((s, item["id"], item))

    results.sort(reverse=True)
    return results[:top_k]


# ═══════════════════════════════════════════════════════
# 四、便捷入口：一次拿到可用的检索器
# ═══════════════════════════════════════════════════════

class Retriever:
    """检索器：建一次索引，反复查询"""

    def __init__(self, path=None):
        self.index, self.df = build_index(path)
        self.weight = make_weight_func(self.index, self.df)

    def search(self, query, top_k=3):
        return search(query, self.index, self.weight, top_k)

    def __len__(self):
        return len(self.index)

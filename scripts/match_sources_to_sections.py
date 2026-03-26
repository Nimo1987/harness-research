#!/usr/bin/env python3
"""
章节信源匹配脚本 v5.2
在章节写作前，预筛选与每个章节最相关的信源，减少 LLM prompt 长度。

用法：
  python match_sources_to_sections.py \
    --plan research_plan.json \
    --sources filtered_sources.json \
    --output sources/section_source_map.json

逻辑：
  1. 从每个 section 的 title + purpose 提取关键词集合
  2. 从每条 source 的 title + snippet + key_facts 提取关键词集合
  3. 计算 Jaccard 相似度 + TF-IDF 余弦相似度
  4. 每个 section 取 top-K 最相关信源（K = min(15, total/sections)）
  5. 确保每条信源至少被分配到 1 个 section（不丢弃）
"""

import argparse
import json
import math
import re
from collections import Counter


def safe_load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return default
        data = json.loads(content)
        return data if data is not None else default
    except (json.JSONDecodeError, FileNotFoundError):
        return default


def tokenize(text):
    """简单分词：中文按字切分，英文按词切分，去除停用词和短词"""
    if not text or not isinstance(text, str):
        return []

    # 英文：按非字母数字分割
    en_tokens = re.findall(r"[a-zA-Z]{2,}", text.lower())

    # 中文：按 2-gram 切分
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    cn_tokens = []
    for i in range(len(cn_chars) - 1):
        cn_tokens.append(cn_chars[i] + cn_chars[i + 1])

    # 数字保留（可能是年份、百分比等重要数据）
    num_tokens = re.findall(r"\d+\.?\d*%?", text)

    # 英文停用词
    stop_words = {
        "the",
        "is",
        "at",
        "of",
        "on",
        "and",
        "or",
        "to",
        "in",
        "for",
        "by",
        "an",
        "be",
        "as",
        "it",
        "its",
        "was",
        "are",
        "has",
        "have",
        "had",
        "this",
        "that",
        "with",
        "from",
        "not",
        "but",
        "can",
        "will",
        "may",
        "all",
        "any",
        "each",
        "more",
        "also",
        "than",
        "very",
        "about",
    }

    filtered_en = [t for t in en_tokens if t not in stop_words and len(t) > 1]

    return filtered_en + cn_tokens + num_tokens


def extract_source_text(source):
    """从信源中提取用于匹配的文本"""
    parts = []
    for field in ["title", "snippet", "description"]:
        val = source.get(field, "")
        if val and isinstance(val, str):
            parts.append(val)

    # key_facts
    facts = source.get("key_facts", [])
    if isinstance(facts, list):
        for f in facts:
            if isinstance(f, str):
                parts.append(f)

    return " ".join(parts)


def jaccard_similarity(set_a, set_b):
    """计算 Jaccard 相似度"""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def tfidf_cosine(tokens_a, tokens_b, idf_map):
    """计算基于 TF-IDF 的余弦相似度"""
    if not tokens_a or not tokens_b:
        return 0.0

    # TF
    tf_a = Counter(tokens_a)
    tf_b = Counter(tokens_b)

    # TF-IDF 向量
    all_terms = set(tf_a.keys()) | set(tf_b.keys())
    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for term in all_terms:
        idf = idf_map.get(term, 1.0)
        va = tf_a.get(term, 0) * idf
        vb = tf_b.get(term, 0) * idf
        dot_product += va * vb
        norm_a += va * va
        norm_b += vb * vb

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))


def main():
    parser = argparse.ArgumentParser(description="章节信源匹配 v5.2")
    parser.add_argument("--plan", required=True, help="研究计划 JSON")
    parser.add_argument("--sources", required=True, help="过滤后信源 JSON")
    parser.add_argument("--output", required=True, help="输出匹配映射 JSON")
    args = parser.parse_args()

    plan = safe_load_json(args.plan, {})
    sources = safe_load_json(args.sources, [])

    if not isinstance(sources, list):
        sources = []

    sections = plan.get("sections", [])
    if not sections:
        print("[MATCH-SOURCES] 警告：研究计划中没有章节定义")
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print(f"[MATCH-SOURCES] 输出 → {args.output}")
        return

    total_sources = len(sources)
    num_sections = len(sections)
    k = min(15, max(5, total_sources // max(num_sections, 1)))

    print(f"[MATCH-SOURCES] v5.2 章节信源预匹配")
    print(f"[MATCH-SOURCES] 章节: {num_sections}, 信源: {total_sources}, K={k}")

    # 1. 为所有文档分词
    section_tokens = {}
    for sec in sections:
        title = sec.get("title", "")
        purpose = sec.get("purpose", "")
        tokens = tokenize(f"{title} {purpose}")
        section_tokens[title] = tokens

    source_tokens = {}
    source_urls = []
    for src in sources:
        url = src.get("url", "")
        if not url:
            continue
        text = extract_source_text(src)
        tokens = tokenize(text)
        source_tokens[url] = tokens
        source_urls.append(url)

    # 2. 计算 IDF
    all_docs = list(section_tokens.values()) + list(source_tokens.values())
    n_docs = len(all_docs)
    doc_freq = Counter()
    for doc_tokens in all_docs:
        unique_tokens = set(doc_tokens)
        for token in unique_tokens:
            doc_freq[token] += 1

    idf_map = {}
    for token, freq in doc_freq.items():
        idf_map[token] = math.log((n_docs + 1) / (freq + 1)) + 1

    # 3. 为每个章节计算与所有信源的相似度，取 top-K
    result = {}
    assigned_sources = set()

    for sec in sections:
        title = sec.get("title", "")
        sec_toks = section_tokens.get(title, [])
        sec_set = set(sec_toks)

        scores = []
        for url in source_urls:
            src_toks = source_tokens.get(url, [])
            src_set = set(src_toks)

            # 综合评分: 0.4 * Jaccard + 0.6 * TF-IDF cosine
            j_score = jaccard_similarity(sec_set, src_set)
            t_score = tfidf_cosine(sec_toks, src_toks, idf_map)
            combined = 0.4 * j_score + 0.6 * t_score
            scores.append((url, combined))

        # 按分数排序，取 top-K
        scores.sort(key=lambda x: -x[1])
        top_urls = [url for url, score in scores[:k]]
        result[title] = top_urls
        assigned_sources.update(top_urls)

    # 4. 确保每条信源至少被分配到 1 个 section
    unassigned = [url for url in source_urls if url not in assigned_sources]
    if unassigned:
        result["_unassigned"] = unassigned
        print(
            f"[MATCH-SOURCES] 未匹配信源: {len(unassigned)} 条（将添加到 _unassigned）"
        )

    # 保存结果
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_assigned = sum(len(v) for k, v in result.items() if k != "_unassigned")
    print(
        f"[MATCH-SOURCES] 完成: {num_sections} 章节, 共分配 {total_assigned} 条信源引用"
    )
    print(f"[MATCH-SOURCES] 输出 → {args.output}")


if __name__ == "__main__":
    main()

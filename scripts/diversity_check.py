#!/usr/bin/env python3
"""
信息茧房/多样性检测脚本 (v5.0 新增)

检测 5 个维度的多样性：
  1. 语言多样性 — 信源语言分布的 Shannon 熵
  2. 信源类型多样性 — 政府/学术/媒体/行业/社交分布熵
  3. 观点方向性 — key_facts 正面/负面/中性比例偏离度
  4. 地域多样性 — 信源域名国家/地区分布熵
  5. 时间分布 — 信源发布时间的标准差

低于阈值自动生成补充搜索建议。

用法：
  python diversity_check.py \
    --sources filtered_sources.json \
    --config config.yaml \
    --output diversity_report.json
"""

import argparse
import json
import math
import re
from collections import Counter
from urllib.parse import urlparse

import yaml


def shannon_entropy(counts: dict) -> float:
    """计算 Shannon 熵（归一化到 0-1）"""
    total = sum(counts.values())
    if total == 0 or len(counts) <= 1:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    # 归一化：除以 log2(类别数)
    max_entropy = math.log2(len(counts))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def detect_language(text: str) -> str:
    """简单的语言检测（基于字符特征）"""
    if not text:
        return "unknown"
    # 统计各类字符比例
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    ja = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text))
    ko = len(re.findall(r"[\uac00-\ud7af\u1100-\u11ff]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    cyrillic = len(re.findall(r"[\u0400-\u04ff]", text))
    arabic = len(re.findall(r"[\u0600-\u06ff]", text))

    total = cjk + ja + ko + latin + cyrillic + arabic
    if total == 0:
        return "unknown"

    scores = {
        "zh": cjk / total if cjk > 0 else 0,
        "ja": ja / total if ja > 0 else 0,
        "ko": ko / total if ko > 0 else 0,
        "en": latin / total if latin > 0 else 0,
        "ru": cyrillic / total if cyrillic > 0 else 0,
        "ar": arabic / total if arabic > 0 else 0,
    }

    # 中文 vs 日文消歧：有平假名/片假名则日文
    if cjk > 0 and ja > 0:
        scores["ja"] += scores["zh"] * 0.5

    best = max(scores, key=scores.get)
    return best if scores[best] > 0.1 else "other"


def detect_geo_from_domain(url: str) -> str:
    """从域名 TLD 推断地域"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
    except Exception:
        return "unknown"

    tld_map = {
        ".cn": "CN",
        ".com.cn": "CN",
        ".gov.cn": "CN",
        ".edu.cn": "CN",
        ".jp": "JP",
        ".go.jp": "JP",
        ".co.jp": "JP",
        ".ac.jp": "JP",
        ".kr": "KR",
        ".go.kr": "KR",
        ".co.kr": "KR",
        ".uk": "UK",
        ".gov.uk": "UK",
        ".co.uk": "UK",
        ".ac.uk": "UK",
        ".de": "DE",
        ".fr": "FR",
        ".it": "IT",
        ".es": "ES",
        ".au": "AU",
        ".gov.au": "AU",
        ".in": "IN",
        ".gov.in": "IN",
        ".br": "BR",
        ".gov.br": "BR",
        ".ru": "RU",
        ".gov.ru": "RU",
        ".sg": "SG",
        ".gov.sg": "SG",
        ".eu": "EU",
        ".europa.eu": "EU",
        ".gov": "US",
    }

    # 按长度降序匹配（避免 .cn 误匹配 .com.cn）
    for tld, geo in sorted(tld_map.items(), key=lambda x: -len(x[0])):
        if domain.endswith(tld):
            return geo

    # .com/.org/.net 等通用 TLD
    if domain.endswith((".com", ".org", ".net", ".io")):
        return "INTL"

    return "other"


def classify_source_type(source: dict) -> str:
    """分类信源类型"""
    tier = source.get("tier", 4)
    if tier == 0:
        return "government_data"
    elif tier == 1:
        url = source.get("url", "").lower()
        if any(
            kw in url
            for kw in [
                ".edu",
                ".ac.",
                "arxiv",
                "pubmed",
                "scholar",
                "nature.com",
                "science.org",
            ]
        ):
            return "academic"
        return "government"
    elif tier == 2:
        return "professional"
    elif tier == 3:
        return "news"
    elif tier == 5:
        return "social"
    return "general"


def analyze_sentiment_direction(sources: list) -> dict:
    """
    分析 key_facts 的情感方向
    返回: {"positive": count, "negative": count, "neutral": count}
    """
    # 正面/负面关键词（中英文）
    positive_words = re.compile(
        r"增长|增加|上升|突破|创新|领先|稳健|强劲|超预期|增速|利好|"
        r"growth|increase|rise|breakthrough|leading|strong|exceed|accelerat",
        re.IGNORECASE,
    )
    negative_words = re.compile(
        r"下降|下滑|减少|萎缩|风险|亏损|困难|挑战|低迷|压力|利空|危机|"
        r"decline|decrease|fall|risk|loss|challeng|weak|crisis|slow|shrink",
        re.IGNORECASE,
    )

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for source in sources:
        facts = source.get("key_facts", [])
        if not facts:
            content = source.get("content", "") + " " + source.get("title", "")
            facts = [content]

        for fact in facts:
            if not isinstance(fact, str):
                continue
            pos = len(positive_words.findall(fact))
            neg = len(negative_words.findall(fact))
            if pos > neg:
                counts["positive"] += 1
            elif neg > pos:
                counts["negative"] += 1
            else:
                counts["neutral"] += 1

    return counts


def generate_suggestions(scores: dict, warnings: list, sources: list) -> list:
    """生成补充搜索建议"""
    suggestions = []

    if scores.get("language", 1.0) < 0.3:
        # 检测当前主要语言，建议搜索其他语言
        lang_dist = Counter()
        for s in sources:
            lang = detect_language(s.get("title", "") + s.get("content", ""))
            lang_dist[lang] += 1
        dominant = lang_dist.most_common(1)[0][0] if lang_dist else "zh"
        if dominant in ("zh", "en"):
            suggestions.extend(
                [
                    f"补充日语搜索: <topic> 市場規模",
                    f"补充韩语搜索: <topic> 시장 규모",
                ]
            )
        if dominant == "zh":
            suggestions.append("补充英语搜索: <topic> market analysis")
        elif dominant == "en":
            suggestions.append("补充中文搜索: <topic> 市场分析")

    if scores.get("type", 1.0) < 0.5:
        # 缺少的信源类型
        type_dist = Counter(classify_source_type(s) for s in sources)
        missing_types = {
            "government_data",
            "academic",
            "professional",
            "news",
            "social",
        } - set(type_dist.keys())
        for mt in missing_types:
            type_search_map = {
                "government_data": "site:gov.cn OR site:.gov <topic>",
                "academic": "site:arxiv.org OR site:scholar.google.com <topic>",
                "professional": "site:mckinsey.com OR site:bcg.com <topic>",
                "news": "site:reuters.com OR site:bbc.com <topic>",
                "social": "site:zhihu.com OR site:reddit.com <topic>",
            }
            if mt in type_search_map:
                suggestions.append(f"补充{mt}搜索: {type_search_map[mt]}")

    if scores.get("sentiment", 1.0) < 0.3:
        suggestions.extend(
            [
                "<topic> criticism 争议 问题",
                "<topic> risk 风险 挑战",
                "<topic> failure 失败案例",
            ]
        )

    if scores.get("geo", 1.0) < 0.3:
        geo_dist = Counter(detect_geo_from_domain(s.get("url", "")) for s in sources)
        dominant = geo_dist.most_common(1)[0][0] if geo_dist else "CN"
        if dominant in ("CN", "INTL"):
            suggestions.append("补充欧洲视角: <topic> EU policy regulation")
            suggestions.append("补充东南亚视角: <topic> ASEAN Southeast Asia")

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="信息茧房/多样性检测 (v5.0)")
    parser.add_argument("--sources", required=True, help="过滤后的信源 JSON")
    parser.add_argument("--config", required=True, help="config.yaml")
    parser.add_argument("--output", required=True, help="输出多样性报告 JSON")
    args = parser.parse_args()

    # 加载数据
    try:
        with open(args.sources, "r", encoding="utf-8") as f:
            sources = json.load(f)
    except Exception as e:
        print(f"[DIVERSITY] 加载信源失败: {e}")
        sources = []

    if not isinstance(sources, list):
        sources = []

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    diversity_config = config.get("quality_gates", {}).get("diversity", {})
    min_language_entropy = diversity_config.get("min_language_entropy", 0.3)
    min_type_entropy = diversity_config.get("min_type_entropy", 0.5)
    max_sentiment_skew = diversity_config.get("max_sentiment_skew", 0.7)
    min_geo_entropy = diversity_config.get("min_geo_entropy", 0.3)

    print(f"[DIVERSITY] v5.0 信息多样性检测 — {len(sources)} 条信源")

    # =========================================================
    # 维度 1: 语言多样性
    # =========================================================
    lang_dist = Counter()
    for s in sources:
        text = s.get("title", "") + " " + s.get("content", "")
        lang = detect_language(text)
        lang_dist[lang] += 1
    language_score = shannon_entropy(dict(lang_dist))

    # =========================================================
    # 维度 2: 信源类型多样性
    # =========================================================
    type_dist = Counter()
    for s in sources:
        stype = classify_source_type(s)
        type_dist[stype] += 1
    type_score = shannon_entropy(dict(type_dist))

    # =========================================================
    # 维度 3: 观点方向性
    # =========================================================
    sentiment_counts = analyze_sentiment_direction(sources)
    total_sentiment = sum(sentiment_counts.values())
    if total_sentiment > 0:
        max_ratio = max(sentiment_counts.values()) / total_sentiment
        sentiment_score = 1.0 - max_ratio  # 越均匀分数越高
    else:
        sentiment_score = 0.5

    # =========================================================
    # 维度 4: 地域多样性
    # =========================================================
    geo_dist = Counter()
    for s in sources:
        geo = detect_geo_from_domain(s.get("url", ""))
        geo_dist[geo] += 1
    geo_score = shannon_entropy(dict(geo_dist))

    # =========================================================
    # 维度 5: 时间分布
    # =========================================================
    # 从 published_date 或 content 中提取年份信息
    years = []
    for s in sources:
        date_str = s.get("published_date", "")
        if date_str:
            year_match = re.search(r"(20\d{2})", str(date_str))
            if year_match:
                years.append(int(year_match.group(1)))
    if len(years) >= 2:
        mean_year = sum(years) / len(years)
        variance = sum((y - mean_year) ** 2 for y in years) / len(years)
        std_dev = math.sqrt(variance)
        temporal_score = min(std_dev / 3.0, 1.0)  # 标准差 3 年以上 = 满分
    else:
        temporal_score = 0.5  # 无法评估

    # =========================================================
    # 综合评分与警告
    # =========================================================
    scores = {
        "language": round(language_score, 3),
        "type": round(type_score, 3),
        "sentiment": round(sentiment_score, 3),
        "geo": round(geo_score, 3),
        "temporal": round(temporal_score, 3),
    }
    overall = round(sum(scores.values()) / len(scores), 3)

    warnings = []
    if language_score < min_language_entropy:
        dominant_lang = lang_dist.most_common(1)[0] if lang_dist else ("unknown", 0)
        warnings.append(
            f"语言多样性不足 ({language_score:.2f} < {min_language_entropy})，"
            f"{dominant_lang[0]}占{dominant_lang[1]}/{sum(lang_dist.values())}，建议搜索其他语言信源"
        )
    if type_score < min_type_entropy:
        dominant_type = type_dist.most_common(1)[0] if type_dist else ("unknown", 0)
        warnings.append(
            f"信源类型多样性不足 ({type_score:.2f} < {min_type_entropy})，"
            f"{dominant_type[0]}占{dominant_type[1]}/{sum(type_dist.values())}，建议补充缺失类型"
        )
    if total_sentiment > 0:
        max_sentiment_key = max(sentiment_counts, key=sentiment_counts.get)
        max_ratio = sentiment_counts[max_sentiment_key] / total_sentiment
        if max_ratio > max_sentiment_skew:
            warnings.append(
                f"观点方向高度一致 ({max_ratio:.0%} {max_sentiment_key})，"
                f"建议搜索反对观点"
            )
    if geo_score < min_geo_entropy:
        dominant_geo = geo_dist.most_common(1)[0] if geo_dist else ("unknown", 0)
        warnings.append(
            f"地域多样性不足 ({geo_score:.2f} < {min_geo_entropy})，"
            f"{dominant_geo[0]}占{dominant_geo[1]}/{sum(geo_dist.values())}"
        )

    filter_bubble_risk = len(warnings) >= 2

    # 生成补充搜索建议
    suggested_searches = generate_suggestions(scores, warnings, sources)

    # 输出报告
    report = {
        "scores": scores,
        "overall_diversity": overall,
        "distributions": {
            "language": dict(lang_dist),
            "type": dict(type_dist),
            "sentiment": sentiment_counts,
            "geo": dict(geo_dist),
            "temporal_years": sorted(set(years)) if years else [],
        },
        "warnings": warnings,
        "suggested_searches": suggested_searches,
        "filter_bubble_risk": filter_bubble_risk,
        "thresholds": {
            "min_language_entropy": min_language_entropy,
            "min_type_entropy": min_type_entropy,
            "max_sentiment_skew": max_sentiment_skew,
            "min_geo_entropy": min_geo_entropy,
        },
    }

    print(f"[DIVERSITY] 多样性评分:")
    for dim, score in scores.items():
        status = "OK" if score >= 0.3 else "LOW"
        print(f"  {dim}: {score:.3f} [{status}]")
    print(f"  综合: {overall:.3f}")
    if warnings:
        print(f"[DIVERSITY] 警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    if filter_bubble_risk:
        print("[DIVERSITY] *** 信息茧房风险 ***")
    if suggested_searches:
        print(f"[DIVERSITY] 补充搜索建议 ({len(suggested_searches)}):")
        for s in suggested_searches[:5]:
            print(f"  → {s}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[DIVERSITY] 完成 → {args.output}")


if __name__ == "__main__":
    main()

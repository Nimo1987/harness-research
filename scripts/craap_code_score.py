#!/usr/bin/env python3
"""
CRAAP 代码化评分脚本 v5.2
将 Currency（时效性）和 Authority（权威性）两个维度从 LLM 评估中剥离，改为纯代码计算。

用法：
  python craap_code_score.py \
    --sources classified_sources.json \
    --config config.yaml \
    --tiers source_tiers.yaml \
    --output sources/craap_code_scores.json

输出格式：
  {
    "https://example.com/article": {
      "currency": {"score": 8.5, "reason": "发布于 2025-11-03，距今 143 天", "method": "code"},
      "authority": {"score": 9.0, "reason": "T1 权威信源 (nature.com)", "method": "code"}
    },
    ...
  }
"""

import argparse
import json
import math
import re
from datetime import datetime, timezone

import yaml


def safe_load_json(path, default=None):
    if default is None:
        default = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return default
        data = json.loads(content)
        return data if data is not None else default
    except (json.JSONDecodeError, FileNotFoundError):
        return default


def parse_date(text):
    """从 snippet/metadata 文本中解析日期。

    尝试多种日期格式，返回 datetime 对象或 None。
    """
    if not text or not isinstance(text, str):
        return None

    # 常见日期正则模式
    patterns = [
        # ISO 格式: 2025-03-26, 2025-03-26T10:30:00
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
        # 斜杠格式: 2025/03/26
        (r"(\d{4}/\d{2}/\d{2})", "%Y/%m/%d"),
        # 英文月格式: Mar 26, 2025 / March 26, 2025
        (
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
            None,
        ),
        # 中文日期: 2025年3月26日
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", None),
        # 日期点分: 26.03.2025
        (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", None),
    ]

    for pattern, fmt in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if fmt:
                    return datetime.strptime(match.group(1), fmt)
                elif "年" in pattern:
                    y, m, d = (
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                    )
                    return datetime(y, m, d)
                elif "\\." in pattern:
                    d, m, y = (
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                    )
                    if 1 <= m <= 12 and 1 <= d <= 31:
                        return datetime(y, m, d)
                else:
                    # 英文月份
                    from dateutil import parser as dateutil_parser

                    return dateutil_parser.parse(match.group(1), fuzzy=True)
            except (ValueError, ImportError):
                continue

    # 最后尝试 dateutil 模糊解析
    try:
        from dateutil import parser as dateutil_parser

        # 限制只解析包含数字的文本
        if re.search(r"\d{4}", text):
            parsed = dateutil_parser.parse(text, fuzzy=True)
            # 验证年份合理性
            if 2000 <= parsed.year <= 2030:
                return parsed
    except (ValueError, ImportError, OverflowError):
        pass

    return None


def score_currency(source, freshness_halflife=365):
    """计算 Currency（时效性）评分。

    评分规则：
      score = max(1, 10 - (days_ago / freshness_halflife) * decay_rate)
      decay_rate 默认 = 5（halflife 天后衰减到 5 分）

    无法解析日期时返回 fallback 标记。
    """
    # 尝试从多个字段提取日期
    date_text = None
    for field in ["published_date", "date", "publish_date", "snippet", "title"]:
        val = source.get(field)
        if val and isinstance(val, str):
            date_text = val
            parsed = parse_date(val)
            if parsed:
                break
    else:
        parsed = None

    if not parsed:
        return {
            "score": 5.0,
            "reason": "无法解析发布日期，使用默认分数",
            "method": "code_fallback",
        }

    now = datetime.now()
    days_ago = (now - parsed).days

    if days_ago < 0:
        days_ago = 0

    # 衰减公式: decay_rate=5 意味着在 halflife 天后得 5 分
    decay_rate = 5.0
    score = max(1.0, 10.0 - (days_ago / max(freshness_halflife, 1)) * decay_rate)
    score = min(10.0, score)
    score = round(score, 1)

    date_str = parsed.strftime("%Y-%m-%d")
    return {
        "score": score,
        "reason": f"发布于 {date_str}，距今 {days_ago} 天",
        "method": "code",
    }


def score_authority(source, tier_domains):
    """计算 Authority（权威性）评分。

    评分规则（基于 source_tiers.yaml 分级）：
      T0 → 10.0（政府原始数据）
      T1 → 9.0（顶级权威）
      T2 → 7.5（专业机构）
      T3 → 5.5（主流新闻）
      T4 → 3.5（一般网站，默认）
      T5 → 1.5（社交/自媒体）
    """
    tier_score_map = {
        0: 10.0,
        1: 9.0,
        2: 7.5,
        3: 5.5,
        4: 3.5,
        5: 1.5,
    }

    # 优先使用已有 tier 字段
    tier = source.get("tier")
    if tier is not None and tier in tier_score_map:
        domain = source.get("domain", "")
        tier_label = {
            0: "T0 零级原始数据",
            1: "T1 权威信源",
            2: "T2 专业机构",
            3: "T3 主流新闻",
            4: "T4 一般网站",
            5: "T5 社交/自媒体",
        }
        return {
            "score": tier_score_map[tier],
            "reason": f"{tier_label.get(tier, f'T{tier}')} ({domain})",
            "method": "code",
        }

    # 如果没有 tier 字段，使用域名匹配
    url = source.get("url", "")
    domain = source.get("domain", "")
    if not domain and url:
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ""

    # 从 tier_domains 匹配
    matched_tier = 4  # 默认 T4
    for tier_level, domains in tier_domains.items():
        for d in domains:
            if d in domain or d in url:
                matched_tier = tier_level
                break
        if matched_tier != 4:
            break

    score = tier_score_map.get(matched_tier, 3.5)
    tier_label = {
        0: "T0 零级原始数据",
        1: "T1 权威信源",
        2: "T2 专业机构",
        3: "T3 主流新闻",
        4: "T4 一般网站",
        5: "T5 社交/自媒体",
    }
    return {
        "score": score,
        "reason": f"{tier_label.get(matched_tier, f'T{matched_tier}')} ({domain})",
        "method": "code",
    }


def load_tier_domains(tiers_path):
    """加载 source_tiers.yaml 并转为 {tier_level: [domain_list]} 格式"""
    try:
        with open(tiers_path, "r", encoding="utf-8") as f:
            tiers = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[CRAAP-CODE] 警告：未找到 {tiers_path}，Authority 评分将使用默认值")
        return {}

    tier_map = {
        "tier_0_raw_data": 0,
        "tier_1_authority": 1,
        "tier_2_professional": 2,
        "tier_3_news": 3,
        "tier_5_social": 5,
    }

    result = {}
    for key, level in tier_map.items():
        domains = tiers.get(key, [])
        if isinstance(domains, list):
            result[level] = [d.strip().lower() for d in domains if isinstance(d, str)]

    return result


def main():
    parser = argparse.ArgumentParser(description="CRAAP 代码化评分 v5.2")
    parser.add_argument("--sources", required=True, help="分类后的信源 JSON 文件")
    parser.add_argument("--config", required=True, help="全局配置 YAML")
    parser.add_argument("--tiers", required=True, help="信源分级 YAML 文件")
    parser.add_argument("--output", required=True, help="输出评分 JSON 文件")
    args = parser.parse_args()

    # 加载数据
    sources = safe_load_json(args.sources, [])
    tier_domains = load_tier_domains(args.tiers)

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}

    # 从 config 推导 freshness_halflife
    eval_config = config.get("evaluation", {})
    currency_weight = eval_config.get("craap_weights", {}).get("currency", 0.2)
    # currency_weight 越高，halflife 越短（对时效性更敏感）
    # 基准: weight=0.2 → halflife=365, weight=0.4 → halflife=180
    freshness_halflife = max(90, int(365 * (0.2 / max(currency_weight, 0.05))))

    print(f"[CRAAP-CODE] v5.2 代码化评分开始")
    print(
        f"[CRAAP-CODE] 信源数: {len(sources)}, freshness_halflife: {freshness_halflife} 天"
    )
    print(f"[CRAAP-CODE] 域名分级规则: {sum(len(v) for v in tier_domains.values())} 条")

    # 评分
    results = {}
    code_count = 0
    fallback_count = 0

    for source in sources:
        if not isinstance(source, dict):
            continue
        url = source.get("url", "")
        if not url:
            continue

        currency = score_currency(source, freshness_halflife)
        authority = score_authority(source, tier_domains)

        results[url] = {
            "currency": currency,
            "authority": authority,
        }

        if currency.get("method") == "code":
            code_count += 1
        else:
            fallback_count += 1

    # 保存结果
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[CRAAP-CODE] 完成: {len(results)} 条评分")
    print(f"[CRAAP-CODE] Currency 代码评分: {code_count}, 回退 LLM: {fallback_count}")
    print(f"[CRAAP-CODE] 输出 → {args.output}")


if __name__ == "__main__":
    main()

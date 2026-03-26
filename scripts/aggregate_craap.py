#!/usr/bin/env python3
"""
CRAAP 评分聚合与过滤脚本 v5.2
v5.0 变更：T0 信源直通逻辑（政府原始数据跳过 CRAAP 评估，直接通过）
v5.2 变更：合并代码评分（Currency/Authority）和 LLM 评分（Relevance/Accuracy/Purpose）

用法：
  python aggregate_craap.py \
    --sources classified_sources.json \
    --scores craap_scores.json \
    --code-scores craap_code_scores.json \
    --config config.yaml \
    --output filtered_sources.json \
    --stats eval_stats.json
"""

import argparse
import json

import yaml


def safe_load_json(path: str, default=None):
    """安全加载 JSON，处理空文件和格式错误"""
    if default is None:
        default = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            print(f"[AGGREGATE] 警告：{path} 为空文件，使用默认值")
            return default
        data = json.loads(content)
        if data is None:
            return default
        return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[AGGREGATE] 警告：加载 {path} 失败 ({e})，使用默认值")
        return default


def safe_score(dim_data, fallback=5) -> float:
    """安全提取评分，处理各种异常格式"""
    if dim_data is None:
        return fallback
    if isinstance(dim_data, (int, float)):
        return float(dim_data)
    if isinstance(dim_data, dict):
        score = dim_data.get("score", fallback)
        if score is None:
            return fallback
        try:
            return float(score)
        except (ValueError, TypeError):
            return fallback
    return fallback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True)
    parser.add_argument("--scores", required=True)
    parser.add_argument(
        "--code-scores", default=None, help="v5.2: 代码评分文件（Currency/Authority）"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats", required=True)
    parser.add_argument(
        "--cross-source-map", default=None, help="交叉信源映射文件路径（可选）"
    )
    parser.add_argument(
        "--currency-weight", type=int, default=1, help="时效权重倍数 1-3（默认 1）"
    )
    args = parser.parse_args()

    sources = safe_load_json(args.sources, [])
    scores = safe_load_json(args.scores, [])

    # v5.2: 加载代码评分
    code_scores = {}
    if args.code_scores:
        code_scores = safe_load_json(args.code_scores, {})
        if not isinstance(code_scores, dict):
            code_scores = {}
        print(f"[AGGREGATE] v5.2 代码评分: {len(code_scores)} 条")

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    eval_config = config.get("evaluation", {})
    threshold = eval_config.get("craap_threshold", 6.0)
    craap_weights = eval_config.get(
        "craap_weights",
        {
            "currency": 0.167,
            "relevance": 0.167,
            "authority": 0.25,
            "accuracy": 0.25,
            "purpose": 0.167,
        },
    )

    # 加载交叉信源映射（可选）
    cross_map = {}
    if args.cross_source_map:
        cross_map = safe_load_json(args.cross_source_map, {})
        if not isinstance(cross_map, dict):
            cross_map = {}
        print(f"[AGGREGATE] 交叉信源映射: {len(cross_map)} 条")

    # 时效权重归一化
    currency_weight = max(1, min(3, args.currency_weight))
    adjusted_weights = dict(craap_weights)
    if currency_weight > 1:
        adjusted_weights["currency"] = (
            adjusted_weights.get("currency", 0.2) * currency_weight
        )
        total_w = sum(adjusted_weights.values())
        if total_w > 0:
            adjusted_weights = {k: v / total_w for k, v in adjusted_weights.items()}

    # 过滤无效 scores 条目
    valid_scores = [s for s in scores if isinstance(s, dict) and s.get("url")]

    # 建立 URL → LLM 评分 映射
    score_map = {}
    for entry in valid_scores:
        url = entry.get("url", "")
        if url:
            score_map[url] = entry

    print(
        f"[AGGREGATE] v5.2 信源: {len(sources)}, LLM评分: {len(valid_scores)}, 代码评分: {len(code_scores)}"
    )

    # =========================================================
    # v5.0: 分离 T0 信源和普通信源
    # T0 信源直通，不需要 CRAAP 评分
    # =========================================================
    t0_sources = []
    regular_sources = []

    for s in sources:
        if not isinstance(s, dict):
            continue
        if s.get("skip_craap", False) or s.get("tier") == 0:
            # T0 信源：直通，设置满分
            s["craap_score"] = 10.0
            s["craap_detail"] = {"note": "T0 零级原始数据，跳过 CRAAP 评估"}
            s["key_facts"] = s.get("key_facts", [])
            s["bias_detected"] = False
            s["bias_description"] = ""
            s["t0_passthrough"] = True
            t0_sources.append(s)
        else:
            regular_sources.append(s)

    if t0_sources:
        print(f"[AGGREGATE] v5.0 T0 直通信源: {len(t0_sources)} 条")

    # v5.2: 合并代码评分和 LLM 评分到普通信源
    matched = 0
    code_used = 0
    for s in regular_sources:
        url = s.get("url", "")
        eval_data = score_map.get(url, {})
        code_data = code_scores.get(url, {})

        if eval_data or code_data:
            matched += 1
            dims = ["currency", "relevance", "authority", "accuracy", "purpose"]
            weighted_sum = 0
            scoring_method = {}

            for dim in dims:
                dim_weight = adjusted_weights.get(dim, 0.2)

                # v5.2: Currency 和 Authority 优先使用代码评分
                if dim in ("currency", "authority") and code_data.get(dim):
                    code_dim = code_data[dim]
                    # 如果代码评分是 fallback，则使用 LLM 评分（如果有）
                    if code_dim.get("method") == "code_fallback" and eval_data.get(dim):
                        dim_score = safe_score(eval_data.get(dim), 5)
                        scoring_method[dim] = "llm_fallback"
                    else:
                        dim_score = safe_score(code_dim, 5)
                        scoring_method[dim] = "code"
                        code_used += 1
                else:
                    # Relevance/Accuracy/Purpose 使用 LLM 评分
                    dim_score = safe_score(eval_data.get(dim), 5)
                    scoring_method[dim] = "llm"

                weighted_sum += dim_score * dim_weight

            # 交叉信源加成
            cross_info = cross_map.get(url, {})
            bonus_pct = (
                cross_info.get("bonus_pct", 0) if isinstance(cross_info, dict) else 0
            )
            if bonus_pct > 0:
                weighted_sum = weighted_sum * (1 + bonus_pct)
                s["cross_source"] = True
                s["cross_layers"] = cross_info.get("layers", [])
                s["cross_bonus"] = bonus_pct

            s["craap_score"] = round(weighted_sum, 2)

            # v5.2: 合并 detail，包含代码评分和 LLM 评分
            detail = {}
            for dim in dims:
                if dim in ("currency", "authority") and code_data.get(dim):
                    code_dim = code_data[dim]
                    if code_dim.get("method") != "code_fallback":
                        detail[dim] = code_dim
                    elif eval_data.get(dim):
                        detail[dim] = eval_data.get(dim, {})
                    else:
                        detail[dim] = code_dim
                else:
                    detail[dim] = eval_data.get(dim, {})

            s["craap_detail"] = detail
            s["scoring_method"] = scoring_method
            s["key_facts"] = eval_data.get("key_facts") or []
            s["bias_detected"] = bool(eval_data.get("bias_detected", False))
            s["bias_description"] = eval_data.get("bias_description") or ""
        else:
            s["craap_score"] = 0
            s["craap_detail"] = {}
            s["scoring_method"] = {}
            s["key_facts"] = []
            s["bias_detected"] = False
            s["bias_description"] = ""

    print(f"[AGGREGATE] 匹配到评分: {matched}/{len(regular_sources)}")
    print(f"[AGGREGATE] v5.2 代码评分使用次数: {code_used}")

    # 过滤普通信源
    passed_regular = [
        s for s in regular_sources if s.get("craap_score", 0) >= threshold
    ]
    rejected = [s for s in regular_sources if s.get("craap_score", 0) < threshold]

    # v5.0: 合并 T0 直通信源 + 通过筛选的普通信源
    passed = t0_sources + passed_regular

    # 排序：T0 置顶，然后按权重×评分排序
    passed.sort(
        key=lambda x: (
            0 if x.get("tier") == 0 else 1,  # T0 在前
            -(x.get("weight", 0.4) * x.get("craap_score", 0)),
        )
    )

    # 统计
    avg_craap = (
        sum(s.get("craap_score", 0) for s in passed) / len(passed) if passed else 0
    )
    tier_dist = {}
    for s in passed:
        t = s.get("tier", 4)
        tier_dist[f"T{t}"] = tier_dist.get(f"T{t}", 0) + 1

    stats = {
        "total_evaluated": len(sources),
        "t0_passthrough": len(t0_sources),
        "regular_evaluated": len(regular_sources),
        "passed": len(passed),
        "passed_regular": len(passed_regular),
        "rejected": len(rejected),
        "avg_craap_score": round(avg_craap, 2),
        "tier_distribution": tier_dist,
        "threshold_used": threshold,
        "bias_detected_count": sum(
            1 for s in sources if isinstance(s, dict) and s.get("bias_detected")
        ),
        "cross_source_count": sum(1 for s in passed if s.get("cross_source")),
        "currency_weight": currency_weight,
        "adjusted_weights": {k: round(v, 3) for k, v in adjusted_weights.items()},
        # v5.2 新增
        "code_scored_dimensions": code_used,
        "scoring_version": "5.2",
    }

    print(
        f"[AGGREGATE] 通过: {len(passed)} (T0直通:{len(t0_sources)} + 常规:{len(passed_regular)}), "
        f"过滤: {len(rejected)}, 平均CRAAP: {avg_craap:.2f}"
    )
    print(f"[AGGREGATE] 分布: {tier_dist}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(passed, f, ensure_ascii=False, indent=2)

    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"[AGGREGATE] 完成 → {args.output}, {args.stats}")


if __name__ == "__main__":
    main()

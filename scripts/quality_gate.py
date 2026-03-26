#!/usr/bin/env python3
"""
质量门控脚本 v5.0 — 三级判定：PASS / WARN / FAIL
v5.0 变更：新增多样性门控 + 反直觉门控 + T0 信源检查 + 数据表格密度

用法：
  python quality_gate.py check_sources \
    --filtered filtered_sources.json \
    --stats eval_stats.json \
    --triangulation triangulation.json \
    --diversity diversity_report.json \
    --contradiction contradiction_analysis.json \
    --config config.yaml \
    --retry-count 0 \
    --warnings-output warnings.json

  python quality_gate.py check_report \
    --report clean_report.html \
    --config config.yaml \
    --retry-count 0 \
    --warnings-output warnings.json
"""

import argparse
import json
import os
import re
import sys

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
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return default


def check_sources(args):
    sources = safe_load_json(args.filtered, [])
    stats = safe_load_json(args.stats, {})

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    gates = config.get("quality_gates", {}).get("sources", {})
    diversity_gates = config.get("quality_gates", {}).get("diversity", {})
    retry_count = args.retry_count
    max_retries = 2

    hard_fails = []
    warnings = []

    # ===== 基本阈值 =====
    min_total = gates.get("min_total_sources", 10)
    min_t1 = gates.get("min_tier1_sources", 1)
    min_t2 = gates.get("min_tier2_sources", 2)
    min_avg = gates.get("min_avg_craap", 5.5)
    min_verified = gates.get("min_verified_points", 2)
    hard_min_total = gates.get("hard_min_total_sources", 5)
    hard_min_craap = gates.get("hard_min_avg_craap", 4.0)

    # ===== 动态阈值 =====
    adaptive = gates.get("adaptive_threshold", False)
    reduction = gates.get("adaptive_reduction", 0.3)

    raw_results_path = os.path.join(
        os.path.dirname(args.filtered), "raw_search_results.json"
    )
    raw_count = 0
    if os.path.exists(raw_results_path):
        try:
            with open(raw_results_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                raw_count = len(raw_data) if isinstance(raw_data, list) else 0
        except Exception:
            raw_count = 0

    if adaptive and raw_count > 0 and raw_count < 40:
        factor = 1.0 - reduction
        min_total = max(hard_min_total, int(min_total * factor))
        min_t1 = max(0, int(min_t1 * factor))
        min_t2 = max(0, int(min_t2 * factor))
        min_avg = max(hard_min_craap, min_avg * factor)
        min_verified = max(1, int(min_verified * factor))
        warnings.append(
            f"信源稀少（原始搜索结果仅 {raw_count} 条），已自动降低质量阈值 {int(reduction * 100)}%"
        )

    # ===== 总信源数 =====
    total = len(sources)
    if total < hard_min_total:
        hard_fails.append(f"信源严重不足: {total}/{hard_min_total}（最低要求）")
    elif total < min_total:
        warnings.append(f"信源数量偏少: {total}/{min_total}（可继续但报告深度受限）")

    # ===== T0 信源（v5.0 新增，不强制要求） =====
    t0 = sum(1 for s in sources if s.get("tier") == 0)
    if t0 > 0:
        print(f"  [INFO] T0 原始数据信源: {t0} 条")

    # ===== 一级权威 =====
    t1 = sum(1 for s in sources if s.get("tier") == 1)
    if t1 < min_t1:
        if retry_count < max_retries:
            hard_fails.append(
                f"一级权威信源不足: {t1}/{min_t1}，"
                f"建议搜索关键词加上 site:.gov OR site:.edu OR site:nature.com"
            )
        else:
            warnings.append(
                f"一级权威信源不足: {t1}/{min_t1}（已重试{retry_count}次，降级继续）"
            )

    # ===== 二级专业 =====
    t2 = sum(1 for s in sources if s.get("tier") == 2)
    if t2 < min_t2:
        if retry_count < max_retries:
            hard_fails.append(
                f"二级专业信源不足: {t2}/{min_t2}，"
                f"建议搜索关键词加上 site:mckinsey.com OR site:gartner.com"
            )
        else:
            warnings.append(
                f"二级专业信源不足: {t2}/{min_t2}（已重试{retry_count}次，降级继续）"
            )

    # ===== 平均 CRAAP =====
    avg = stats.get("avg_craap_score", 0)
    if avg < min_avg and avg > 0:
        if avg < hard_min_craap:
            hard_fails.append(f"平均 CRAAP 分数过低: {avg:.2f}/{min_avg}")
        else:
            warnings.append(f"平均 CRAAP 分数偏低: {avg:.2f}/{min_avg}")

    # ===== 三角验证 =====
    if args.triangulation:
        try:
            with open(args.triangulation, "r", encoding="utf-8") as f:
                tri = json.loads(f.read().strip() or "{}")
        except Exception:
            tri = {}
        verified = len(tri.get("verified_data_points", []))
        if verified < min_verified:
            warnings.append(f"已验证数据点偏少: {verified}/{min_verified}")

    # ===== v5.0: 多样性门控 =====
    if args.diversity:
        diversity = safe_load_json(args.diversity, {})
        if isinstance(diversity, dict):
            scores = diversity.get("scores", {})
            min_lang = diversity_gates.get("min_language_entropy", 0.3)
            min_type = diversity_gates.get("min_type_entropy", 0.5)
            max_skew = diversity_gates.get("max_sentiment_skew", 0.7)

            if scores.get("language", 1.0) < min_lang:
                warnings.append(
                    f"语言多样性不足: {scores.get('language', 0):.2f}/{min_lang}，"
                    f"建议补充非主要语言搜索"
                )
            if scores.get("type", 1.0) < min_type:
                warnings.append(
                    f"信源类型多样性不足: {scores.get('type', 0):.2f}/{min_type}"
                )
            if scores.get("sentiment", 1.0) < (1.0 - max_skew):
                warnings.append(f"观点方向高度一致，可能存在信息茧房风险")
            if diversity.get("filter_bubble_risk"):
                warnings.append("信息茧房风险警告：多个多样性维度低于阈值")

    # ===== v5.0: 反直觉门控 =====
    if args.contradiction:
        contradiction = safe_load_json(args.contradiction, {})
        if isinstance(contradiction, dict):
            findings = contradiction.get("counterintuitive_findings", [])
            min_findings = diversity_gates.get("min_counterintuitive_findings", 1)
            if len(findings) < min_findings:
                warnings.append(
                    f"反直觉发现不足: {len(findings)}/{min_findings}，"
                    f"报告可能缺少深度洞察"
                )

    # ===== 判定 =====
    result = {
        "hard_fails": hard_fails,
        "warnings": warnings,
        "retry_count": retry_count,
        "t0_count": t0,
    }

    if args.warnings_output:
        with open(args.warnings_output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    if hard_fails:
        print("FAIL")
        for item in hard_fails:
            print(f"  [FAIL] {item}")
        for item in warnings:
            print(f"  [WARN] {item}")
        sys.exit(1)
    elif warnings:
        print("WARN")
        for item in warnings:
            print(f"  [WARN] {item}")
        print("  → 降级继续，上述问题将在报告「研究方法与局限性」章节中披露")
        sys.exit(0)
    else:
        print("PASS")
        print(f"  信源: {total} (T0:{t0} T1:{t1} T2:{t2}), 平均CRAAP: {avg:.2f}")
        sys.exit(0)


def check_report(args):
    try:
        with open(args.report, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("FAIL")
        print(f"  [FAIL] 报告文件不存在: {args.report}")
        sys.exit(1)

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    gates = config.get("quality_gates", {}).get("report", {})
    retry_count = args.retry_count

    hard_fails = []
    warnings = []

    # 字符数
    text_only = re.sub(r"<[^>]+>", "", html)
    char_count = len(text_only.strip())
    min_chars = gates.get("min_char_count", 3000)
    hard_min = gates.get("hard_min_char_count", 500)
    if char_count < hard_min:
        hard_fails.append(f"报告字数严重不足: {char_count}/{hard_min}（最低要求）")
    elif char_count < min_chars:
        if retry_count < 1:
            hard_fails.append(f"报告字数不足: {char_count}/{min_chars}")
        else:
            warnings.append(
                f"报告字数偏少: {char_count}/{min_chars}（已重试，降级继续）"
            )

    # 必要章节
    required = gates.get("required_sections", [])
    missing = [s for s in required if s not in html]
    if missing:
        if retry_count < 1:
            hard_fails.append(f"缺少必要章节: {', '.join(missing)}")
        else:
            warnings.append(f"缺少章节: {', '.join(missing)}（已重试，降级继续）")

    # 表格检查
    if gates.get("must_have_tables", True):
        if "<table" not in html:
            warnings.append("报告中没有表格")

    # v5.0: 数据表格密度检查
    min_density = gates.get("min_data_table_density", 0.001)
    table_count = html.count("<table")
    if char_count > 0:
        density = table_count / max(char_count, 1)
        expected_tables = max(1, int(char_count * min_density))
        if table_count < expected_tables:
            warnings.append(
                f"数据表格密度偏低: {table_count}个/{expected_tables}个期望"
                f"（每1000字至少1个）"
            )

    # Markdown 残留
    if gates.get("no_markdown_tables", True):
        md_table_pattern = r"\|[\s\-:]+\|"
        if re.search(md_table_pattern, html):
            hard_fails.append("检测到 Markdown 表格语法残留")

    if "```" in html:
        hard_fails.append("检测到 Markdown 代码块残留")

    # ===== v5.2: 报告一致性检查 =====
    # 1. 检查执行摘要中提到的结论是否在正文章节中有对应分析
    exec_summary_match = re.search(
        r"<h2[^>]*>.*?执行摘要.*?</h2>(.*?)(?=<h2|$)", html, re.DOTALL | re.IGNORECASE
    )
    if exec_summary_match:
        exec_text = re.sub(r"<[^>]+>", "", exec_summary_match.group(1))
        body_text = html[exec_summary_match.end() :]
        body_plain = re.sub(r"<[^>]+>", "", body_text)

        # 提取执行摘要中的数字型结论（如百分比、金额等）
        exec_numbers = set(re.findall(r"\d+\.?\d*%", exec_text))
        body_numbers = set(re.findall(r"\d+\.?\d*%", body_plain))
        orphan_numbers = exec_numbers - body_numbers
        if orphan_numbers and len(orphan_numbers) > len(exec_numbers) * 0.5:
            warnings.append(
                f"执行摘要中 {len(orphan_numbers)} 个数据点在正文中未找到对应分析"
            )

    # 2. 检查参考文献列表的信源是否都在正文中被引用（孤立引用检测）
    ref_section = re.search(
        r"<h2[^>]*>.*?参考文献.*?</h2>(.*?)(?=<h2|$)", html, re.DOTALL | re.IGNORECASE
    )
    if ref_section:
        ref_urls = re.findall(r'href="(https?://[^"]+)"', ref_section.group(1))
        body_before_refs = html[: ref_section.start()]
        orphan_refs = []
        for ref_url in ref_urls:
            # 检查 URL 或域名是否在正文中出现
            domain = re.search(r"https?://([^/]+)", ref_url)
            domain_str = domain.group(1) if domain else ref_url
            if domain_str not in body_before_refs and ref_url not in body_before_refs:
                orphan_refs.append(ref_url)
        if orphan_refs:
            warnings.append(f"发现 {len(orphan_refs)} 条孤立参考文献（未在正文中引用）")

    # 3. 检查置信度标签分布（不应全是 [高置信度]）
    confidence_tags = re.findall(r"\[([高中低])置信度\]", html)
    if confidence_tags:
        high_count = confidence_tags.count("高")
        total_conf = len(confidence_tags)
        if total_conf >= 3 and high_count == total_conf:
            warnings.append(
                f"所有 {total_conf} 个置信度标签均为[高置信度]，可能缺乏审慎评估"
            )
        elif total_conf >= 5 and high_count / total_conf > 0.8:
            warnings.append(f"置信度分布偏高: {high_count}/{total_conf} 为[高置信度]")

    # 判定
    result = {
        "hard_fails": hard_fails,
        "warnings": warnings,
        "retry_count": retry_count,
    }

    if args.warnings_output:
        with open(args.warnings_output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    if hard_fails:
        print("FAIL")
        for item in hard_fails:
            print(f"  [FAIL] {item}")
        for item in warnings:
            print(f"  [WARN] {item}")
        sys.exit(1)
    elif warnings:
        print("WARN")
        for item in warnings:
            print(f"  [WARN] {item}")
        sys.exit(0)
    else:
        print("PASS")
        print(f"  字符数: {char_count}, 表格: {table_count}")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    sp1 = subparsers.add_parser("check_sources")
    sp1.add_argument("--filtered", required=True)
    sp1.add_argument("--stats", required=True)
    sp1.add_argument("--triangulation", default=None)
    sp1.add_argument("--diversity", default=None, help="v5.0: 多样性报告 JSON")
    sp1.add_argument("--contradiction", default=None, help="v5.0: 矛盾分析 JSON")
    sp1.add_argument("--config", required=True)
    sp1.add_argument("--retry-count", type=int, default=0)
    sp1.add_argument("--warnings-output", default=None)

    sp2 = subparsers.add_parser("check_report")
    sp2.add_argument("--report", required=True)
    sp2.add_argument("--config", required=True)
    sp2.add_argument("--retry-count", type=int, default=0)
    sp2.add_argument("--warnings-output", default=None)

    args = parser.parse_args()

    if args.command == "check_sources":
        check_sources(args)
    elif args.command == "check_report":
        check_report(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

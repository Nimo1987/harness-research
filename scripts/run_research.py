#!/usr/bin/env python3
"""
Deep Research Pro v5.3 — State Machine Driver (Harness Research)

核心设计：将 30 步流程的编排权从 LLM 收回到代码中。
LLM agent 只需循环调用此脚本，脚本告诉 agent 下一步做什么。

v5.3 变更：
  - 修复：16_quality_gate2 回退目标从 9b_write_sections 改为 14_merge_html，
    避免回退后 agent auto-confirm LLM 步骤导致正文文件被清空
  - 修复：merge_html_fragments() 增加空文件检测和警告，
    不再静默合并空章节文件

v5.2 变更：
  - 新增 3a2_dedup（搜索去重前置）
  - 5_craap 拆分为 5a_craap_code（代码）+ 5b_craap_llm（LLM）
  - 新增 9a_match_sources（章节信源预匹配）
  - 9_write_sections 改名为 9b_write_sections
  - 6_aggregate 新增 --code-scores 参数
  - 16_quality_gate2 增强一致性检查
  - 新增 status 子命令

两种步骤类型：
  CODE  — 脚本直接执行（调用其他 Python 脚本），不需要 LLM
  LLM   — 脚本输出 prompt 文件路径 + 模板变量，agent 执行 LLM 调用后写回结果文件

用法：
  # 初始化（仅首次）
  python run_research.py init --topic "研究主题" --workspace /path/to/workspace --skill-dir /path/to/skill

  # 推进到下一步（循环调用）
  python run_research.py next --workspace /path/to/workspace --skill-dir /path/to/skill

  # 查看当前进度
  python run_research.py status --workspace /path/to/workspace --skill-dir /path/to/skill

输出格式（JSON，agent 解析执行）：
  {"status": "need_llm", "step": "1_plan", "prompt_file": "...", "variables": {...}, "output_file": "...", "instruction": "..."}
  {"status": "done_code", "step": "3a_search", "message": "搜索完成，已保存到...", "next": true}
  {"status": "completed", "message": "全部完成", "outputs": [...]}
  {"status": "failed", "step": "...", "error": "..."}
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def q(path):
    """Shell-quote a path for safe embedding in shell commands."""
    return shlex.quote(str(path))


# =============================================================================
# 步骤定义：严格有序，不可跳过（v5.2: 30 步）
# =============================================================================

STEPS = [
    # === 阶段一：研究计划 ===
    {"id": "1_plan", "type": "LLM", "phase": "PLAN"},
    {"id": "2_mece", "type": "LLM", "phase": "PLAN"},
    # === 阶段二：多层搜索 ===
    {"id": "3a_search_web", "type": "CODE", "phase": "SEARCH"},
    {"id": "3a2_dedup", "type": "CODE", "phase": "SEARCH"},  # v5.2 新增
    {"id": "3b_finance", "type": "CODE", "phase": "SEARCH", "conditional": "finance"},
    {"id": "3c_academic", "type": "CODE", "phase": "SEARCH", "conditional": "academic"},
    {"id": "3d_gov_data", "type": "CODE", "phase": "SEARCH", "conditional": "gov_data"},
    {
        "id": "3e_regulatory",
        "type": "CODE",
        "phase": "SEARCH",
        "conditional": "regulatory_filings",
    },
    {
        "id": "3f_weak_signals",
        "type": "CODE",
        "phase": "SEARCH",
        "conditional": "weak_signals",
    },
    # === 阶段三：信源评估 ===
    {"id": "4_classify", "type": "CODE", "phase": "EVALUATE"},
    {"id": "4.5_cross_source", "type": "CODE", "phase": "EVALUATE"},
    {"id": "3g_full_content", "type": "CODE", "phase": "EVALUATE"},
    {"id": "5a_craap_code", "type": "CODE", "phase": "EVALUATE"},  # v5.2 新增
    {"id": "5b_craap_llm", "type": "LLM", "phase": "EVALUATE"},  # v5.2 改名
    {"id": "6_aggregate", "type": "CODE", "phase": "EVALUATE"},
    {"id": "6.5_diversity", "type": "CODE", "phase": "EVALUATE"},
    # === 阶段四：验证与矛盾分析 ===
    {"id": "7_triangulate", "type": "LLM", "phase": "VERIFY"},
    {"id": "7.5_contradiction", "type": "LLM", "phase": "VERIFY"},
    {"id": "7.6_cross_lang", "type": "LLM", "phase": "VERIFY"},
    {"id": "8_quality_gate1", "type": "CODE", "phase": "VERIFY"},
    # === 阶段五：分析与撰写 ===
    {"id": "9a_match_sources", "type": "CODE", "phase": "WRITE"},  # v5.2 新增
    {"id": "9b_write_sections", "type": "LLM", "phase": "WRITE"},  # v5.2 改名
    {"id": "10_exec_summary", "type": "LLM", "phase": "WRITE"},
    {"id": "12_methodology", "type": "LLM", "phase": "WRITE"},
    {"id": "12.5_verification", "type": "LLM", "phase": "WRITE"},
    # === 阶段六：合并与渲染 ===
    {"id": "13_references", "type": "CODE", "phase": "RENDER"},
    {"id": "14_merge_html", "type": "CODE", "phase": "RENDER"},
    {"id": "15_sanitize", "type": "CODE", "phase": "RENDER"},
    {"id": "16_quality_gate2", "type": "CODE", "phase": "RENDER"},
    {"id": "17_render_all", "type": "CODE", "phase": "RENDER"},
]


def load_state(workspace):
    """加载当前执行状态"""
    state_file = os.path.join(workspace, "driver_state.json")
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(workspace, state):
    """保存执行状态"""
    state_file = os.path.join(workspace, "driver_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def safe_load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def run_script(cmd, cwd=None):
    """执行 Python 脚本，返回 (returncode, stdout, stderr)。

    cmd 可以是字符串或列表。如果是字符串，用 shlex.split 拆分以正确处理带空格路径。
    """
    try:
        if isinstance(cmd, str):
            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd
        result = subprocess.run(
            cmd_list, capture_output=True, text=True, cwd=cwd, timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout after 300s"
    except Exception as e:
        return -1, "", str(e)


def output(data):
    """输出 JSON 给 agent 解析"""
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


def output_error(step_id, error_msg):
    output({"status": "failed", "step": step_id, "error": error_msg})


# =============================================================================
# 初始化
# =============================================================================


def cmd_init(args):
    workspace = os.path.abspath(args.workspace)
    skill_dir = os.path.abspath(args.skill_dir)
    topic = args.topic

    # 创建目录
    for sub in ["sources", "analysis", "output"]:
        os.makedirs(os.path.join(workspace, sub), exist_ok=True)

    # 写入主题
    with open(os.path.join(workspace, "topic.txt"), "w", encoding="utf-8") as f:
        f.write(topic)

    # 初始化状态
    state = {
        "topic": topic,
        "workspace": workspace,
        "skill_dir": skill_dir,
        "current_step_index": 0,
        "search_retry": 0,
        "report_retry": 0,
        "completed_steps": [],
        "skipped_steps": [],
        "sections": [],  # 章节列表（步骤 1 完成后填充）
        "data_sources": {},  # 数据源配置（步骤 1 完成后填充）
        "version": "5.3.0",
    }
    save_state(workspace, state)

    output(
        {
            "status": "initialized",
            "message": f"工作目录已创建: {workspace}",
            "next_step": STEPS[0]["id"],
            "total_steps": len(STEPS),
            "version": "5.3.0",
        }
    )


# =============================================================================
# 推进到下一步
# =============================================================================


def cmd_next(args):
    workspace = os.path.abspath(args.workspace)
    skill_dir = os.path.abspath(args.skill_dir)

    state = load_state(workspace)
    if not state:
        output_error("init", "未找到 driver_state.json，请先运行 init")

    idx = state["current_step_index"]
    if idx >= len(STEPS):
        # 全部完成
        output_completed(workspace)
        return

    step = STEPS[idx]
    step_id = step["id"]
    step_type = step["type"]
    topic = state["topic"]

    # 检查条件步骤
    if "conditional" in step:
        data_sources = state.get("data_sources", {})
        condition_key = step["conditional"]
        if not data_sources.get(condition_key, False):
            # 跳过此步骤
            state["skipped_steps"].append(step_id)
            state["current_step_index"] = idx + 1
            save_state(workspace, state)
            # 递归推进到下一步
            cmd_next(args)
            return

    # 分发执行
    if step_type == "CODE":
        execute_code_step(step_id, state, workspace, skill_dir)
    elif step_type == "LLM":
        prepare_llm_step(step_id, state, workspace, skill_dir)


def advance_step(state, workspace, step_id, message=""):
    """标记当前步骤完成，推进索引"""
    state["completed_steps"].append(step_id)
    state["current_step_index"] += 1
    save_state(workspace, state)

    idx = state["current_step_index"]
    if idx >= len(STEPS):
        output(
            {
                "status": "done_code",
                "step": step_id,
                "message": message,
                "next": False,
                "all_done": True,
            }
        )
    else:
        output(
            {
                "status": "done_code",
                "step": step_id,
                "message": message,
                "next": True,
                "next_step": STEPS[idx]["id"],
                "progress": f"{idx}/{len(STEPS)}",
            }
        )


def output_completed(workspace):
    """全部完成，列出输出文件"""
    output_dir = os.path.join(workspace, "output")
    files = []
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if not f.startswith(".")]
    output(
        {
            "status": "completed",
            "message": f"全部 {len(STEPS)} 步已完成。",
            "outputs": files,
            "output_dir": output_dir,
        }
    )


# =============================================================================
# CODE 步骤执行
# =============================================================================


def execute_code_step(step_id, state, workspace, skill_dir):
    topic = state["topic"]
    src = os.path.join(workspace, "sources")
    ana = os.path.join(workspace, "analysis")
    scripts = os.path.join(skill_dir, "scripts")
    config = os.path.join(skill_dir, "config.yaml")
    tiers = os.path.join(skill_dir, "references", "source_tiers.yaml")

    py = sys.executable  # 使用当前 Python 解释器的完整路径，避免 PATH 问题

    if step_id == "3a_search_web":
        execute_search_web(state, workspace, skill_dir, py, scripts, src)

    # v5.2 新增：搜索去重前置
    elif step_id == "3a2_dedup":
        raw_path = os.path.join(src, "raw_search_results.json")
        deduped_path = os.path.join(src, "raw_search_results_deduped.json")
        stats_path = os.path.join(src, "dedup_stats.json")
        cmd = [
            py,
            os.path.join(scripts, "dedup_sources.py"),
            "--input",
            raw_path,
            "--output",
            deduped_path,
            "--stats",
            stats_path,
        ]
        rc, out, err = run_script(cmd)
        # 用去重后的结果替换原始结果
        if rc == 0 and os.path.exists(deduped_path):
            import shutil

            shutil.copy2(deduped_path, raw_path)
        advance_step(
            state,
            workspace,
            step_id,
            f"搜索去重完成: {out.strip()}"
            if rc == 0
            else f"去重失败（已降级跳过）: {err.strip()}",
        )

    elif step_id == "3b_finance":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        fc = plan.get("finance_context", {})
        fc_path = os.path.join(src, "finance_context.json")
        with open(fc_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        cmd = [
            py,
            os.path.join(scripts, "fetch_financial_data.py"),
            "--finance-context",
            fc_path,
            "--output",
            os.path.join(src, "financial_data.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"金融数据获取{'完成' if rc == 0 else '失败（已降级跳过）'}: {out.strip()}",
        )

    elif step_id == "3c_academic":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        kws = plan.get("search_keywords", {}).get("academic", [])
        kw_path = os.path.join(src, "academic_keywords.json")
        keywords = extract_keywords(kws)
        with open(kw_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False)
        cmd = [
            py,
            os.path.join(scripts, "search_sources.py"),
            "academic",
            "--keywords-file",
            kw_path,
            "--max-results",
            "10",
            "--output",
            os.path.join(src, "academic_results.json"),
        ]
        rc, out, err = run_script(cmd)
        merge_results(src, "academic_results.json")
        advance_step(state, workspace, step_id, f"学术搜索完成: {out.strip()}")

    elif step_id == "3d_gov_data":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        gov_plan = plan.get("gov_data_sources", [])
        plan_path = os.path.join(src, "gov_data_plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(gov_plan, f, ensure_ascii=False, indent=2)
        cmd = [
            py,
            os.path.join(scripts, "fetch_gov_data.py"),
            "--plan",
            plan_path,
            "--output",
            os.path.join(src, "gov_data.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"政府数据获取{'完成' if rc == 0 else '失败（已降级跳过）'}",
        )

    elif step_id == "3e_regulatory":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        reg_plan = plan.get("regulatory_filings", [])
        plan_path = os.path.join(src, "regulatory_plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(reg_plan, f, ensure_ascii=False, indent=2)
        cmd = [
            py,
            os.path.join(scripts, "fetch_regulatory_filings.py"),
            "--plan",
            plan_path,
            "--output",
            os.path.join(src, "regulatory_filings.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"监管文件获取{'完成' if rc == 0 else '失败（已降级跳过）'}",
        )

    elif step_id == "3f_weak_signals":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        ws_plan = plan.get("weak_signal_queries", [])
        plan_path = os.path.join(src, "weak_signals_plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(ws_plan, f, ensure_ascii=False, indent=2)
        cmd = [
            py,
            os.path.join(scripts, "fetch_weak_signals.py"),
            "--plan",
            plan_path,
            "--output",
            os.path.join(src, "weak_signals.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"弱信号采集{'完成' if rc == 0 else '失败（已降级跳过）'}",
        )

    elif step_id == "4_classify":
        cmd = [
            py,
            os.path.join(scripts, "classify_sources.py"),
            "--input",
            os.path.join(src, "raw_search_results.json"),
            "--config",
            config,
            "--tiers",
            tiers,
            "--output",
            os.path.join(src, "classified_sources.json"),
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            output_error(step_id, f"信源分类失败: {err}")
        advance_step(state, workspace, step_id, f"信源分类完成: {out.strip()}")

    elif step_id == "4.5_cross_source":
        cmd = [
            py,
            os.path.join(scripts, "cross_source_detect.py"),
            "--input",
            os.path.join(src, "raw_search_results.json"),
            "--output",
            os.path.join(src, "cross_source_map.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(state, workspace, step_id, "交叉信源检测完成")

    elif step_id == "3g_full_content":
        classified = safe_load_json(os.path.join(src, "classified_sources.json"), [])
        if isinstance(classified, list):
            urls = [s.get("url") for s in classified[:20] if s.get("url")]
        else:
            urls = []
        urls_path = os.path.join(src, "top_urls.json")
        with open(urls_path, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False)
        cmd = [
            py,
            os.path.join(scripts, "fetch_full_content.py"),
            "--urls-file",
            urls_path,
            "--output-dir",
            os.path.join(src, "full_content"),
            "--output",
            os.path.join(src, "full_content_summary.json"),
            "--max-sources",
            "20",
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"全文获取完成: {out.strip()}" if rc == 0 else "全文获取部分失败（已降级）",
        )

    # v5.2 新增：CRAAP 代码评分（Currency/Authority）
    elif step_id == "5a_craap_code":
        cmd = [
            py,
            os.path.join(scripts, "craap_code_score.py"),
            "--sources",
            os.path.join(src, "classified_sources.json"),
            "--config",
            config,
            "--tiers",
            tiers,
            "--output",
            os.path.join(src, "craap_code_scores.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"CRAAP 代码评分完成: {out.strip()}"
            if rc == 0
            else f"代码评分失败（已降级）: {err.strip()}",
        )

    elif step_id == "6_aggregate":
        plan = safe_load_json(os.path.join(src, "research_plan.json"))
        cw = str(plan.get("currency_weight", 0.2))
        cmd = [
            py,
            os.path.join(scripts, "aggregate_craap.py"),
            "--sources",
            os.path.join(src, "classified_sources.json"),
            "--scores",
            os.path.join(src, "craap_scores.json"),
            "--code-scores",
            os.path.join(src, "craap_code_scores.json"),  # v5.2 新增
            "--config",
            config,
            "--output",
            os.path.join(src, "filtered_sources.json"),
            "--stats",
            os.path.join(src, "eval_stats.json"),
            "--cross-source-map",
            os.path.join(src, "cross_source_map.json"),
            "--currency-weight",
            cw,
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            output_error(step_id, f"聚合过滤失败: {err}")
        advance_step(state, workspace, step_id, f"CRAAP 聚合过滤完成: {out.strip()}")

    elif step_id == "6.5_diversity":
        cmd = [
            py,
            os.path.join(scripts, "diversity_check.py"),
            "--sources",
            os.path.join(src, "filtered_sources.json"),
            "--config",
            config,
            "--output",
            os.path.join(src, "diversity_report.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(state, workspace, step_id, f"多样性检测完成: {out.strip()}")

    elif step_id == "8_quality_gate1":
        tri_path = os.path.join(ana, "triangulation.json")
        div_path = os.path.join(src, "diversity_report.json")
        con_path = os.path.join(ana, "contradiction_analysis.json")
        retry = state.get("search_retry", 0)
        cmd = [
            py,
            os.path.join(scripts, "quality_gate.py"),
            "check_sources",
            "--filtered",
            os.path.join(src, "filtered_sources.json"),
            "--stats",
            os.path.join(src, "eval_stats.json"),
            "--triangulation",
            tri_path,
            "--diversity",
            div_path,
            "--contradiction",
            con_path,
            "--config",
            config,
            "--retry-count",
            str(retry),
            "--warnings-output",
            os.path.join(src, "quality_warnings.json"),
        ]
        rc, out, err = run_script(cmd)
        if rc != 0 and retry < 2:
            state["search_retry"] = retry + 1
            # 回退到搜索步骤（找到 3a_search_web 的索引）
            for i, s in enumerate(STEPS):
                if s["id"] == "3a_search_web":
                    state["current_step_index"] = i
                    break
            save_state(workspace, state)
            output(
                {
                    "status": "retry",
                    "step": step_id,
                    "message": f"质量门控未通过，重试搜索（第{retry + 1}次）: {out.strip()}",
                    "retry_count": retry + 1,
                }
            )
        else:
            advance_step(state, workspace, step_id, f"质量门控1: {out.strip()}")

    # v5.2 新增：章节信源预匹配
    elif step_id == "9a_match_sources":
        cmd = [
            py,
            os.path.join(scripts, "match_sources_to_sections.py"),
            "--plan",
            os.path.join(src, "research_plan.json"),
            "--sources",
            os.path.join(src, "filtered_sources.json"),
            "--output",
            os.path.join(src, "section_source_map.json"),
        ]
        rc, out, err = run_script(cmd)
        advance_step(
            state,
            workspace,
            step_id,
            f"章节信源预匹配完成: {out.strip()}"
            if rc == 0
            else f"预匹配失败（已降级）: {err.strip()}",
        )

    elif step_id == "13_references":
        # 代码生成参考文献 HTML
        generate_references(workspace, state)
        advance_step(state, workspace, step_id, "参考文献生成完成")

    elif step_id == "14_merge_html":
        merge_html_fragments(workspace, state)
        advance_step(state, workspace, step_id, "HTML 片段合并完成")

    elif step_id == "15_sanitize":
        cmd = [
            py,
            os.path.join(scripts, "sanitize_html.py"),
            "--input",
            os.path.join(ana, "full_report.html"),
            "--output",
            os.path.join(ana, "clean_report.html"),
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            output_error(step_id, f"HTML 清理失败: {err}")
        advance_step(state, workspace, step_id, f"HTML 清理完成: {out.strip()}")

    elif step_id == "16_quality_gate2":
        retry = state.get("report_retry", 0)
        cmd = [
            py,
            os.path.join(scripts, "quality_gate.py"),
            "check_report",
            "--report",
            os.path.join(ana, "clean_report.html"),
            "--config",
            config,
            "--retry-count",
            str(retry),
            "--warnings-output",
            os.path.join(ana, "report_warnings.json"),
        ]
        rc, out, err = run_script(cmd)
        if rc != 0 and retry < 1:
            state["report_retry"] = retry + 1
            # v5.3 fix: fallback to 14_merge_html instead of 9b_write_sections
            # quality_gate2 checks report formatting (Markdown residue, word count, etc.),
            # section content is already written and should not be re-generated.
            # Falling back to 9b caused agent to auto-confirm LLM steps, emptying body files.
            for i, s in enumerate(STEPS):
                if s["id"] == "14_merge_html":
                    state["current_step_index"] = i
                    break
            save_state(workspace, state)
            output(
                {
                    "status": "retry",
                    "step": step_id,
                    "message": f"报告质量门控未通过，从合并步骤重试（正文已保留）: {out.strip()}",
                    "retry_count": retry + 1,
                }
            )
        else:
            advance_step(state, workspace, step_id, f"质量门控2: {out.strip()}")

    elif step_id == "17_render_all":
        # 三格式一次性渲染
        css = os.path.join(skill_dir, "templates", "styles.css")
        template = os.path.join(skill_dir, "templates", "report.html")
        out_dir = os.path.join(workspace, "output")
        clean = os.path.join(ana, "clean_report.html")
        errors = []

        # PDF
        cmd = [
            py,
            os.path.join(scripts, "render_pdf.py"),
            "--input",
            clean,
            "--template",
            template,
            "--css",
            css,
            "--output",
            out_dir + "/",
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            errors.append(f"PDF: {err.strip()}")
        # DOCX
        cmd = [
            py,
            os.path.join(scripts, "render_docx.py"),
            "--input",
            clean,
            "--output",
            out_dir + "/",
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            errors.append(f"DOCX: {err.strip()}")
        # Interactive HTML
        cmd = [
            py,
            os.path.join(scripts, "render_interactive.py"),
            "--input",
            clean,
            "--css",
            css,
            "--output",
            out_dir + "/",
        ]
        rc, out, err = run_script(cmd)
        if rc != 0:
            errors.append(f"HTML: {err.strip()}")

        if errors:
            msg = f"渲染完成（部分错误）: {'; '.join(errors)}"
        else:
            msg = "三格式渲染全部完成（PDF + DOCX + 交互式HTML）"
        advance_step(state, workspace, step_id, msg)

    else:
        output_error(step_id, f"未知的 CODE 步骤: {step_id}")


# =============================================================================
# LLM 步骤准备
# =============================================================================


def prepare_llm_step(step_id, state, workspace, skill_dir):
    topic = state["topic"]
    src = os.path.join(workspace, "sources")
    ana = os.path.join(workspace, "analysis")
    prompts_dir = os.path.join(skill_dir, "prompts")

    if step_id == "1_plan":
        prompt_file = os.path.join(prompts_dir, "01_plan.md")
        output_file = os.path.join(src, "research_plan.json")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {"{{TOPIC}}": topic},
                "output_file": output_file,
                "output_format": "json",
                "instruction": (
                    f"读取 prompt 文件 {prompt_file}，将 {{{{TOPIC}}}} 替换为「{topic}」，"
                    f"发送给系统 LLM，要求输出纯 JSON。"
                    f"将 LLM 返回的 JSON 保存到 {output_file}。"
                    f"保存后立即执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "2_mece":
        plan_path = os.path.join(src, "research_plan.json")
        prompt_file = os.path.join(prompts_dir, "02_mece_check.md")
        output_file = os.path.join(src, "mece_result.json")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {"{{PLAN_JSON}}": f"读取 {plan_path} 的内容"},
                "output_file": output_file,
                "output_format": "json",
                "instruction": (
                    f"读取 {prompt_file}，将 {{{{PLAN_JSON}}}} 替换为 {plan_path} 的内容，"
                    f"发送给系统 LLM。将结果保存到 {output_file}。"
                    f"如果 is_mece 为 false 且重试次数 < 2，回到步骤 1 重新生成计划。"
                    f"否则继续: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "5b_craap_llm":  # v5.2 改名
        prepare_craap_step(state, workspace, skill_dir)

    elif step_id == "7_triangulate":
        prompt_file = os.path.join(prompts_dir, "04_triangulate.md")
        output_file = os.path.join(ana, "triangulation.json")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{FACTS_JSON}}": f"从 {src}/filtered_sources.json 提取所有 key_facts",
                    "{{GOV_DATA}}": f"读取 {src}/gov_data.json（如不存在则为空对象）",
                    "{{REGULATORY_DATA}}": f"读取 {src}/regulatory_filings.json（如不存在则为空对象）",
                },
                "output_file": output_file,
                "output_format": "json",
                "instruction": (
                    f"读取 {prompt_file}，替换所有变量（从对应文件读取数据），"
                    f"发送给系统 LLM。将结果保存到 {output_file}。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "7.5_contradiction":
        prompt_file = os.path.join(prompts_dir, "10_contradiction_analysis.md")
        output_file = os.path.join(ana, "contradiction_analysis.json")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{FILTERED_SOURCES}}": f"读取 {src}/filtered_sources.json",
                    "{{TRIANGULATION}}": f"读取 {ana}/triangulation.json",
                    "{{GOV_DATA}}": f"读取 {src}/gov_data.json（如不存在则为空对象）",
                    "{{REGULATORY_FILINGS}}": f"读取 {src}/regulatory_filings.json（如不存在则为空对象）",
                },
                "output_file": output_file,
                "output_format": "json",
                "instruction": (
                    f"读取 {prompt_file}，替换所有变量，发送给系统 LLM。"
                    f"将结果保存到 {output_file}。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "7.6_cross_lang":
        prompt_file = os.path.join(prompts_dir, "11_cross_language_compare.md")
        output_file = os.path.join(ana, "cross_language.json")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{SOURCES_BY_LANGUAGE}}": f"从 {src}/filtered_sources.json 按 language 字段分组",
                },
                "output_file": output_file,
                "output_format": "json",
                "instruction": (
                    f"读取 {prompt_file}，替换变量（将 filtered_sources 按语言分组后作为 SOURCES_BY_LANGUAGE），"
                    f"发送给系统 LLM。将结果保存到 {output_file}。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "9b_write_sections":  # v5.2 改名
        prepare_write_sections(state, workspace, skill_dir)

    elif step_id == "10_exec_summary":
        prompt_file = os.path.join(prompts_dir, "06_write_exec_summary.md")
        output_file = os.path.join(ana, "exec_summary.html")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{CORE_QUESTION}}": "从 research_plan.json 读取 core_question",
                    "{{SECTION_SUMMARIES}}": f"读取 {ana}/sections/ 下所有章节文件的 analysis.core_argument 组成摘要",
                    "{{COUNTERINTUITIVE_FINDINGS}}": f"从 {ana}/contradiction_analysis.json 提取 counterintuitive_findings",
                },
                "output_file": output_file,
                "output_format": "html",
                "instruction": (
                    f"读取 {prompt_file}，替换所有变量，发送给系统 LLM。"
                    f"LLM 返回的是纯 HTML 片段（无 html/head/body 标签）。"
                    f"保存到 {output_file}。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "12_methodology":
        prompt_file = os.path.join(prompts_dir, "08_write_methodology.md")
        output_file = os.path.join(ana, "methodology.html")
        # v5.2: 新增去重统计
        dedup_stats_note = f"读取 {src}/dedup_stats.json（如不存在则为空）"
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{SEARCH_STATS}}": "搜索统计（总搜索数、各层结果数）",
                    "{{PASSED_SOURCES}}": f"从 {src}/eval_stats.json 读取",
                    "{{REJECTED_SOURCES}}": f"从 {src}/eval_stats.json 读取",
                    "{{T0_SOURCES}}": f"从 {src}/filtered_sources.json 筛选 tier=0 的信源",
                    "{{VERIFIED_POINTS}}": f"从 {ana}/triangulation.json 读取 verified_data_points 数量",
                    "{{CONFLICTING_POINTS}}": f"从 {ana}/triangulation.json 读取 conflicting_data_points",
                    "{{TIER_DISTRIBUTION}}": f"从 {src}/eval_stats.json 读取信源层级分布",
                    "{{DIVERSITY_REPORT}}": f"读取 {src}/diversity_report.json",
                    "{{WEAK_SIGNAL_STATS}}": f"读取 {src}/weak_signals.json 的统计（如不存在则为空）",
                    "{{GOV_DATA_STATS}}": f"读取 {src}/gov_data.json 的统计（如不存在则为空）",
                    "{{QUALITY_WARNINGS}}": f"读取 {src}/quality_warnings.json",
                    "{{DEDUP_STATS}}": dedup_stats_note,
                },
                "output_file": output_file,
                "output_format": "html",
                "instruction": (
                    f"读取 {prompt_file}，替换所有变量（从对应文件读取），"
                    f"发送给系统 LLM。保存 HTML 片段到 {output_file}。"
                    f"注意：v5.2 新增去重统计（{dedup_stats_note}），请在方法论中说明搜索去重策略。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    elif step_id == "12.5_verification":
        prompt_file = os.path.join(prompts_dir, "12_human_verification.md")
        output_file_json = os.path.join(ana, "human_verification.json")
        output_file_html = os.path.join(ana, "human_verification.html")
        output(
            {
                "status": "need_llm",
                "step": step_id,
                "prompt_file": prompt_file,
                "variables": {
                    "{{TOPIC}}": topic,
                    "{{SECTION_ANALYSES}}": f"读取 {ana}/sections/ 下所有章节分析摘要",
                    "{{TRIANGULATION}}": f"读取 {ana}/triangulation.json",
                    "{{CONTRADICTION_ANALYSIS}}": f"读取 {ana}/contradiction_analysis.json",
                    "{{WEAK_SIGNALS}}": f"读取 {src}/weak_signals.json（如不存在则为空）",
                    "{{SOURCE_STATS}}": f"读取 {src}/eval_stats.json",
                },
                "output_file": output_file_json,
                "output_format": "json",
                "instruction": (
                    f"读取 {prompt_file}，替换所有变量，发送给系统 LLM。"
                    f"将 JSON 结果保存到 {output_file_json}。"
                    f"然后根据 JSON 生成一个 HTML 片段（人工验证清单），使用 class='verification-checklist'，"
                    f"保存到 {output_file_html}。"
                    f"然后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                    f"confirm --workspace {workspace} --skill-dir {skill_dir} --step {step_id}"
                ),
            }
        )

    else:
        output_error(step_id, f"未知的 LLM 步骤: {step_id}")


def prepare_craap_step(state, workspace, skill_dir):
    """准备 CRAAP 评估 — 分 T1-2（快速提取）和 T3+（完整评估）两批
    v5.2: Currency 和 Authority 已由代码预计算，LLM 只评估 Relevance/Accuracy/Purpose
    """
    src = os.path.join(workspace, "sources")
    prompts_dir = os.path.join(skill_dir, "prompts")
    classified = safe_load_json(os.path.join(src, "classified_sources.json"), [])

    # 分批
    t0_sources = [s for s in classified if s.get("tier") == 0]  # 跳过
    t12_sources = [s for s in classified if s.get("tier") in (1, 2)]
    t345_sources = [s for s in classified if s.get("tier") in (3, 4, 5)]

    output(
        {
            "status": "need_llm",
            "step": "5b_craap_llm",
            "instruction": (
                f"CRAAP 评估分三部分执行：\n\n"
                f"**v5.2 重要变更**：Currency（时效性）和 Authority（权威性）已由代码预计算（见 craap_code_scores.json），"
                f"LLM 只需评估 Relevance（相关性）、Accuracy（准确性）、Purpose（目的性）三个维度。\n\n"
                f"1. T0 信源（{len(t0_sources)} 条）跳过评估，直接标记 craap_score=10.0\n\n"
                f"2. T1-2 信源（{len(t12_sources)} 条）使用快速提取模式：\n"
                f"   读取 {prompts_dir}/03a_craap_extract.md\n"
                f"   将 T1-2 信源列表作为 {{{{SOURCES_BATCH}}}} 替换\n"
                f"   发送给 LLM，获取 JSON Array 结果\n\n"
                f"3. T3-5 信源（{len(t345_sources)} 条）使用完整评估模式：\n"
                f"   读取 {prompts_dir}/03b_craap_batch.md\n"
                f"   将 T3-5 信源列表作为 {{{{SOURCES_BATCH}}}} 替换\n"
                f"   发送给 LLM，获取 JSON Array 结果\n\n"
                f"将所有评分结果合并为一个 JSON 对象（key 为 URL），保存到 {src}/craap_scores.json。\n"
                f'T0 信源的评分格式：{{"craap_score": 10.0, "relevance": {{"score": 10}}, "accuracy": {{"score": 10}}, "purpose": {{"score": 10}}, "key_facts": []}}\n\n'
                f"完成后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                f"confirm --workspace {workspace} --skill-dir {skill_dir} --step 5b_craap_llm"
            ),
            "sources_summary": {
                "t0_skip": len(t0_sources),
                "t12_fast": len(t12_sources),
                "t345_full": len(t345_sources),
            },
            "output_file": os.path.join(src, "craap_scores.json"),
        }
    )


def prepare_write_sections(state, workspace, skill_dir):
    """准备章节撰写 — 列出所有章节，agent 逐个撰写
    v5.2: 使用预匹配的信源映射，每章节只传递相关信源
    """
    src = os.path.join(workspace, "sources")
    ana = os.path.join(workspace, "analysis")
    prompts_dir = os.path.join(skill_dir, "prompts")

    plan = safe_load_json(os.path.join(src, "research_plan.json"))
    sections = plan.get("sections", [])
    state["sections"] = sections
    save_state(workspace, state)

    sections_dir = os.path.join(ana, "sections")
    os.makedirs(sections_dir, exist_ok=True)

    # v5.2: 加载信源预匹配映射
    section_source_map = safe_load_json(
        os.path.join(src, "section_source_map.json"), {}
    )
    has_source_map = bool(section_source_map)

    section_tasks = []
    for i, sec in enumerate(sections):
        title = sec.get("title", f"章节{i + 1}")
        purpose = sec.get("purpose", "")
        safe_title = re.sub(r'[\\/:*?"<>|]', "", title)[:20]
        matched_urls = section_source_map.get(title, [])
        section_tasks.append(
            {
                "index": i + 1,
                "title": title,
                "purpose": purpose,
                "analysis_file": os.path.join(
                    sections_dir, f"section_{i + 1}_analysis.json"
                ),
                "html_file": os.path.join(sections_dir, f"section_{i + 1}.html"),
                "matched_sources": matched_urls,  # v5.2 新增
            }
        )

    # v5.2: 信源预筛选说明
    source_instruction = ""
    if has_source_map:
        source_instruction = (
            f"   - {{{{SOURCE_MATERIALS}}}}: **仅使用该章节的预筛选信源**（见 matched_sources 列表）\n"
            f"     从 filtered_sources.json 中筛选 URL 在 matched_sources 列表中的信源\n"
        )
    else:
        source_instruction = (
            f"   - {{{{SOURCE_MATERIALS}}}}: 从 filtered_sources.json 筛选相关信源\n"
        )

    output(
        {
            "status": "need_llm",
            "step": "9b_write_sections",
            "prompt_file": os.path.join(prompts_dir, "09_analyze_and_write.md"),
            "sections": section_tasks,
            "instruction": (
                f"共 {len(sections)} 个章节需要逐个分析与撰写。\n\n"
                f"{'v5.2 优化：已预匹配每章节的相关信源，请只使用预筛选信源。' if has_source_map else ''}\n\n"
                f"对每个章节：\n"
                f"1. 读取 {prompts_dir}/09_analyze_and_write.md\n"
                f"2. 替换模板变量：\n"
                f"   - {{{{TOPIC}}}}: {state['topic']}\n"
                f"   - {{{{CORE_QUESTION}}}}: 从 research_plan.json 读取\n"
                f"   - {{{{SECTION_TITLE}}}}: 章节标题\n"
                f"   - {{{{SECTION_PURPOSE}}}}: 章节目的\n"
                f"   - {{{{KEY_DATA_POINTS}}}}: 从对应信源筛选 key_facts\n"
                + source_instruction
                + f"   - {{{{TRIANGULATION}}}}: 从 {ana}/triangulation.json 读取\n"
                f"   - {{{{GOV_DATA}}}}: 从 {src}/gov_data.json 读取相关数据\n"
                f"   - {{{{REGULATORY_FILINGS}}}}: 从 {src}/regulatory_filings.json 读取\n"
                f"   - {{{{CONTRADICTION_ANALYSIS}}}}: 从 {ana}/contradiction_analysis.json 读取\n"
                f"   - {{{{WEAK_SIGNALS}}}}: 从 {src}/weak_signals.json 读取\n"
                f"3. 发送给 LLM，获取 JSON（包含 analysis 和 html 两个字段）\n"
                f"4. 将完整 JSON 保存到 analysis_file\n"
                f"5. 将 html 字段内容单独保存到 html_file\n\n"
                f"章节列表：\n"
                + "\n".join(
                    [
                        f"  {t['index']}. {t['title']} → {t['html_file']}"
                        + (
                            f" (预匹配 {len(t['matched_sources'])} 条信源)"
                            if t["matched_sources"]
                            else ""
                        )
                        for t in section_tasks
                    ]
                )
                + f"\n\n如果章节 >= 4 个，可以使用 subagent 并行撰写。\n"
                f"全部章节完成后执行: python3 {os.path.join(skill_dir, 'scripts', 'run_research.py')} "
                f"confirm --workspace {workspace} --skill-dir {skill_dir} --step 9b_write_sections"
            ),
        }
    )


# =============================================================================
# 确认步骤完成
# =============================================================================


def cmd_confirm(args):
    workspace = os.path.abspath(args.workspace)
    skill_dir = os.path.abspath(args.skill_dir)
    step_id = args.step

    state = load_state(workspace)
    if not state:
        output_error("confirm", "未找到状态文件")

    # 步骤 1 完成后需要提取 data_sources 和 sections
    if step_id == "1_plan":
        plan_path = os.path.join(workspace, "sources", "research_plan.json")
        plan = safe_load_json(plan_path)
        state["data_sources"] = plan.get("data_sources", {})
        state["sections"] = plan.get("sections", [])

    # 标记完成并推进
    advance_step(state, workspace, step_id, f"LLM 步骤 {step_id} 已确认完成")


# =============================================================================
# v5.2 新增：status 子命令
# =============================================================================


def cmd_status(args):
    workspace = os.path.abspath(args.workspace)

    state = load_state(workspace)
    if not state:
        output(
            {
                "status": "no_state",
                "message": "未找到 driver_state.json，请先运行 init",
                "can_resume": False,
            }
        )
        return

    idx = state.get("current_step_index", 0)
    completed = state.get("completed_steps", [])
    skipped = state.get("skipped_steps", [])

    if idx >= len(STEPS):
        current_step = "completed"
        phase = "DONE"
        can_resume = False
    else:
        current_step = STEPS[idx]["id"]
        phase = STEPS[idx]["phase"]
        can_resume = True

    status_data = {
        "status": "progress",
        "current_step": current_step,
        "progress": f"{idx}/{len(STEPS)}",
        "completed": len(completed),
        "skipped": len(skipped),
        "phase": phase,
        "elapsed_steps": completed,
        "skipped_steps": skipped,
        "can_resume": can_resume,
        "topic": state.get("topic", ""),
        "version": state.get("version", "5.1.0"),
    }

    output(status_data)


# =============================================================================
# 辅助函数
# =============================================================================


def extract_keywords(kw_list):
    """从 {"keyword": "...", "lang": "xx"} 格式提取纯关键词列表"""
    keywords = []
    for item in kw_list:
        if isinstance(item, dict):
            keywords.append(item.get("keyword", ""))
        elif isinstance(item, str):
            keywords.append(item)
    return [k for k in keywords if k]


def execute_search_web(state, workspace, skill_dir, py, scripts, src):
    """执行 6 层 Web 搜索"""
    plan = safe_load_json(os.path.join(src, "research_plan.json"))
    search_kws = plan.get("search_keywords", {})
    freshness = plan.get("freshness_policy", {})
    layers = [
        "background",
        "authority",
        "timeliness",
        "academic",
        "regulatory",
        "weak_signal",
    ]

    all_results = []
    for layer in layers:
        kws = search_kws.get(layer, [])
        if not kws:
            continue
        keywords = extract_keywords(kws)
        kw_path = os.path.join(src, f"{layer}_keywords.json")
        with open(kw_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False)

        fresh = freshness.get(layer, "")
        cmd = [
            py,
            os.path.join(scripts, "search_sources.py"),
            "web",
            "--keywords-file",
            kw_path,
            "--layer",
            layer,
            "--max-results",
            "10",
            "--output",
            os.path.join(src, f"{layer}_results.json"),
        ]
        if fresh:
            cmd.extend(["--freshness-days", str(fresh)])
        rc, out, err = run_script(cmd)
        # 加载结果
        layer_results = safe_load_json(os.path.join(src, f"{layer}_results.json"), [])
        if isinstance(layer_results, list):
            all_results.extend(layer_results)

    # 保存合并结果
    with open(os.path.join(src, "raw_search_results.json"), "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    advance_step(
        state,
        workspace,
        "3a_search_web",
        f"6 层 Web 搜索完成，共 {len(all_results)} 条结果",
    )


def merge_results(src, filename):
    """将额外结果合并到 raw_search_results.json"""
    raw_path = os.path.join(src, "raw_search_results.json")
    extra_path = os.path.join(src, filename)

    raw = safe_load_json(raw_path, [])
    extra = safe_load_json(extra_path, [])

    if isinstance(raw, list) and isinstance(extra, list):
        raw.extend(extra)
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)


def generate_references(workspace, state):
    """从 filtered_sources 生成参考文献 HTML"""
    src = os.path.join(workspace, "sources")
    ana = os.path.join(workspace, "analysis")
    sources = safe_load_json(os.path.join(src, "filtered_sources.json"), [])

    refs = ["<h2>参考文献</h2>", '<ol class="references">']
    for i, s in enumerate(sources, 1):
        title = s.get("title", "未知标题")
        url = s.get("url", "#")
        tier = s.get("tier", 5)
        domain = s.get("domain", "")
        tier_badge = f'<span class="tier-badge t{tier}">T{tier}</span>'
        refs.append(
            f"<li>{title} {tier_badge} "
            f'<a href="{url}" target="_blank">{domain}</a> '
            f'<span class="ref-meta">CRAAP: {s.get("craap_score", "N/A")}</span></li>'
        )
    refs.append("</ol>")

    ref_html = "\n".join(refs)
    with open(os.path.join(ana, "references.html"), "w", encoding="utf-8") as f:
        f.write(ref_html)


def merge_html_fragments(workspace, state):
    """合并所有 HTML 片段为完整报告

    v5.3 fix: validate that fragment files are non-empty before merging,
    preventing silent generation of body-less reports.
    """
    ana = os.path.join(workspace, "analysis")
    topic = state["topic"]
    empty_warnings = []

    parts = []
    # 1. 标题
    parts.append(f'<h1 class="report-title">{topic}</h1>')
    parts.append(
        f'<div class="report-meta">Deep Research Report · 2026年3月 '
        f'<span class="version-badge">v5.3</span></div>'
    )
    parts.append('<div class="report-meta">⚠ 本报告仅供研究参考，不构成投资建议</div>')

    # 2. 执行摘要
    exec_path = os.path.join(ana, "exec_summary.html")
    if os.path.exists(exec_path):
        content = _read_and_check(exec_path, "执行摘要", empty_warnings)
        if content:
            parts.append(content)

    # 3. 各章节
    sections_dir = os.path.join(ana, "sections")
    non_empty_sections = 0
    if os.path.exists(sections_dir):
        section_files = sorted(
            [
                f
                for f in os.listdir(sections_dir)
                if f.startswith("section_") and f.endswith(".html")
            ]
        )
        for sf in section_files:
            content = _read_and_check(
                os.path.join(sections_dir, sf), f"章节文件 {sf}", empty_warnings
            )
            if content:
                parts.append(content)
                non_empty_sections += 1

    # 4. 研究方法
    meth_path = os.path.join(ana, "methodology.html")
    if os.path.exists(meth_path):
        content = _read_and_check(meth_path, "研究方法", empty_warnings)
        if content:
            parts.append(content)

    # 5. 人工验证清单
    verify_path = os.path.join(ana, "human_verification.html")
    if os.path.exists(verify_path):
        content = _read_and_check(verify_path, "人工验证清单", empty_warnings)
        if content:
            parts.append(content)

    # 6. 参考文献
    ref_path = os.path.join(ana, "references.html")
    if os.path.exists(ref_path):
        content = _read_and_check(ref_path, "参考文献", empty_warnings)
        if content:
            parts.append(content)

    # v5.3: output empty-file warnings to stderr and a warnings file
    if empty_warnings:
        warn_msg = (
            f"[WARN] merge_html_fragments: 发现 {len(empty_warnings)} 个空/无效片段文件:\n"
            + "\n".join(f"  - {w}" for w in empty_warnings)
        )
        print(warn_msg, file=sys.stderr)
        # save warnings for downstream steps
        warn_path = os.path.join(ana, "merge_warnings.json")
        with open(warn_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "empty_fragments": empty_warnings,
                    "non_empty_sections": non_empty_sections,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    if non_empty_sections == 0 and os.path.exists(sections_dir):
        print(
            "[ERROR] merge_html_fragments: 所有章节文件均为空！报告将缺失正文。",
            file=sys.stderr,
        )

    full_html = "\n\n".join(parts)
    with open(os.path.join(ana, "full_report.html"), "w", encoding="utf-8") as f:
        f.write(full_html)


def _read_and_check(filepath, label, warnings_list):
    """Read an HTML fragment file and check whether it is empty.

    Returns file content (if non-empty) or None (if empty/invalid),
    appending a warning to warnings_list when appropriate.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        warnings_list.append(f"{label}: 读取失败 ({e})")
        return None

    stripped = content.strip()
    if not stripped:
        warnings_list.append(f"{label}: 文件为空 ({filepath})")
        return None
    # check for files containing only empty HTML tags (e.g. <div></div>)
    text_only = re.sub(r"<[^>]*>", "", stripped).strip()
    if not text_only:
        warnings_list.append(
            f"{label}: 文件仅包含空 HTML 标签，无实际内容 ({filepath})"
        )
        return None
    return content


# =============================================================================
# 主入口
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Harness Research v5.3 State Machine Driver"
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    sp_init = subparsers.add_parser("init")
    sp_init.add_argument("--topic", required=True)
    sp_init.add_argument("--workspace", required=True)
    sp_init.add_argument("--skill-dir", required=True)

    # next
    sp_next = subparsers.add_parser("next")
    sp_next.add_argument("--workspace", required=True)
    sp_next.add_argument("--skill-dir", required=True)

    # confirm (LLM 步骤完成后调用)
    sp_confirm = subparsers.add_parser("confirm")
    sp_confirm.add_argument("--workspace", required=True)
    sp_confirm.add_argument("--skill-dir", required=True)
    sp_confirm.add_argument("--step", required=True)

    # v5.2 新增：status
    sp_status = subparsers.add_parser("status")
    sp_status.add_argument("--workspace", required=True)
    sp_status.add_argument("--skill-dir", required=True)

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "next":
        cmd_next(args)
    elif args.command == "confirm":
        cmd_confirm(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

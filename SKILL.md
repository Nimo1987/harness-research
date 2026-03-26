# Harness Research v5.2

多层数据源直接访问型知识发现引擎。**程序驱动模式**：由 `run_research.py` 状态机严格控制 30 步流程，agent 仅负责执行 LLM 推理和中间结果读写。

v5.2 升级要点：Currency/Authority 代码化评分（降 LLM 调用量 30-40%）、章节信源预筛选（降 prompt 长度 40-50%）、搜索去重前置、报告一致性检查。

## CRITICAL — 执行纪律

> 以下规则优先级高于所有流程步骤。

### 核心原则：程序驱动，agent 服从

1. **NEVER 自行决定下一步**：所有步骤顺序由 `run_research.py` 状态机控制。agent 禁止跳步、改序、遗漏。
2. **NEVER 等待汇报**：等待 shell 命令返回时，禁止发送任何过渡性消息。
3. **NEVER 上下文堆积**：禁止将超过 500 tokens 的中间结果保留在对话上下文中。
4. **ALWAYS 结果直写**：所有中间结果立即写入文件，后续步骤通过 `read` 工具按需读取。
5. **ALWAYS 静默执行**：仅在任务启动、任务完成、需要用户决策时向用户发消息。
6. **ALWAYS 信任驱动脚本**：当驱动脚本返回 `done_code` + `next: true`，立即调用 `next`；返回 `need_llm`，执行 LLM 步骤后调用 `confirm`。

### 上下文管理规则

7. 搜索结果保存后禁止在后续 prompt 中内联完整内容。
8. CRAAP 评分保存后只引用统计摘要。
9. 章节 HTML 保存后只保留 `{标题: 文件路径}` 索引。
10. 主 agent 上下文全程不超过 30K tokens。

### Subagent 使用原则

11. 只在驱动脚本明确允许时使用 subagent（章节撰写步骤 9b_write_sections，且章节 ≥ 4）。
12. 以下任务禁止使用 subagent：CRAAP 评估、三角验证、执行摘要、研究方法。
13. Spawn subagent 后主 agent 继续调用 `next` 推进不依赖该结果的后续步骤。

### 断点续传与恢复

14. 如果用户说"继续"或"恢复"，检查工作目录下是否存在 `driver_state.json`：
    - 如果存在且 status != completed，直接调用 `next` 继续
    - 如果不存在，提示用户先 `init`
15. 可通过 `status` 子命令查看当前进度：
    ```bash
    python3 $SKILL_DIR/scripts/run_research.py status --workspace $WORKSPACE --skill-dir $SKILL_DIR
    ```

## 触发条件

当用户要求进行深度调研、行业分析、市场研究、技术评估或任何需要多信源交叉验证的研究任务时，使用此 Skill。

## 环境准备（仅首次）

```bash
pip install weasyprint python-docx beautifulsoup4 pyyaml requests lxml feedparser openpyxl python-dateutil
```

## 执行流程（程序驱动模式）

> agent 只需执行 3 种命令：`init`（初始化）、`next`（推进）、`confirm`（确认 LLM 步骤完成）。

### 第一步：初始化

```bash
SKILL_DIR={SKILL_DIR}
WORKSPACE={workspace}/deep-research-{topic_slug}
python3 $SKILL_DIR/scripts/run_research.py init \
  --topic "用户的研究主题" \
  --workspace $WORKSPACE \
  --skill-dir $SKILL_DIR
```

### 第二步：循环推进

驱动脚本返回 JSON，agent 根据 `status` 字段执行对应动作：

#### status = "done_code"（代码步骤已完成）

驱动脚本已自行执行完一个纯代码步骤。检查 `next` 字段：
- `next: true` → 立即调用 `next` 继续
- `next: false` + `all_done: true` → 流程结束

```bash
python3 $SKILL_DIR/scripts/run_research.py next \
  --workspace $WORKSPACE --skill-dir $SKILL_DIR
```

#### status = "need_llm"（需要 LLM 执行）

驱动脚本准备好了 prompt 和变量，agent 需要：
1. 读取 `instruction` 字段，按其指示执行 LLM 调用
2. 将 LLM 输出保存到 `output_file` 指定的路径
3. 调用 `confirm` 标记完成：

```bash
python3 $SKILL_DIR/scripts/run_research.py confirm \
  --workspace $WORKSPACE --skill-dir $SKILL_DIR --step {step_id}
```

#### status = "retry"（需要重试）

质量门控未通过，驱动脚本已自动回退到正确的步骤。agent 调用 `next` 继续：

```bash
python3 $SKILL_DIR/scripts/run_research.py next \
  --workspace $WORKSPACE --skill-dir $SKILL_DIR
```

#### status = "completed"（全部完成）

所有步骤已执行完毕。将 `output_dir` 下的文件交付给用户（PDF + DOCX + 交互式 HTML）。

### 第三步：交付

将 `{workspace}/output/` 下的 **PDF + DOCX + 交互式 HTML** 三格式文件交付给用户。

## 驱动脚本管理的 30 步流程

> agent 无需记忆以下步骤，驱动脚本会自动按顺序执行。

| # | 步骤 ID | 类型 | 说明 |
|---|--------|------|------|
| 1 | 1_plan | LLM | 生成研究计划 |
| 2 | 2_mece | LLM | MECE 自检 |
| 3 | 3a_search_web | CODE | 6 层 Web 搜索 |
| 4 | 3a2_dedup | CODE | **v5.2** 搜索去重前置 |
| 5 | 3b_finance | CODE | 金融数据获取（条件） |
| 6 | 3c_academic | CODE | 学术搜索 |
| 7 | 3d_gov_data | CODE | 政府数据获取（条件） |
| 8 | 3e_regulatory | CODE | 监管文件获取（条件） |
| 9 | 3f_weak_signals | CODE | 弱信号采集（条件） |
| 10 | 4_classify | CODE | 信源分类 |
| 11 | 4.5_cross_source | CODE | 交叉信源检测 |
| 12 | 3g_full_content | CODE | Top 20 全文获取 |
| 13 | 5a_craap_code | CODE | **v5.2** CRAAP 代码评分（Currency/Authority） |
| 14 | 5b_craap_llm | LLM | CRAAP LLM 评估（Relevance/Accuracy/Purpose，prompt 缩减 35%） |
| 15 | 6_aggregate | CODE | 聚合与过滤（合并代码评分 + LLM 评分） |
| 16 | 6.5_diversity | CODE | 多样性检测 |
| 17 | 7_triangulate | LLM | 三角验证 |
| 18 | 7.5_contradiction | LLM | 矛盾信号分析 |
| 19 | 7.6_cross_lang | LLM | 跨语言框架对比 |
| 20 | 8_quality_gate1 | CODE | 质量门控 1 |
| 21 | 9a_match_sources | CODE | **v5.2** 章节信源预匹配 |
| 22 | 9b_write_sections | LLM | 逐章分析与撰写（prompt 缩减 40-50%） |
| 23 | 10_exec_summary | LLM | 执行摘要 |
| 24 | 12_methodology | LLM | 研究方法与局限性 |
| 25 | 12.5_verification | LLM | 人工验证清单 |
| 26 | 13_references | CODE | 生成参考文献 |
| 27 | 14_merge_html | CODE | 合并 HTML 片段 |
| 28 | 15_sanitize | CODE | 清理 Markdown 残留 |
| 29 | 16_quality_gate2 | CODE | 报告质量门控（v5.2 增强一致性检查） |
| 30 | 17_render_all | CODE | **三格式一次性渲染**（PDF + DOCX + HTML） |

**LLM 步骤数**：10 步（与 v5.1 相同）
**CODE 步骤数**：20 步（v5.1 为 17 步，+3）

## 重要约束

1. 搜索脚本和 fetch_*.py 只做 API 调用和数据格式化，不含 LLM 推理。
2. 所有 LLM 交互通过系统主模型，Skill 只提供 prompt 模板。
3. 搜索降级链：**Tavily → Brave → DuckDuckGo**（3 级）。
4. 学术搜索：**arXiv + Semantic Scholar + PubMed**（3 源）。
5. 政府数据：**10 源直接 API 访问**。
6. 输出禁止 Markdown 表格语法，所有表格必须是 HTML `<table>`。
7. 搜索返回空结果时跳过继续，不中断流程。
8. 质量门控和重试由驱动脚本自动管理，agent 无需判断。
9. 渲染步骤已合并为一步（17_render_all），三格式一次产出，不可能遗漏。
10. 上下文卸载规则：保存到文件后禁止内联引用完整内容。主 agent 上下文全程 ≤ 30K tokens。

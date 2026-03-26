# Harness Research

**[English](README.md)**

基于**线束工程（Harness Engineering）**范式构建的状态机驱动型深度研究引擎 —— 一个从探索 AI Agent 开发新模式中诞生的实践产品。

核心理念：不让 LLM 决定下一步做什么。整个 30 步研究流水线由确定性状态机控制，AI agent 只做它擅长的事：对文本进行推理。搜索、评分、过滤、渲染 —— 全部用纯代码完成。

## 功能概述

给它一个研究主题，获得三种格式的专业研究报告（PDF + DOCX + 交互式 HTML），报告背后是：

- **6 层搜索** — 覆盖网页、学术、政府、监管、金融和弱信号源
- **530+ 域名分级** — T0-T5 六级信源可信度体系
- **CRAAP 评估** — 混合代码+LLM评分（时效性/权威性由代码计算，相关性/准确性/目的性由LLM评估）
- **三角验证** — 多信源交叉验证，含政府数据对照
- **矛盾分析** — 主动发现反直觉洞察
- **信息茧房检测** — 5 维多样性评分
- **质量门控** — 信源质量不达标时自动重试

## 架构：线束工程的落地实践

本项目是 **Harness Skill** 模式的实际实现：

```
传统方式:    LLM 决定一切 → 不可预测、成本高
线束方式:    代码编排、LLM 推理 → 确定性、高效
```

`run_research.py` 状态机：
- 严格定义 30 步执行顺序（10 步 LLM + 20 步 CODE）
- CODE 步骤直接执行（搜索、评分、过滤、渲染）
- LLM 步骤提供精确的 prompt、变量和输出格式
- 自动管理重试、质量门控和降级策略

Agent 只需做三件事：`init` → 循环 `next` / `confirm` → 直到 `completed`。

**效果**：零步骤遗漏。确定性执行。相比全 LLM 驱动方案，token 成本降低 35-40%。

## 成本与时间估算

| 指标 | 典型范围 |
|------|---------|
| **总 LLM Token 消耗** | 90K - 130K tokens / 次研究 |
| **端到端耗时** | 14 - 20 分钟 |
| **LLM 步骤数** | 10 步（总共 30 步） |
| **评估信源数** | 30 - 60 条 / 次研究 |

> Token 消耗取决于主题复杂度和搜索到的信源数量。v5.2 的混合 CRAAP 评分和信源预匹配机制，相比 v5.0 减少了约 35-40% 的 LLM token 消耗。

## 环境要求

### 运行环境

这是一个 **Harness Skill**，设计为在支持 Skill/工具编排的 AI Agent 中运行：

- **任何能执行 Shell 命令并解析 JSON 指令的 LLM Agent**

### 系统依赖

- Python 3.9+
- PDF 渲染的系统依赖：
  ```bash
  # macOS
  brew install pango libffi

  # Ubuntu/Debian
  sudo apt-get install libpango1.0-dev libffi-dev
  ```

### Python 依赖

```bash
pip install -r requirements.txt
```

### API Key 配置

复制 `.env.example` 为 `.env` 并填入你的 Key：

```bash
cp .env.example .env
```

| Key | 是否必需 | 是否免费 | 用途 |
|-----|---------|---------|------|
| `TAVILY_API_KEY` | **必需** | 有免费额度 | 主搜索引擎 |
| `BRAVE_API_KEY` | 推荐 | 有免费额度 | 搜索降级备选 |
| `FRED_API_KEY` | 可选 | 免费 | 美国经济数据 |
| `PUBMED_API_KEY` | 可选 | 免费 | 生物医学文献 |
| `SEC_EDGAR_USER_AGENT` | 可选 | 免费（只需邮箱） | SEC 监管文件 |
| `TUSHARE_TOKEN` | 可选 | 有免费额度 | 中国 A 股数据 |
| `SEMANTIC_SCHOLAR_KEY` | 可选 | 无 Key 可用 | 学术搜索 |

> **DuckDuckGo** 作为最终搜索降级方案，无需 Key。系统会优雅降级 —— 缺少的可选 Key 只会跳过对应数据源，不影响整体流程。

## 快速开始

### 作为 Harness Skill 使用

1. 将本目录放到 agent 的 Skill 目录下
2. Agent 读取 `SKILL.md` 并遵循状态机协议：

```bash
# 初始化
python3 scripts/run_research.py init \
  --topic "你的研究主题" \
  --workspace /path/to/workspace \
  --skill-dir /path/to/harness-research

# Agent 循环调用:
python3 scripts/run_research.py next --workspace ... --skill-dir ...
# → 返回 JSON: {"status": "done_code", "next": true} 或 {"status": "need_llm", ...}

# 随时查看进度:
python3 scripts/run_research.py status --workspace ... --skill-dir ...
```

### 30 步流水线

| 阶段 | 步骤 | 类型 | 说明 |
|------|------|------|------|
| **计划** | 1-2 | LLM | 研究计划 + MECE 验证 |
| **搜索** | 3-9 | CODE | 6 层搜索 + 去重 + 金融/学术/政府/监管/弱信号 |
| **评估** | 10-16 | 混合 | 信源分类 + CRAAP（代码+LLM）+ 聚合 + 多样性检测 |
| **验证** | 17-20 | 混合 | 三角验证 + 矛盾分析 + 跨语言对比 + 质量门控 |
| **撰写** | 21-25 | 混合 | 信源预匹配 + 逐章撰写 + 执行摘要 + 研究方法 |
| **渲染** | 26-30 | CODE | 参考文献 + 合并 + 清理 + 质量门控 + 三格式渲染 |

## 输出物

每次研究在 `output/` 目录下生成三个文件：

- **PDF** — 可打印报告，含表格分页优化
- **DOCX** — 可编辑文档，方便二次加工
- **交互式 HTML** — 侧边栏导航、可折叠章节、Chart.js 图表、表格排序、暗色/亮色主题切换

## 线束工程在本项目中的体现

核心洞察：**不要让 LLM 编排流程 —— 让代码编排 LLM。**

| 关注点 | 传统方式 | 线束方式 |
|--------|---------|---------|
| 步骤顺序 | LLM 自行决定 | 状态机强制执行 |
| 时效性评分 | LLM 猜测 | 代码根据日期计算 |
| 权威性评分 | LLM 猜测 | 代码查域名数据库映射 |
| 信源-章节匹配 | LLM 选择（有位置偏差） | TF-IDF + Jaccard（无偏差） |
| 搜索去重 | LLM 处理或延后 | 代码在搜索后立即执行 |
| 质量控制 | 听天由命 | 自动门控 + 重试循环 |
| 报告一致性 | 人工检查 | 代码检查（孤立引用、置信度分布） |

这不是要替代 LLM —— 而是让 LLM 做它有价值的事（推理、分析、写作），其他所有事都用确定性代码完成。

## 参与贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[Apache License 2.0](LICENSE)

## 致谢

由 [Jiaqi](https://github.com/Nimo1987) 通过线束工程（Harness Engineering）实践构建 —— 围绕 LLM 能力构建确定性编排框架的工程方法论。

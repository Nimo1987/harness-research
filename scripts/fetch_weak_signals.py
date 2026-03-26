#!/usr/bin/env python3
"""
弱信号数据采集脚本 (v5.0 新增)

信号类型：
  - 专利动态 (PatentsView API + Google Patents 搜索)
  - 招聘信号 (通过搜索引擎 site:linkedin.com/jobs)
  - 政府采购 (中国政府采购网)
  - 学术热度趋势 (arXiv + Semantic Scholar 按月统计)

用法：
  python fetch_weak_signals.py --type patents --query "artificial intelligence" --output patents.json
  python fetch_weak_signals.py --type hiring --company "美团" --keywords "即时零售" --output hiring.json
  python fetch_weak_signals.py --type procurement --query "人工智能" --output procurement.json
  python fetch_weak_signals.py --type academic_trend --query "large language model" --months 24 --output trends.json

  # 批量获取（从 JSON 计划文件）
  python fetch_weak_signals.py --plan weak_signals_plan.json --output weak_signals.json

注意：弱信号不作为报告正文直接论据，而是作为「分析提示」注入章节分析 prompt。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta


TIMEOUT = 30
USER_AGENT = "DeepResearchPro/5.0 (research-tool)"


def _get(url, params=None, headers=None, timeout=TIMEOUT):
    """统一 HTTP GET"""
    import requests

    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp


def _normalize_signal(signal_type, query, data_point, significance="", raw_data=None):
    """统一输出格式"""
    return {
        "signal_type": signal_type,
        "query": query,
        "data_point": data_point,
        "significance": significance,
        "fetch_time": datetime.now().isoformat(),
        "raw_data": raw_data or {},
        "is_weak_signal": True,
        "note": "弱信号，需持续跟踪验证",
    }


# ===========================================================================
# 专利动态 — PatentsView API (USPTO)
# ===========================================================================


def fetch_patents_patentsview(query, years=3, max_results=50):
    """
    PatentsView API — 按关键词/技术分类查询美国专利
    https://api.patentsview.org/patents/query
    """
    results = []
    try:
        url = "https://api.patentsview.org/patents/query"

        # 构建查询
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        payload = {
            "q": {
                "_and": [
                    {"_text_any": {"patent_abstract": query}},
                    {"_gte": {"patent_date": start_date}},
                ]
            },
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "assignee_organization",
                "inventor_first_name",
                "inventor_last_name",
            ],
            "o": {"per_page": min(max_results, 100)},
            "s": [{"patent_date": "desc"}],
        }

        import requests

        resp = requests.post(
            url, json=payload, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        # 按年统计趋势
        year_counts = {}
        for patent in patents:
            date = patent.get("patent_date", "")
            if date:
                year = date[:4]
                year_counts[year] = year_counts.get(year, 0) + 1

        # 添加趋势摘要
        if year_counts:
            sorted_years = sorted(year_counts.items())
            trend_text = ", ".join(f"{y}: {c}件" for y, c in sorted_years)
            results.append(
                _normalize_signal(
                    signal_type="patent_trend",
                    query=query,
                    data_point=f"美国专利趋势 (总计{total}件匹配): {trend_text}",
                    significance=_analyze_patent_trend(sorted_years),
                    raw_data={"total": total, "by_year": dict(sorted_years)},
                )
            )

        # 添加关键专利
        for patent in patents[:10]:
            assignees = patent.get("assignees", [])
            org = assignees[0].get("assignee_organization", "") if assignees else ""
            results.append(
                _normalize_signal(
                    signal_type="patent",
                    query=query,
                    data_point=f"[{patent.get('patent_date', '')}] {org}: {patent.get('patent_title', '')}",
                    significance="专利申请反映技术研发方向",
                    raw_data={
                        "patent_number": patent.get("patent_number", ""),
                        "title": patent.get("patent_title", ""),
                        "date": patent.get("patent_date", ""),
                        "assignee": org,
                        "abstract": patent.get("patent_abstract", "")[:500],
                    },
                )
            )

        print(f"  [PatentsView] '{query}' → {total} 件专利, 返回 {len(results)} 条信号")
    except Exception as e:
        print(f"  [PatentsView] '{query}' 失败: {e}")

    return results


def _analyze_patent_trend(sorted_years):
    """分析专利趋势方向"""
    if len(sorted_years) < 2:
        return "数据不足，无法判断趋势"
    counts = [c for _, c in sorted_years]
    if counts[-1] > counts[0] * 1.5:
        return "专利申请量显著上升，提示技术布局加速（提前18-24个月预示技术方向）"
    elif counts[-1] < counts[0] * 0.7:
        return "专利申请量下降，可能表明技术成熟或研发方向转移"
    else:
        return "专利申请量基本稳定"


# ===========================================================================
# 招聘信号 — 通过搜索引擎查询
# ===========================================================================


def fetch_hiring_signals(company, keywords, search_func=None):
    """
    通过搜索引擎查找招聘信号
    查询模式: "{company} {keywords} site:linkedin.com/jobs" 或通用搜索
    """
    results = []

    # 构建搜索查询
    queries = [
        f"{company} {keywords} site:linkedin.com/jobs",
        f"{company} {keywords} 招聘",
        f"{company} {keywords} hiring",
    ]

    for query in queries:
        try:
            # 使用搜索引擎（需要在 SKILL.md 中由编排层调用 search_sources.py）
            # 这里记录需要搜索的查询，实际搜索由编排层执行
            results.append(
                _normalize_signal(
                    signal_type="hiring_query",
                    query=query,
                    data_point=f"招聘搜索查询: {query}",
                    significance="招聘岗位异常变化可提前6-12个月预示战略转型",
                    raw_data={"search_query": query, "needs_search_engine": True},
                )
            )
        except Exception as e:
            print(f"  [招聘] 查询生成失败: {e}")

    print(f"  [招聘] '{company}' → {len(results)} 条查询信号")
    return results


# ===========================================================================
# 政府采购 — 中国政府采购网
# ===========================================================================


def fetch_procurement(query, max_results=20):
    """
    中国政府采购网 (ccgp.gov.cn) 中标公告搜索

    注意：该网站为公开页面，通过搜索接口获取结构化数据
    """
    results = []

    try:
        url = "http://search.ccgp.gov.cn/bxsearch"
        params = {
            "searchtype": 1,
            "page_index": 1,
            "bidSort": 0,
            "buyerName": "",
            "projectId": "",
            "pinMu": 0,
            "bidType": 7,  # 中标公告
            "dbselect": "bidx",
            "kw": query,
            "start_time": (datetime.now() - timedelta(days=365)).strftime("%Y:%m:%d"),
            "end_time": datetime.now().strftime("%Y:%m:%d"),
            "timeType": 2,
            "displayZone": "",
            "zoneId": "",
            "pppStatus": 0,
            "agession": "",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "http://search.ccgp.gov.cn/",
        }

        resp = _get(url, params=params, headers=headers)

        # 解析 HTML 响应
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("ul.vT-srch-result-list-bid li")
        for item in items[:max_results]:
            link_elem = item.find("a")
            if not link_elem:
                continue

            title = link_elem.get_text(strip=True)
            href = link_elem.get("href", "")

            # 提取日期和金额
            spans = item.find_all("span")
            date_text = ""
            amount_text = ""
            for span in spans:
                text = span.get_text(strip=True)
                if "日期" in text or "-" in text:
                    date_text = text
                if "万" in text or "元" in text:
                    amount_text = text

            results.append(
                _normalize_signal(
                    signal_type="procurement",
                    query=query,
                    data_point=f"[{date_text}] {title}"
                    + (f" 金额:{amount_text}" if amount_text else ""),
                    significance="政府采购方向反映技术成熟度和政府认可度",
                    raw_data={
                        "title": title,
                        "url": href,
                        "date": date_text,
                        "amount": amount_text,
                    },
                )
            )

        print(f"  [政府采购] '{query}' → {len(results)} 条")
    except Exception as e:
        print(f"  [政府采购] '{query}' 失败: {e}")

    return results


# ===========================================================================
# 学术热度趋势 — arXiv + Semantic Scholar
# ===========================================================================


def fetch_academic_trend(query, months=24):
    """
    按月统计特定关键词在 arXiv 和 Semantic Scholar 上的论文发表量趋势
    """
    results = []

    # --- arXiv 趋势 ---
    try:
        import arxiv

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=500,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        month_counts = {}
        cutoff = datetime.now() - timedelta(days=months * 30)

        for paper in client.results(search):
            if paper.published and paper.published.replace(tzinfo=None) >= cutoff:
                month_key = paper.published.strftime("%Y-%m")
                month_counts[month_key] = month_counts.get(month_key, 0) + 1
            elif paper.published and paper.published.replace(tzinfo=None) < cutoff:
                break

        if month_counts:
            sorted_months = sorted(month_counts.items())
            trend_text = ", ".join(f"{m}: {c}篇" for m, c in sorted_months[-12:])
            results.append(
                _normalize_signal(
                    signal_type="academic_trend_arxiv",
                    query=query,
                    data_point=f"arXiv 月度论文趋势: {trend_text}",
                    significance=_analyze_academic_trend(sorted_months),
                    raw_data={"source": "arxiv", "by_month": dict(sorted_months)},
                )
            )

        print(f"  [arXiv趋势] '{query}' → {len(month_counts)} 个月数据")
    except Exception as e:
        print(f"  [arXiv趋势] '{query}' 失败: {e}")

    # --- Semantic Scholar 趋势 ---
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": 100,
            "fields": "title,year,citationCount,publicationDate",
        }

        resp = _get(url, params=params)
        data = resp.json()

        year_counts = {}
        citation_totals = {}
        for paper in data.get("data", []):
            year = paper.get("year")
            if year and year >= datetime.now().year - (months // 12 + 1):
                year_counts[year] = year_counts.get(year, 0) + 1
                citation_totals[year] = citation_totals.get(year, 0) + (
                    paper.get("citationCount", 0) or 0
                )

        if year_counts:
            sorted_years = sorted(year_counts.items())
            trend_text = ", ".join(
                f"{y}: {c}篇(引用{citation_totals.get(y, 0)})" for y, c in sorted_years
            )
            results.append(
                _normalize_signal(
                    signal_type="academic_trend_s2",
                    query=query,
                    data_point=f"Semantic Scholar 年度论文趋势: {trend_text}",
                    significance="学术热度变化提前12-24个月预示产业趋势",
                    raw_data={
                        "source": "semantic_scholar",
                        "total": data.get("total", 0),
                        "by_year": dict(sorted_years),
                        "citations_by_year": citation_totals,
                    },
                )
            )

        print(f"  [S2趋势] '{query}' → {len(year_counts)} 年数据")
    except Exception as e:
        print(f"  [S2趋势] '{query}' 失败: {e}")

    time.sleep(3)  # arXiv 速率限制
    return results


def _analyze_academic_trend(sorted_months):
    """分析学术趋势"""
    if len(sorted_months) < 3:
        return "数据不足"
    counts = [c for _, c in sorted_months]
    recent_avg = sum(counts[-3:]) / 3
    older_avg = sum(counts[:3]) / 3 if len(counts) >= 6 else counts[0]
    if recent_avg > older_avg * 2:
        return "学术热度急速上升，可能预示重大技术突破或新研究方向"
    elif recent_avg > older_avg * 1.3:
        return "学术热度稳步上升，领域处于活跃发展期"
    elif recent_avg < older_avg * 0.5:
        return "学术热度下降，可能表明领域趋于成熟或关注度转移"
    else:
        return "学术热度基本稳定"


# ===========================================================================
# 批量获取（从计划 JSON）
# ===========================================================================


def fetch_from_plan(plan):
    """
    从计划 JSON 批量获取弱信号

    plan 格式（与 01_plan.md 输出匹配）：
    {
      "patents": [{"query": "instant delivery robot", "years": 3}],
      "hiring": [{"company": "美团", "keywords": "即时零售"}],
      "procurement": [{"query": "即时配送"}],
      "academic_trend": [{"query": "instant delivery", "months": 24}]
    }
    """
    all_results = []
    errors = []

    # 专利
    for item in plan.get("patents", []):
        try:
            all_results.extend(
                fetch_patents_patentsview(
                    item.get("query", ""),
                    years=item.get("years", 3),
                )
            )
        except Exception as e:
            errors.append(f"patents/{item.get('query', '')}: {e}")

    # 招聘
    for item in plan.get("hiring", []):
        try:
            all_results.extend(
                fetch_hiring_signals(
                    item.get("company", ""),
                    item.get("keywords", ""),
                )
            )
        except Exception as e:
            errors.append(f"hiring/{item.get('company', '')}: {e}")

    # 政府采购
    for item in plan.get("procurement", []):
        try:
            all_results.extend(fetch_procurement(item.get("query", "")))
        except Exception as e:
            errors.append(f"procurement/{item.get('query', '')}: {e}")

    # 学术热度
    for item in plan.get("academic_trend", []):
        try:
            all_results.extend(
                fetch_academic_trend(
                    item.get("query", ""),
                    months=item.get("months", 24),
                )
            )
        except Exception as e:
            errors.append(f"academic_trend/{item.get('query', '')}: {e}")

    return all_results, errors


# ===========================================================================
# CLI 入口
# ===========================================================================


def main():
    parser = argparse.ArgumentParser(description="弱信号数据采集 (v5.0)")
    parser.add_argument(
        "--type",
        dest="signal_type",
        help="信号类型 (patents/hiring/procurement/academic_trend)",
    )
    parser.add_argument("--plan", help="批量获取计划 JSON 文件路径")
    parser.add_argument("--query", default="", help="搜索关键词")
    parser.add_argument("--company", default="", help="公司名称 (hiring 模式)")
    parser.add_argument("--keywords", default="", help="招聘关键词 (hiring 模式)")
    parser.add_argument("--years", type=int, default=3, help="专利查询年数（默认 3）")
    parser.add_argument(
        "--months", type=int, default=24, help="学术趋势月数（默认 24）"
    )
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    print(f"[WEAK_SIGNALS] v5.0 弱信号数据采集")

    all_results = []
    errors = []

    if args.plan:
        try:
            with open(args.plan, "r", encoding="utf-8") as f:
                plan = json.load(f)
            print(f"[WEAK_SIGNALS] 批量模式：从 {args.plan} 加载计划")
            all_results, errors = fetch_from_plan(plan)
        except Exception as e:
            print(f"[WEAK_SIGNALS] 计划文件加载失败: {e}")
            errors.append(str(e))
    elif args.signal_type:
        sig_type = args.signal_type.lower()
        print(f"[WEAK_SIGNALS] 单类型模式：{sig_type}")

        dispatch = {
            "patents": lambda: fetch_patents_patentsview(args.query, args.years),
            "hiring": lambda: fetch_hiring_signals(args.company, args.keywords),
            "procurement": lambda: fetch_procurement(args.query),
            "academic_trend": lambda: fetch_academic_trend(args.query, args.months),
        }

        if sig_type in dispatch:
            try:
                all_results = dispatch[sig_type]()
            except Exception as e:
                errors.append(f"{sig_type}: {e}")
        else:
            print(f"[WEAK_SIGNALS] 未知信号类型: {sig_type}")
            sys.exit(1)
    else:
        print("[WEAK_SIGNALS] 请指定 --type 或 --plan")
        parser.print_help()
        sys.exit(1)

    output = {
        "fetch_time": datetime.now().isoformat(),
        "total_signals": len(all_results),
        "signals": all_results,
        "errors": errors,
        "note": "弱信号不作为直接论据，仅作为分析提示注入章节分析",
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[WEAK_SIGNALS] 完成: {len(all_results)} 条信号, {len(errors)} 个错误")
    print(f"[WEAK_SIGNALS] 输出 → {args.output}")
    if errors:
        for e in errors:
            print(f"  [错误] {e}")


if __name__ == "__main__":
    main()

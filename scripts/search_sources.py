#!/usr/bin/env python3
"""
统一搜索源脚本 v5.0 — 6 层搜索 + 3 级降级链 + 多学术源

搜索引擎降级链：Tavily → Brave → DuckDuckGo（3 级）
学术搜索：arXiv + Semantic Scholar + PubMed
搜索层：background / authority / timeliness / academic / regulatory / weak_signal

用法：
  # 通用搜索（Tavily → Brave → DuckDuckGo 自动降级）
  python search_sources.py web \
    --keywords-file search_keywords.json \
    --layer background \
    --max-results 10 \
    --freshness-days 90 \
    --output results.json

  # 学术搜索（arXiv + Semantic Scholar + PubMed）
  python search_sources.py academic \
    --keywords-file search_keywords.json \
    --max-results 10 \
    --output results.json

v5.0 变更：
  - 搜索引擎降级链从 2 级扩展到 3 级 (Tavily→Brave→DuckDuckGo)
  - Google CSE 已弃用，Bing 已取消
  - 搜索层从 4 层扩展到 6 层（新增 regulatory, weak_signal）
  - 关键词支持多语言标记 {"keyword": "...", "lang": "zh"}
  - 新增 Semantic Scholar 和 PubMed 学术搜索
"""

import argparse
import json
import os
import sys
import time


# ---------------------------------------------------------------------------
# Tavily 搜索（降级链第 1 位）
# ---------------------------------------------------------------------------


def tavily_search(
    keyword: str, max_results: int, freshness_days: int | None, layer: str
) -> list[dict]:
    """调用 Tavily API 进行通用搜索"""
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY 未设置")

    client = TavilyClient(api_key=api_key)

    kwargs: dict = {
        "query": keyword,
        "search_depth": "basic",
        "max_results": max_results,
        "include_raw_content": False,
        "topic": "general",
    }
    if freshness_days is not None:
        kwargs["days"] = freshness_days

    response = client.search(**kwargs)

    results = []
    for item in response.get("results", []):
        results.append(
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "search_layer": layer,
                "search_keyword": keyword,
                "source_engine": "tavily",
            }
        )
    return results


# ---------------------------------------------------------------------------
# Brave 搜索（降级链第 2 位）
# ---------------------------------------------------------------------------


def brave_search(
    keyword: str, max_results: int, freshness_days: int | None, layer: str
) -> list[dict]:
    """调用 Brave Search API"""
    import requests

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY 未设置")

    headers = {"X-Subscription-Token": api_key}
    params: dict = {
        "q": keyword,
        "count": max_results,
    }
    if freshness_days is not None:
        if freshness_days <= 1:
            params["freshness"] = "pd"
        elif freshness_days <= 7:
            params["freshness"] = "pw"
        elif freshness_days <= 31:
            params["freshness"] = "pm"
        elif freshness_days <= 365:
            params["freshness"] = "py"

    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append(
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("description", ""),
                "search_layer": layer,
                "search_keyword": keyword,
                "source_engine": "brave",
            }
        )
    return results


# ---------------------------------------------------------------------------
# DuckDuckGo 搜索（降级链第 3 位，v5.0 新增）
# ---------------------------------------------------------------------------


def duckduckgo_search(
    keyword: str, max_results: int, freshness_days: int | None, layer: str
) -> list[dict]:
    """
    DuckDuckGo 搜索 — 使用 Instant Answer API + HTML 搜索降级

    注意：DuckDuckGo Instant Answer API 是免费无 Key 的，
    但返回的是即时回答而非完整搜索结果。
    当 Tavily 和 Brave 都不可用时作为最后兜底。
    """
    import requests

    results = []

    # 方案 1：DuckDuckGo Instant Answer API
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": keyword,
                "format": "json",
                "no_html": 1,
                "no_redirect": 1,
            },
            timeout=15,
        )
        data = resp.json()

        # 提取 AbstractURL 和相关主题
        if data.get("AbstractURL"):
            results.append(
                {
                    "url": data["AbstractURL"],
                    "title": data.get("Heading", ""),
                    "content": data.get("AbstractText", ""),
                    "search_layer": layer,
                    "search_keyword": keyword,
                    "source_engine": "duckduckgo",
                }
            )

        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict):
                if topic.get("FirstURL"):
                    results.append(
                        {
                            "url": topic["FirstURL"],
                            "title": topic.get("Text", "")[:100],
                            "content": topic.get("Text", ""),
                            "search_layer": layer,
                            "search_keyword": keyword,
                            "source_engine": "duckduckgo",
                        }
                    )
                # 子主题
                elif "Topics" in topic:
                    for sub in topic["Topics"]:
                        if isinstance(sub, dict) and sub.get("FirstURL"):
                            results.append(
                                {
                                    "url": sub["FirstURL"],
                                    "title": sub.get("Text", "")[:100],
                                    "content": sub.get("Text", ""),
                                    "search_layer": layer,
                                    "search_keyword": keyword,
                                    "source_engine": "duckduckgo",
                                }
                            )

            if len(results) >= max_results:
                break

    except Exception as e:
        print(f"  [DuckDuckGo] API 失败: {e}")

    # 方案 2：如果 Instant Answer 结果不足，尝试 DuckDuckGo HTML 搜索
    if len(results) < 3:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": keyword},
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
                timeout=15,
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            for result_div in soup.select(".result__body"):
                link = result_div.select_one(".result__a")
                snippet = result_div.select_one(".result__snippet")
                if link and link.get("href"):
                    href = link["href"]
                    # DuckDuckGo 使用重定向 URL，提取实际 URL
                    if "uddg=" in href:
                        from urllib.parse import unquote, parse_qs, urlparse

                        parsed = urlparse(href)
                        actual_url = parse_qs(parsed.query).get("uddg", [href])[0]
                        href = unquote(actual_url)

                    results.append(
                        {
                            "url": href,
                            "title": link.get_text(strip=True),
                            "content": snippet.get_text(strip=True) if snippet else "",
                            "search_layer": layer,
                            "search_keyword": keyword,
                            "source_engine": "duckduckgo",
                        }
                    )

                if len(results) >= max_results:
                    break

        except Exception as e:
            print(f"  [DuckDuckGo] HTML 搜索也失败: {e}")

    return results[:max_results]


# ---------------------------------------------------------------------------
# 通用搜索：Tavily → Brave → DuckDuckGo 3 级自动降级
# ---------------------------------------------------------------------------


def search_web(
    keyword: str, max_results: int, freshness_days: int | None, layer: str
) -> list[dict]:
    """通用搜索入口，3 级降级链"""
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    brave_key = os.environ.get("BRAVE_API_KEY", "")

    # 定义降级链
    chain = []
    if tavily_key:
        chain.append(
            (
                "tavily",
                lambda: tavily_search(keyword, max_results, freshness_days, layer),
            )
        )
    if brave_key:
        chain.append(
            ("brave", lambda: brave_search(keyword, max_results, freshness_days, layer))
        )
    # DuckDuckGo 始终可用（无需 Key）
    chain.append(
        (
            "duckduckgo",
            lambda: duckduckgo_search(keyword, max_results, freshness_days, layer),
        )
    )

    if not chain:
        print("[SEARCH] 警告：无可用搜索引擎")
        return []

    for engine_name, search_fn in chain:
        try:
            results = search_fn()
            if results:
                return results
            else:
                print(f"[SEARCH] {engine_name} 返回空结果，尝试下一个引擎")
        except Exception as e:
            print(f"[SEARCH] {engine_name} 失败（{e}），尝试下一个引擎")

    print("[SEARCH] 所有搜索引擎均失败")
    return []


# ---------------------------------------------------------------------------
# arXiv 学术搜索
# ---------------------------------------------------------------------------


def arxiv_search(keyword: str, max_results: int) -> list[dict]:
    """调用 arXiv API 进行学术搜索"""
    import arxiv

    client = arxiv.Client()
    search = arxiv.Search(
        query=keyword,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    results = []
    for r in client.results(search):
        results.append(
            {
                "url": r.entry_id,
                "title": r.title,
                "content": r.summary,
                "search_layer": "academic",
                "search_keyword": keyword,
                "source_engine": "arxiv",
                "authors": [a.name for a in r.authors],
                "published_date": r.published.isoformat() if r.published else "",
                "pdf_url": r.pdf_url or "",
            }
        )
    return results


# ---------------------------------------------------------------------------
# Semantic Scholar 学术搜索 (v5.0 新增)
# ---------------------------------------------------------------------------


def semantic_scholar_search(keyword: str, max_results: int) -> list[dict]:
    """
    Semantic Scholar API — 免费无 Key 模式
    https://api.semanticscholar.org/graph/v1/paper/search

    注意：S2 无 Key 模式限速极严（实测连续请求需 ≥5 秒间隔），
    429 时使用指数退避重试，最多 2 次。
    """
    import requests

    results = []
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": keyword,
        "limit": min(max_results, 100),
        "fields": "title,abstract,url,year,citationCount,authors,publicationDate,externalIds",
    }

    headers = {"User-Agent": "DeepResearchPro/5.0"}
    s2_key = os.environ.get("SEMANTIC_SCHOLAR_KEY", "")
    if s2_key:
        headers["x-api-key"] = s2_key

    # 指数退避重试（S2 限速极严）
    max_retries = 2
    for attempt in range(max_retries + 1):
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429:
            if attempt < max_retries:
                wait = 5 * (2**attempt)  # 5s, 10s
                print(
                    f"  [S2] 429 限速，等待 {wait}s 后重试 ({attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                continue
            else:
                print(f"  [S2] 429 限速，已重试 {max_retries} 次仍失败，跳过")
                return results
        resp.raise_for_status()
        break

    data = resp.json()

    for paper in data.get("data", []):
        authors = [a.get("name", "") for a in paper.get("authors", [])]
        ext_ids = paper.get("externalIds", {})
        doi = ext_ids.get("DOI", "")
        paper_url = paper.get("url", "")
        if not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"

        results.append(
            {
                "url": paper_url,
                "title": paper.get("title", ""),
                "content": paper.get("abstract", "") or "",
                "search_layer": "academic",
                "search_keyword": keyword,
                "source_engine": "semantic_scholar",
                "authors": authors,
                "published_date": paper.get("publicationDate", "")
                or str(paper.get("year", "")),
                "citation_count": paper.get("citationCount", 0),
                "doi": doi,
            }
        )

    return results


# ---------------------------------------------------------------------------
# PubMed 学术搜索 (v5.0 新增)
# ---------------------------------------------------------------------------


def pubmed_search(keyword: str, max_results: int) -> list[dict]:
    """
    PubMed E-utilities API
    1. ESearch: 搜索获取 PMID 列表
    2. EFetch: 获取文章详情
    """
    import requests

    results = []
    api_key = os.environ.get("PUBMED_API_KEY", "")

    # Step 1: ESearch
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": keyword,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    if api_key:
        params["api_key"] = api_key

    resp = requests.get(esearch_url, params=params, timeout=30)
    resp.raise_for_status()
    search_data = resp.json()
    pmids = search_data.get("esearchresult", {}).get("idlist", [])

    if not pmids:
        return results

    # Step 2: ESummary for details
    esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    resp = requests.get(esummary_url, params=params, timeout=30)
    resp.raise_for_status()
    summary_data = resp.json()

    for pmid in pmids:
        article = summary_data.get("result", {}).get(pmid, {})
        if not article or pmid == "uids":
            continue

        authors = [a.get("name", "") for a in article.get("authors", [])]

        results.append(
            {
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "title": article.get("title", ""),
                "content": article.get("sorttitle", ""),
                "search_layer": "academic",
                "search_keyword": keyword,
                "source_engine": "pubmed",
                "authors": authors,
                "published_date": article.get("pubdate", ""),
                "pmid": pmid,
                "doi": article.get("elocationid", ""),
            }
        )

    return results


# ---------------------------------------------------------------------------
# 学术搜索入口（arXiv + Semantic Scholar + PubMed）
# ---------------------------------------------------------------------------


def search_academic(keywords: list[str], max_results: int) -> list[dict]:
    """
    v5.0 学术搜索入口 — 同时查询 arXiv + Semantic Scholar + PubMed

    arXiv: 将关键词 2-3 个一组用 OR 合并
    Semantic Scholar: 逐个查询
    PubMed: 逐个查询（生物医学相关时）
    """
    all_results = []

    # --- arXiv（最稳定，先执行）---
    batch_size = 3
    batches = []
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i : i + batch_size]
        combined = " OR ".join(f'"{kw}"' for kw in batch)
        batches.append(combined)

    for idx, query in enumerate(batches):
        print(f"[SEARCH] arXiv {idx + 1}/{len(batches)}: {query[:80]}...")
        try:
            results = arxiv_search(query, max_results)
            all_results.extend(results)
            print(f"  → {len(results)} 条")
        except Exception as e:
            print(f"  → 失败: {e}")
        if idx < len(batches) - 1:
            time.sleep(3)  # arXiv 速率限制

    # --- PubMed（稳定，有 Key 时无限速）---
    for idx, kw in enumerate(keywords):
        print(f"[SEARCH] PubMed {idx + 1}/{len(keywords)}: {kw[:60]}...")
        try:
            results = pubmed_search(kw, max_results)
            all_results.extend(results)
            print(f"  → {len(results)} 条")
        except Exception as e:
            print(f"  → 失败: {e}")
        time.sleep(0.5)

    # --- Semantic Scholar（限速最严，放最后，容忍失败）---
    s2_success = 0
    s2_total = len(keywords)
    for idx, kw in enumerate(keywords):
        print(f"[SEARCH] Semantic Scholar {idx + 1}/{s2_total}: {kw[:60]}...")
        try:
            results = semantic_scholar_search(kw, max_results)
            all_results.extend(results)
            s2_success += 1
            print(f"  → {len(results)} 条")
        except Exception as e:
            print(f"  → 失败: {e}")
        # S2 无 Key 模式需要 ≥5 秒间隔
        if idx < s2_total - 1:
            time.sleep(5)

    if s2_success == 0 and s2_total > 0:
        print(
            f"[SEARCH] Semantic Scholar 全部失败（{s2_total} 次），可能被限速。arXiv+PubMed 结果仍可用。"
        )

    return all_results


# ---------------------------------------------------------------------------
# 关键词预处理 (v5.0 新增)
# ---------------------------------------------------------------------------


def preprocess_keywords(raw_keywords):
    """
    处理 v5.0 多语言关键词格式

    支持两种格式：
    - 旧格式: ["keyword1", "keyword2"]
    - v5.0 格式: [{"keyword": "...", "lang": "zh"}, {"keyword": "...", "lang": "en"}]

    返回: list[str] (纯关键词列表)
    """
    keywords = []
    for item in raw_keywords:
        if isinstance(item, str):
            if item.strip():
                keywords.append(item.strip())
        elif isinstance(item, dict):
            kw = item.get("keyword", "").strip()
            if kw:
                keywords.append(kw)
    return keywords


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def cmd_web(args):
    """处理 web 子命令"""
    try:
        with open(args.keywords_file, "r", encoding="utf-8") as f:
            raw_keywords = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[SEARCH] 关键词文件加载失败: {e}")
        raw_keywords = []

    if not isinstance(raw_keywords, list):
        print("[SEARCH] 关键词文件格式错误，期望 JSON 数组")
        raw_keywords = []

    keywords = preprocess_keywords(raw_keywords)
    layer = args.layer or "background"
    max_results = args.max_results or 10
    freshness_days = args.freshness_days

    print(
        f"[SEARCH] v5.0 模式=web 层={layer} 关键词={len(keywords)}条 "
        f"max_results={max_results} freshness_days={freshness_days}"
    )
    print(f"[SEARCH] 降级链: Tavily → Brave → DuckDuckGo")

    all_results = []
    for idx, kw in enumerate(keywords):
        print(f"[SEARCH] ({idx + 1}/{len(keywords)}) 搜索: {kw[:60]}...")
        results = search_web(kw, max_results, freshness_days, layer)
        all_results.extend(results)
        print(f"  → {len(results)} 条结果")
        if idx < len(keywords) - 1:
            time.sleep(0.5)

    # 去重
    seen_urls = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(r)

    print(f"[SEARCH] web 完成: {len(all_results)} 条（去重后 {len(deduped)} 条）")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f"[SEARCH] 输出 → {args.output}")


def cmd_academic(args):
    """处理 academic 子命令"""
    try:
        with open(args.keywords_file, "r", encoding="utf-8") as f:
            raw_keywords = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[SEARCH] 关键词文件加载失败: {e}")
        raw_keywords = []

    if not isinstance(raw_keywords, list):
        print("[SEARCH] 关键词文件格式错误，期望 JSON 数组")
        raw_keywords = []

    keywords = preprocess_keywords(raw_keywords)
    max_results = args.max_results or 10

    print(
        f"[SEARCH] v5.0 模式=academic 关键词={len(keywords)}条 max_results={max_results}"
    )
    print(f"[SEARCH] 学术源: arXiv + Semantic Scholar + PubMed")

    all_results = search_academic(keywords, max_results)

    # 去重
    seen_urls = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(r)

    print(f"[SEARCH] academic 完成: {len(all_results)} 条（去重后 {len(deduped)} 条）")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f"[SEARCH] 输出 → {args.output}")


def main():
    parser = argparse.ArgumentParser(
        description="统一搜索源脚本 v5.0（Tavily/Brave/DuckDuckGo/arXiv/SemanticScholar/PubMed）"
    )
    subparsers = parser.add_subparsers(dest="mode", help="搜索模式")

    # web 子命令
    web_parser = subparsers.add_parser(
        "web", help="通用搜索（Tavily → Brave → DuckDuckGo）"
    )
    web_parser.add_argument(
        "--keywords-file", required=True, help="关键词 JSON 文件路径"
    )
    web_parser.add_argument(
        "--layer",
        default="background",
        help="搜索层名称（background/authority/timeliness/academic/regulatory/weak_signal）",
    )
    web_parser.add_argument(
        "--max-results", type=int, default=10, help="每个关键词的最大结果数（默认 10）"
    )
    web_parser.add_argument(
        "--freshness-days",
        type=int,
        default=None,
        help="时效过滤天数（不指定 = 不限时效）",
    )
    web_parser.add_argument("--output", required=True, help="输出 JSON 文件路径")

    # academic 子命令
    academic_parser = subparsers.add_parser(
        "academic", help="学术搜索（arXiv + Semantic Scholar + PubMed）"
    )
    academic_parser.add_argument(
        "--keywords-file", required=True, help="关键词 JSON 文件路径"
    )
    academic_parser.add_argument(
        "--max-results", type=int, default=10, help="每个关键词的最大结果数（默认 10）"
    )
    academic_parser.add_argument("--output", required=True, help="输出 JSON 文件路径")

    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        sys.exit(1)

    if args.mode == "web":
        cmd_web(args)
    elif args.mode == "academic":
        cmd_academic(args)
    else:
        print(f"[SEARCH] 未知模式: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()

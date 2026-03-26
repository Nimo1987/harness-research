#!/usr/bin/env python3
"""
监管申报文件获取脚本 (v5.0 新增)

支持数据源：
  - SEC EDGAR Full-Text Search + XBRL 结构化数据
  - 巨潮资讯 cninfo.com.cn (A 股公告)
  - 港交所披露易 hkexnews.hk (港股公告)
  - EDINET (日本上市公司财务披露)

用法：
  # SEC EDGAR 全文搜索
  python fetch_regulatory_filings.py --source sec_edgar --query "artificial intelligence" --filing-type "10-K" --output sec.json

  # SEC EDGAR 按公司搜索
  python fetch_regulatory_filings.py --source sec_edgar --company "AAPL" --filing-type "10-K" --output sec_aapl.json

  # 巨潮资讯
  python fetch_regulatory_filings.py --source cninfo --company "贵州茅台" --filing-type "年报" --output cninfo.json

  # 港交所披露易
  python fetch_regulatory_filings.py --source hkex --company "03690.HK" --output hkex.json

  # 批量获取（从 JSON 计划文件）
  python fetch_regulatory_filings.py --plan regulatory_plan.json --output regulatory.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime


TIMEOUT = 30


def _get(url, params=None, headers=None, timeout=TIMEOUT):
    """统一 HTTP GET"""
    import requests

    hdrs = {}
    if headers:
        hdrs.update(headers)
    resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp


def _normalize_filing(
    source, company, filing_type, date, title, url, content="", raw_data=None
):
    """统一输出格式"""
    return {
        "source": source,
        "company": company,
        "filing_type": filing_type,
        "date": date,
        "title": title,
        "url": url,
        "content_snippet": content[:3000] if content else "",
        "tier": 0,
        "raw_data": raw_data or {},
        "fetch_time": datetime.now().isoformat(),
    }


# ===========================================================================
# SEC EDGAR
# ===========================================================================


def _sec_user_agent():
    """获取 SEC EDGAR 所需的 User-Agent
    SEC requires: "Company Name admin@example.com"
    See: https://www.sec.gov/os/accessing-edgar-data
    """
    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "")
    if not ua:
        print("[REGULATORY] 警告: SEC_EDGAR_USER_AGENT 未设置，SEC EDGAR 查询将被跳过")
        print(
            "[REGULATORY] 请设置: export SEC_EDGAR_USER_AGENT='YourApp your-email@example.com'"
        )
        return ""
    return ua


def fetch_sec_edgar_search(query="", company="", filing_type="", max_results=10):
    """
    SEC EDGAR 全文搜索 (EFTS)
    https://efts.sec.gov/LATEST/search-index?q=...&dateRange=custom&startdt=...&enddt=...&forms=10-K
    """
    results = []
    headers = {"User-Agent": _sec_user_agent()}

    try:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": query or company or "",
            "forms": filing_type or "",
            "from": 0,
            "size": min(max_results, 40),
        }
        params = {k: v for k, v in params.items() if v}

        resp = _get(url, params=params, headers=headers)
        data = resp.json()

        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{source.get('file_num', '')}"
            )

            results.append(
                _normalize_filing(
                    source="sec_edgar",
                    company=source.get("display_names", [""])[0]
                    if source.get("display_names")
                    else company,
                    filing_type=source.get("form_type", filing_type),
                    date=source.get("file_date", ""),
                    title=source.get("display_names", [""])[0]
                    if source.get("display_names")
                    else "",
                    url=filing_url,
                    content=hit.get("_source", {}).get("text", "")[:3000],
                    raw_data=source,
                )
            )

        print(f"  [SEC EDGAR] '{query or company}' {filing_type} → {len(results)} 条")
    except Exception as e:
        # 降级：尝试 EDGAR 公司搜索 API
        print(f"  [SEC EDGAR] EFTS 搜索失败({e})，尝试公司搜索 API")
        try:
            results = _fetch_sec_company_filings(
                company or query, filing_type, max_results, headers
            )
        except Exception as e2:
            print(f"  [SEC EDGAR] 公司搜索也失败: {e2}")

    return results


def _fetch_sec_company_filings(company, filing_type, max_results, headers):
    """SEC EDGAR 公司 Filings API (降级方案)"""
    results = []

    # 先通过公司搜索获取 CIK
    search_url = "https://efts.sec.gov/LATEST/search-index"
    params = {"q": company, "forms": filing_type, "size": max_results}
    params = {k: v for k, v in params.items() if v}

    # 备选：直接使用 EDGAR 全文搜索 API
    url = "https://efts.sec.gov/LATEST/search-index"
    try:
        resp = _get(url, params={"q": company, "size": max_results}, headers=headers)
        data = resp.json()
        for hit in data.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            results.append(
                _normalize_filing(
                    source="sec_edgar",
                    company=company,
                    filing_type=src.get("form_type", ""),
                    date=src.get("file_date", ""),
                    title=f"{company} - {src.get('form_type', '')}",
                    url=f"https://www.sec.gov/cgi-bin/browse-edgar?company={company}&CIK=&type={filing_type}",
                    raw_data=src,
                )
            )
    except Exception:
        pass

    return results


def fetch_sec_xbrl(cik, filing_type="10-K"):
    """
    SEC XBRL 结构化财务数据
    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
    """
    results = []
    headers = {"User-Agent": _sec_user_agent()}

    try:
        # 确保 CIK 是 10 位零填充
        cik_padded = str(cik).zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        resp = _get(url, headers=headers)
        data = resp.json()

        company_name = data.get("entityName", "")
        facts = data.get("facts", {})

        # 提取 US-GAAP 关键财务指标
        us_gaap = facts.get("us-gaap", {})
        key_metrics = [
            "Revenues",
            "NetIncomeLoss",
            "Assets",
            "StockholdersEquity",
            "OperatingIncomeLoss",
            "EarningsPerShareBasic",
        ]

        for metric in key_metrics:
            if metric in us_gaap:
                units_data = us_gaap[metric].get("units", {})
                for unit_type, values in units_data.items():
                    # 取最近的年度数据
                    annual = [v for v in values if v.get("form") == filing_type]
                    for val in annual[-5:]:  # 最近 5 年
                        results.append(
                            _normalize_filing(
                                source="sec_xbrl",
                                company=company_name,
                                filing_type=filing_type,
                                date=val.get("end", ""),
                                title=f"{company_name} - {metric}",
                                url=url,
                                content=f"{metric}: {val.get('val', '')} {unit_type}",
                                raw_data={
                                    "metric": metric,
                                    "value": val.get("val"),
                                    "unit": unit_type,
                                    "period_end": val.get("end", ""),
                                    "period_start": val.get("start", ""),
                                    "filed": val.get("filed", ""),
                                },
                            )
                        )

        print(f"  [SEC XBRL] CIK={cik} → {len(results)} 条财务数据")
    except Exception as e:
        print(f"  [SEC XBRL] CIK={cik} 失败: {e}")

    return results


# ===========================================================================
# 巨潮资讯 (cninfo.com.cn)
# ===========================================================================


def fetch_cninfo(company="", filing_type="", max_results=10):
    """
    巨潮资讯公告搜索
    http://www.cninfo.com.cn/new/hisAnnouncement/query
    """
    results = []

    try:
        url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
        }
        data = {
            "searchkey": company,
            "category": _cninfo_category(filing_type),
            "pageNum": 1,
            "pageSize": max_results,
            "column": "szse",  # 深交所，也包含上交所
            "tabName": "fulltext",
            "sortName": "",
            "sortType": "",
            "limit": "",
            "seDate": "",
        }

        import requests

        resp = requests.post(url, data=data, headers=headers, timeout=TIMEOUT)
        resp_data = resp.json()

        for ann in resp_data.get("announcements", []):
            pdf_url = f"http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}"
            results.append(
                _normalize_filing(
                    source="cninfo",
                    company=ann.get("secName", company),
                    filing_type=ann.get("announcementTypeName", filing_type),
                    date=_ts_to_date(ann.get("announcementTime", 0)),
                    title=ann.get("announcementTitle", ""),
                    url=pdf_url,
                    content=ann.get("announcementTitle", ""),
                    raw_data={
                        "sec_code": ann.get("secCode", ""),
                        "sec_name": ann.get("secName", ""),
                        "type": ann.get("announcementTypeName", ""),
                        "pdf_url": pdf_url,
                    },
                )
            )

        print(f"  [巨潮] '{company}' {filing_type} → {len(results)} 条")
    except Exception as e:
        print(f"  [巨潮] '{company}' 失败: {e}")

    return results


def _cninfo_category(filing_type):
    """映射中文公告类型到巨潮分类代码"""
    mapping = {
        "年报": "category_ndbg_szsh",
        "半年报": "category_bndbg_szsh",
        "季报": "category_jbdbg_szsh",
        "IPO": "category_sf_szsh",
        "增发": "category_zf_szsh",
    }
    return mapping.get(filing_type, "")


def _ts_to_date(timestamp_ms):
    """毫秒时间戳转日期字符串"""
    if not timestamp_ms:
        return ""
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ===========================================================================
# 港交所披露易 (hkexnews.hk)
# ===========================================================================


def fetch_hkex(company="", max_results=10):
    """
    港交所披露易公告搜索
    https://www1.hkexnews.hk/search/titlesearch.xhtml
    """
    results = []

    try:
        # 提取股票代码数字部分
        stock_code = re.sub(r"[^\d]", "", company)

        url = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
        params = {
            "lang": "ZH",
            "stock": stock_code,
            "notafter": datetime.now().strftime("%Y%m%d"),
            "rowrange": f"1-{max_results}",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

        resp = _get(url, params=params, headers=headers)
        # 解析 HTML 响应
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        rows = soup.select("tr.row0, tr.row1")
        for row in rows[:max_results]:
            cells = row.find_all("td")
            if len(cells) >= 4:
                date_text = cells[0].get_text(strip=True)
                company_name = cells[1].get_text(strip=True)
                title_elem = cells[2].find("a")
                title = (
                    title_elem.get_text(strip=True)
                    if title_elem
                    else cells[2].get_text(strip=True)
                )
                link = title_elem.get("href", "") if title_elem else ""
                if link and not link.startswith("http"):
                    link = f"https://www1.hkexnews.hk{link}"

                results.append(
                    _normalize_filing(
                        source="hkex",
                        company=company_name or company,
                        filing_type="公告",
                        date=date_text,
                        title=title,
                        url=link,
                        raw_data={"stock_code": stock_code},
                    )
                )

        print(f"  [港交所] '{company}' → {len(results)} 条")
    except Exception as e:
        print(f"  [港交所] '{company}' 失败: {e}")

    return results


# ===========================================================================
# EDINET (日本)
# ===========================================================================


def fetch_edinet(company="", max_results=10):
    """
    EDINET API (日本金融厅)
    https://disclosure.edinet-fsa.go.jp/api/v2/documents.json?date=...&type=2
    """
    results = []

    try:
        # EDINET 按日期查询最近文件
        from datetime import timedelta

        today = datetime.now()

        for days_back in range(0, 30, 1):
            if len(results) >= max_results:
                break

            date_str = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
            url = "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json"
            params = {"date": date_str, "type": 2}

            try:
                resp = _get(url, params=params, timeout=15)
                data = resp.json()

                for doc in data.get("results", []):
                    # 如果指定了公司，过滤
                    if company and company not in (
                        doc.get("filerName", "") + doc.get("secCode", "")
                    ):
                        continue

                    doc_url = f"https://disclosure.edinet-fsa.go.jp/api/v2/documents/{doc.get('docID', '')}"
                    results.append(
                        _normalize_filing(
                            source="edinet",
                            company=doc.get("filerName", ""),
                            filing_type=doc.get("docTypeCode", ""),
                            date=doc.get("submitDateTime", ""),
                            title=doc.get("docDescription", ""),
                            url=doc_url,
                            raw_data={
                                "doc_id": doc.get("docID", ""),
                                "sec_code": doc.get("secCode", ""),
                                "doc_type": doc.get("docTypeCode", ""),
                            },
                        )
                    )

                    if len(results) >= max_results:
                        break
            except Exception:
                continue

            time.sleep(0.5)  # 速率控制

        print(f"  [EDINET] '{company}' → {len(results)} 条")
    except Exception as e:
        print(f"  [EDINET] '{company}' 失败: {e}")

    return results


# ===========================================================================
# 批量获取（从计划 JSON）
# ===========================================================================


def fetch_from_plan(plan):
    """
    从计划 JSON 批量获取监管文件

    plan 格式（与 01_plan.md 输出的 regulatory_filings 字段一致）：
    {
      "sec_edgar": {"companies": ["AAPL", "MSFT"], "filing_types": ["10-K"]},
      "cninfo": {"companies": ["贵州茅台"], "types": ["年报"]},
      "hkex": {"companies": ["03690.HK"]},
      "edinet": {"companies": ["トヨタ自動車"]}
    }
    """
    all_results = []
    errors = []

    # SEC EDGAR
    if "sec_edgar" in plan:
        cfg = plan["sec_edgar"]
        companies = cfg.get("companies", [])
        filing_types = cfg.get("filing_types", ["10-K"])
        for company in companies:
            for ft in filing_types:
                try:
                    all_results.extend(
                        fetch_sec_edgar_search(company=company, filing_type=ft)
                    )
                    time.sleep(0.5)  # SEC 速率控制
                except Exception as e:
                    errors.append(f"sec_edgar/{company}/{ft}: {e}")

    # 巨潮
    if "cninfo" in plan:
        cfg = plan["cninfo"]
        companies = cfg.get("companies", [])
        types = cfg.get("types", ["年报"])
        for company in companies:
            for ft in types:
                try:
                    all_results.extend(fetch_cninfo(company=company, filing_type=ft))
                except Exception as e:
                    errors.append(f"cninfo/{company}/{ft}: {e}")

    # 港交所
    if "hkex" in plan:
        cfg = plan["hkex"]
        for company in cfg.get("companies", []):
            try:
                all_results.extend(fetch_hkex(company=company))
            except Exception as e:
                errors.append(f"hkex/{company}: {e}")

    # EDINET
    if "edinet" in plan:
        cfg = plan["edinet"]
        for company in cfg.get("companies", []):
            try:
                all_results.extend(fetch_edinet(company=company))
            except Exception as e:
                errors.append(f"edinet/{company}: {e}")

    return all_results, errors


# ===========================================================================
# CLI 入口
# ===========================================================================


def main():
    parser = argparse.ArgumentParser(description="监管申报文件获取 (v5.0)")
    parser.add_argument("--source", help="数据源 (sec_edgar/cninfo/hkex/edinet)")
    parser.add_argument("--plan", help="批量获取计划 JSON 文件路径")
    parser.add_argument("--company", default="", help="公司名称或股票代码")
    parser.add_argument("--query", default="", help="全文搜索关键词 (SEC EDGAR)")
    parser.add_argument(
        "--filing-type", default="", help="文件类型 (10-K/10-Q/年报 等)"
    )
    parser.add_argument("--cik", default="", help="SEC CIK 号码 (用于 XBRL 查询)")
    parser.add_argument(
        "--max-results", type=int, default=10, help="最大结果数（默认 10）"
    )
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    print(f"[REGULATORY] v5.0 监管申报文件获取")

    all_results = []
    errors = []

    if args.plan:
        try:
            with open(args.plan, "r", encoding="utf-8") as f:
                plan = json.load(f)
            print(f"[REGULATORY] 批量模式：从 {args.plan} 加载计划")
            all_results, errors = fetch_from_plan(plan)
        except Exception as e:
            print(f"[REGULATORY] 计划文件加载失败: {e}")
            errors.append(str(e))
    elif args.source:
        source = args.source.lower()
        print(f"[REGULATORY] 单源模式：{source}")

        dispatch = {
            "sec_edgar": lambda: fetch_sec_edgar_search(
                query=args.query,
                company=args.company,
                filing_type=args.filing_type,
                max_results=args.max_results,
            ),
            "sec_xbrl": lambda: fetch_sec_xbrl(args.cik, args.filing_type or "10-K"),
            "cninfo": lambda: fetch_cninfo(
                args.company, args.filing_type, args.max_results
            ),
            "hkex": lambda: fetch_hkex(args.company, args.max_results),
            "edinet": lambda: fetch_edinet(args.company, args.max_results),
        }

        if source in dispatch:
            try:
                all_results = dispatch[source]()
            except Exception as e:
                errors.append(f"{source}: {e}")
        else:
            print(f"[REGULATORY] 未知数据源: {source}")
            sys.exit(1)
    else:
        print("[REGULATORY] 请指定 --source 或 --plan")
        parser.print_help()
        sys.exit(1)

    output = {
        "fetch_time": datetime.now().isoformat(),
        "total_filings": len(all_results),
        "filings": all_results,
        "errors": errors,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[REGULATORY] 完成: {len(all_results)} 份文件, {len(errors)} 个错误")
    print(f"[REGULATORY] 输出 → {args.output}")
    if errors:
        for e in errors:
            print(f"  [错误] {e}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
政府/国际组织数据统一获取接口 (v5.0 新增)

支持数据源：
  - 世界银行 Open Data
  - IMF WEO
  - FRED (美联储经济数据)
  - 中国国家统计局
  - OECD
  - Eurostat
  - ClinicalTrials.gov
  - EPA FRS
  - data.gov
  - UN Comtrade

用法：
  python fetch_gov_data.py --source worldbank --indicator "NY.GDP.MKTP.KD.ZG" --country "CN;US;JP" --years 10 --output worldbank.json
  python fetch_gov_data.py --source imf --dataset "WEO" --country "CHN" --output imf_weo.json
  python fetch_gov_data.py --source fred --series "GDP;UNRATE;CPIAUCSL" --years 5 --output fred.json
  python fetch_gov_data.py --source china_stats --indicator "A0201" --output china_stats.json
  python fetch_gov_data.py --source oecd --dataset "GREEN_GROWTH" --country "OECD" --output oecd.json
  python fetch_gov_data.py --source eurostat --dataset "nama_10_gdp" --output eurostat.json
  python fetch_gov_data.py --source clinical_trials --condition "diabetes" --status "recruiting" --output ct.json
  python fetch_gov_data.py --source epa --query "facility" --state "CA" --output epa.json
  python fetch_gov_data.py --source data_gov --query "unemployment" --output datagov.json
  python fetch_gov_data.py --source un_comtrade --reporter "156" --partner "840" --year "2023" --output comtrade.json

  # 批量获取（从 JSON 计划文件）
  python fetch_gov_data.py --plan gov_data_plan.json --output gov_data.json

设计原则：
  - 每个数据源独立函数，失败跳过不影响其他
  - 统一输出格式：{source, indicator, country, year, value, unit, raw_data}
  - 降级逻辑：单个数据源超时或报错 → 记录错误 → 继续下一个
"""

import argparse
import json
import os
import sys
from datetime import datetime


TIMEOUT = 30
USER_AGENT = "DeepResearchPro/5.0 (research-tool)"


def _get(url, params=None, headers=None, timeout=TIMEOUT):
    """统一 HTTP GET，返回 response 对象"""
    import requests

    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp


def _normalize(source, indicator, country, year, value, unit="", raw_data=None):
    """统一输出格式"""
    return {
        "source": source,
        "indicator": indicator,
        "country": country,
        "year": year,
        "value": value,
        "unit": unit,
        "raw_data": raw_data or {},
        "tier": 0,
        "fetch_time": datetime.now().isoformat(),
    }


# ===========================================================================
# 世界银行 Open Data
# ===========================================================================


def fetch_worldbank(indicator, countries="all", years=10):
    """
    世界银行 API v2
    https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json
    """
    results = []
    country_str = countries if countries != "all" else "all"
    # 世界银行 API 用分号分隔国家
    url = f"https://api.worldbank.org/v2/country/{country_str}/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": 500,
        "date": f"{datetime.now().year - years}:{datetime.now().year}",
    }

    try:
        resp = _get(url, params=params)
        data = resp.json()
        if isinstance(data, list) and len(data) > 1:
            for item in data[1]:
                if item.get("value") is not None:
                    results.append(
                        _normalize(
                            source="worldbank",
                            indicator=indicator,
                            country=item.get("country", {}).get("id", ""),
                            year=item.get("date", ""),
                            value=item["value"],
                            unit=item.get("indicator", {}).get("value", ""),
                            raw_data=item,
                        )
                    )
        print(f"  [WorldBank] {indicator} → {len(results)} 条数据")
    except Exception as e:
        print(f"  [WorldBank] {indicator} 失败: {e}")

    return results


# ===========================================================================
# IMF WEO (World Economic Outlook)
# ===========================================================================


def fetch_imf(dataset="WEO", country="CHN"):
    """
    IMF DataMapper API
    https://www.imf.org/external/datamapper/api/v1/{indicator}/{country}
    """
    results = []
    # 获取可用指标列表
    base_url = "https://www.imf.org/external/datamapper/api/v1"

    try:
        # 获取常见 WEO 指标
        indicators = ["NGDP_RPCH", "PCPIPCH", "LUR", "BCA_NGDPD"]
        for ind in indicators:
            try:
                url = f"{base_url}/{ind}/{country}"
                resp = _get(url)
                data = resp.json()
                values = data.get("values", {}).get(ind, {}).get(country, {})
                for year_str, val in values.items():
                    results.append(
                        _normalize(
                            source="imf",
                            indicator=ind,
                            country=country,
                            year=year_str,
                            value=val,
                            unit="percent" if "PCH" in ind or "LUR" in ind else "ratio",
                        )
                    )
            except Exception:
                continue
        print(f"  [IMF] {dataset}/{country} → {len(results)} 条数据")
    except Exception as e:
        print(f"  [IMF] {dataset}/{country} 失败: {e}")

    return results


# ===========================================================================
# FRED (美联储经济数据)
# ===========================================================================


def fetch_fred(series_ids, years=5):
    """
    FRED API
    https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key=...&file_type=json
    """
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        print("  [FRED] FRED_API_KEY 未设置，跳过")
        return []

    results = []
    start_date = f"{datetime.now().year - years}-01-01"

    for series_id in series_ids:
        try:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "desc",
                "limit": 100,
            }
            resp = _get(url, params=params)
            data = resp.json()

            # 获取系列信息
            series_info_url = "https://api.stlouisfed.org/fred/series"
            series_params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
            }
            try:
                series_resp = _get(series_info_url, params=series_params)
                series_data = series_resp.json()
                unit = series_data.get("seriess", [{}])[0].get("units", "")
            except Exception:
                unit = ""

            for obs in data.get("observations", []):
                val = obs.get("value", "")
                if val and val != ".":
                    results.append(
                        _normalize(
                            source="fred",
                            indicator=series_id,
                            country="US",
                            year=obs.get("date", ""),
                            value=float(val),
                            unit=unit,
                            raw_data=obs,
                        )
                    )
            print(
                f"  [FRED] {series_id} → {len([r for r in results if r['indicator'] == series_id])} 条"
            )
        except Exception as e:
            print(f"  [FRED] {series_id} 失败: {e}")

    return results


# ===========================================================================
# 中国国家统计局
# ===========================================================================


def fetch_china_stats(indicator, dbcode="hgnd"):
    """
    中国国家统计局数据接口
    https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj&wds=[]&dfwds=[{"wdcode":"zb","valuecode":"..."}]
    """
    results = []
    try:
        url = "https://data.stats.gov.cn/easyquery.htm"
        params = {
            "m": "QueryData",
            "dbcode": dbcode,
            "rowcode": "zb",
            "colcode": "sj",
            "wds": "[]",
            "dfwds": json.dumps([{"wdcode": "zb", "valuecode": indicator}]),
        }
        headers = {
            "Referer": "https://data.stats.gov.cn/easyquery.htm",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        resp = _get(url, params=params, headers=headers)
        data = resp.json()

        if data.get("returncode") == 200:
            nodes = data.get("returndata", {}).get("datanodes", [])
            for node in nodes:
                val = node.get("data", {}).get("data", None)
                if val is not None:
                    wds = {
                        w["wdcode"]: w.get("valuecode", "") for w in node.get("wds", [])
                    }
                    results.append(
                        _normalize(
                            source="china_stats",
                            indicator=indicator,
                            country="CN",
                            year=wds.get("sj", ""),
                            value=val,
                            unit=node.get("data", {}).get("unit", ""),
                            raw_data=node,
                        )
                    )
        print(f"  [ChinaStats] {indicator} → {len(results)} 条数据")
    except Exception as e:
        print(f"  [ChinaStats] {indicator} 失败: {e}")

    return results


# ===========================================================================
# OECD
# ===========================================================================


def fetch_oecd(dataset, country="OECD"):
    """
    OECD SDMX-JSON API
    https://stats.oecd.org/SDMX-JSON/data/{dataset}/{country}+.../all
    """
    results = []
    try:
        url = f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{country}/all"
        params = {"detail": "dataonly", "dimensionAtObservation": "allDimensions"}
        resp = _get(url, params=params, timeout=60)
        data = resp.json()

        # SDMX-JSON 格式解析
        datasets = data.get("dataSets", [])
        if datasets:
            observations = datasets[0].get("observations", {})
            structure = (
                data.get("structure", {}).get("dimensions", {}).get("observation", [])
            )

            # 简化解析：提取时间维度和值
            time_dim = None
            for dim in structure:
                if dim.get("id") in ("TIME_PERIOD", "TIME", "time"):
                    time_dim = dim
                    break

            count = 0
            for key, val_arr in observations.items():
                if val_arr and val_arr[0] is not None:
                    results.append(
                        _normalize(
                            source="oecd",
                            indicator=dataset,
                            country=country,
                            year=key,
                            value=val_arr[0],
                        )
                    )
                    count += 1
                    if count >= 200:  # 限制结果数
                        break

        print(f"  [OECD] {dataset}/{country} → {len(results)} 条数据")
    except Exception as e:
        print(f"  [OECD] {dataset}/{country} 失败: {e}")

    return results


# ===========================================================================
# Eurostat
# ===========================================================================


def fetch_eurostat(dataset):
    """
    Eurostat JSON API
    https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?format=JSON
    """
    results = []
    try:
        url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
        params = {"format": "JSON", "lang": "EN"}
        resp = _get(url, params=params, timeout=60)
        data = resp.json()

        # 解析 Eurostat JSON-stat 格式
        values = data.get("value", {})
        dims = data.get("dimension", {})
        time_dim = dims.get("time", {}).get("category", {}).get("index", {})
        geo_dim = dims.get("geo", {}).get("category", {}).get("label", {})

        count = 0
        for idx_str, val in values.items():
            if val is not None:
                results.append(
                    _normalize(
                        source="eurostat",
                        indicator=dataset,
                        country="EU",
                        year=idx_str,
                        value=val,
                    )
                )
                count += 1
                if count >= 200:
                    break

        print(f"  [Eurostat] {dataset} → {len(results)} 条数据")
    except Exception as e:
        print(f"  [Eurostat] {dataset} 失败: {e}")

    return results


# ===========================================================================
# ClinicalTrials.gov
# ===========================================================================


def fetch_clinical_trials(condition="", status="", keyword="", max_results=20):
    """
    ClinicalTrials.gov API v2
    https://clinicaltrials.gov/api/v2/studies?query.cond=...&query.term=...&filter.overallStatus=...
    """
    results = []
    try:
        url = "https://clinicaltrials.gov/api/v2/studies"
        params = {"pageSize": min(max_results, 100), "format": "json"}
        if condition:
            params["query.cond"] = condition
        if keyword:
            params["query.term"] = keyword
        if status:
            params["filter.overallStatus"] = status

        resp = _get(url, params=params)
        data = resp.json()

        for study in data.get("studies", []):
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})

            results.append(
                _normalize(
                    source="clinical_trials",
                    indicator=condition or keyword,
                    country="",
                    year=status_module.get("studyFirstSubmitDate", ""),
                    value=id_module.get("nctId", ""),
                    unit="study",
                    raw_data={
                        "nct_id": id_module.get("nctId", ""),
                        "title": id_module.get("briefTitle", ""),
                        "status": status_module.get("overallStatus", ""),
                        "start_date": status_module.get("startDateStruct", {}).get(
                            "date", ""
                        ),
                        "phase": (design_module.get("phases", [None]) or [None])[0],
                        "enrollment": design_module.get("enrollmentInfo", {}).get(
                            "count", ""
                        ),
                    },
                )
            )

        print(f"  [ClinicalTrials] {condition or keyword} → {len(results)} 条")
    except Exception as e:
        print(f"  [ClinicalTrials] {condition or keyword} 失败: {e}")

    return results


# ===========================================================================
# EPA FRS (Facility Registry Service)
# ===========================================================================


def fetch_epa(query="", state="", max_results=20):
    """
    EPA Envirofacts API
    https://data.epa.gov/efservice/{table}/rows/{start}:{end}/JSON
    """
    results = []
    try:
        # 使用 FRS 设施查询
        url = "https://data.epa.gov/efservice/FRS_FACILITY_SITE"
        if state:
            url += f"/STATE_CODE/{state}"
        url += f"/rows/0:{max_results}/JSON"

        resp = _get(url)
        data = resp.json()

        for facility in data:
            results.append(
                _normalize(
                    source="epa",
                    indicator="facility",
                    country="US",
                    year="",
                    value=facility.get("REGISTRY_ID", ""),
                    unit="facility",
                    raw_data={
                        "name": facility.get("PRIMARY_NAME", ""),
                        "state": facility.get("STATE_CODE", ""),
                        "city": facility.get("CITY_NAME", ""),
                        "registry_id": facility.get("REGISTRY_ID", ""),
                    },
                )
            )

        print(f"  [EPA] {state or 'all'} → {len(results)} 条")
    except Exception as e:
        print(f"  [EPA] 查询失败: {e}")

    return results


# ===========================================================================
# data.gov (CKAN API)
# ===========================================================================


def fetch_data_gov(query, max_results=10):
    """
    data.gov CKAN API
    https://catalog.data.gov/api/3/action/package_search?q=...
    """
    results = []
    try:
        url = "https://catalog.data.gov/api/3/action/package_search"
        params = {"q": query, "rows": max_results}
        resp = _get(url, params=params)
        data = resp.json()

        if data.get("success"):
            for pkg in data.get("result", {}).get("results", []):
                resources = pkg.get("resources", [])
                csv_urls = [
                    r.get("url", "")
                    for r in resources
                    if r.get("format", "").upper() in ("CSV", "JSON", "XML")
                ]
                results.append(
                    _normalize(
                        source="data_gov",
                        indicator=query,
                        country="US",
                        year=pkg.get("metadata_modified", "")[:4],
                        value=pkg.get("title", ""),
                        unit="dataset",
                        raw_data={
                            "title": pkg.get("title", ""),
                            "notes": (pkg.get("notes", "") or "")[:500],
                            "organization": pkg.get("organization", {}).get(
                                "title", ""
                            ),
                            "resource_count": len(resources),
                            "data_urls": csv_urls[:3],
                        },
                    )
                )

        print(f"  [data.gov] '{query}' → {len(results)} 条")
    except Exception as e:
        print(f"  [data.gov] '{query}' 失败: {e}")

    return results


# ===========================================================================
# UN Comtrade
# ===========================================================================


def fetch_un_comtrade(reporter="", partner="", year="", commodity="TOTAL"):
    """
    UN Comtrade API (v1 公共接口，限量免费)
    https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=...&period=...
    """
    results = []
    try:
        url = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
        params = {
            "reporterCode": reporter,
            "period": year,
            "partnerCode": partner,
            "cmdCode": commodity,
            "flowCode": "M,X",
            "maxRecords": 100,
        }
        # 清理空参数
        params = {k: v for k, v in params.items() if v}

        resp = _get(url, params=params, timeout=60)
        data = resp.json()

        for record in data.get("data", []):
            flow = "Export" if record.get("flowCode") == "X" else "Import"
            results.append(
                _normalize(
                    source="un_comtrade",
                    indicator=f"{flow}_{record.get('cmdDesc', '')}",
                    country=record.get("reporterDesc", ""),
                    year=str(record.get("period", "")),
                    value=record.get("primaryValue", 0),
                    unit="USD",
                    raw_data={
                        "flow": flow,
                        "reporter": record.get("reporterDesc", ""),
                        "partner": record.get("partnerDesc", ""),
                        "commodity": record.get("cmdDesc", ""),
                        "value": record.get("primaryValue", 0),
                        "qty": record.get("qty", 0),
                    },
                )
            )

        print(f"  [UN Comtrade] {reporter}→{partner} {year} → {len(results)} 条")
    except Exception as e:
        print(f"  [UN Comtrade] 查询失败: {e}")

    return results


# ===========================================================================
# 批量获取（从计划 JSON）
# ===========================================================================


def fetch_from_plan(plan):
    """
    从计划 JSON 批量获取政府数据

    plan 格式（与 01_plan.md 输出的 gov_data_sources 字段一致）：
    {
      "worldbank": {"indicators": ["NY.GDP.MKTP.KD.ZG"], "countries": "CN;US", "years": 10},
      "imf": {"dataset": "WEO", "country": "CHN"},
      "fred": {"series": ["GDP", "UNRATE"], "years": 5},
      "china_stats": {"indicators": ["A0201"]},
      "clinical_trials": {"condition": "diabetes", "status": "recruiting"},
      ...
    }
    """
    all_results = []
    errors = []

    # 世界银行
    if "worldbank" in plan:
        cfg = plan["worldbank"]
        indicators = cfg.get("indicators", [])
        countries = cfg.get("countries", "all")
        if isinstance(countries, list):
            countries = ";".join(countries)
        years = cfg.get("years", 10)
        for ind in indicators:
            try:
                all_results.extend(fetch_worldbank(ind, countries, years))
            except Exception as e:
                errors.append(f"worldbank/{ind}: {e}")

    # IMF
    if "imf" in plan:
        cfg = plan["imf"]
        try:
            all_results.extend(
                fetch_imf(cfg.get("dataset", "WEO"), cfg.get("country", "CHN"))
            )
        except Exception as e:
            errors.append(f"imf: {e}")

    # FRED
    if "fred" in plan:
        cfg = plan["fred"]
        series = cfg.get("series", [])
        years = cfg.get("years", 5)
        try:
            all_results.extend(fetch_fred(series, years))
        except Exception as e:
            errors.append(f"fred: {e}")

    # 中国国家统计局
    if "china_stats" in plan:
        cfg = plan["china_stats"]
        indicators = cfg.get("indicators", [])
        dbcode = cfg.get("dbcode", "hgnd")
        for ind in indicators:
            try:
                all_results.extend(fetch_china_stats(ind, dbcode))
            except Exception as e:
                errors.append(f"china_stats/{ind}: {e}")

    # OECD
    if "oecd" in plan:
        cfg = plan["oecd"]
        try:
            all_results.extend(
                fetch_oecd(cfg.get("dataset", ""), cfg.get("country", "OECD"))
            )
        except Exception as e:
            errors.append(f"oecd: {e}")

    # Eurostat
    if "eurostat" in plan:
        cfg = plan["eurostat"]
        try:
            all_results.extend(fetch_eurostat(cfg.get("dataset", "")))
        except Exception as e:
            errors.append(f"eurostat: {e}")

    # ClinicalTrials.gov
    if "clinical_trials" in plan:
        cfg = plan["clinical_trials"]
        try:
            all_results.extend(
                fetch_clinical_trials(
                    condition=cfg.get("condition", ""),
                    status=cfg.get("status", ""),
                    keyword=cfg.get("keyword", ""),
                )
            )
        except Exception as e:
            errors.append(f"clinical_trials: {e}")

    # EPA
    if "epa" in plan:
        cfg = plan["epa"]
        try:
            all_results.extend(
                fetch_epa(
                    query=cfg.get("query", ""),
                    state=cfg.get("state", ""),
                )
            )
        except Exception as e:
            errors.append(f"epa: {e}")

    # data.gov
    if "data_gov" in plan:
        cfg = plan["data_gov"]
        try:
            all_results.extend(fetch_data_gov(cfg.get("query", "")))
        except Exception as e:
            errors.append(f"data_gov: {e}")

    # UN Comtrade
    if "un_comtrade" in plan:
        cfg = plan["un_comtrade"]
        try:
            all_results.extend(
                fetch_un_comtrade(
                    reporter=cfg.get("reporter", ""),
                    partner=cfg.get("partner", ""),
                    year=cfg.get("year", ""),
                    commodity=cfg.get("commodity", "TOTAL"),
                )
            )
        except Exception as e:
            errors.append(f"un_comtrade: {e}")

    return all_results, errors


# ===========================================================================
# CLI 入口
# ===========================================================================


def main():
    parser = argparse.ArgumentParser(description="政府/国际组织数据统一获取接口 (v5.0)")
    parser.add_argument(
        "--source",
        help="数据源名称 (worldbank/imf/fred/china_stats/oecd/eurostat/clinical_trials/epa/data_gov/un_comtrade)",
    )
    parser.add_argument("--plan", help="批量获取计划 JSON 文件路径")
    parser.add_argument("--indicator", help="指标 ID")
    parser.add_argument("--dataset", help="数据集名称")
    parser.add_argument("--country", default="", help="国家代码，多个用分号分隔")
    parser.add_argument("--series", default="", help="FRED 系列 ID，多个用分号分隔")
    parser.add_argument("--years", type=int, default=10, help="获取年数（默认 10）")
    parser.add_argument("--condition", default="", help="ClinicalTrials 疾病条件")
    parser.add_argument("--status", default="", help="ClinicalTrials 试验状态")
    parser.add_argument("--query", default="", help="通用查询关键词")
    parser.add_argument("--state", default="", help="EPA 州代码")
    parser.add_argument("--reporter", default="", help="UN Comtrade 报告国代码")
    parser.add_argument("--partner", default="", help="UN Comtrade 伙伴国代码")
    parser.add_argument("--year", default="", help="UN Comtrade 年份")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    print(f"[GOV_DATA] v5.0 政府/国际组织数据获取")

    all_results = []
    errors = []

    if args.plan:
        # 批量模式
        try:
            with open(args.plan, "r", encoding="utf-8") as f:
                plan = json.load(f)
            print(f"[GOV_DATA] 批量模式：从 {args.plan} 加载计划")
            all_results, errors = fetch_from_plan(plan)
        except Exception as e:
            print(f"[GOV_DATA] 计划文件加载失败: {e}")
            errors.append(str(e))
    elif args.source:
        # 单源模式
        source = args.source.lower()
        print(f"[GOV_DATA] 单源模式：{source}")

        dispatch = {
            "worldbank": lambda: fetch_worldbank(
                args.indicator or "", args.country or "all", args.years
            ),
            "imf": lambda: fetch_imf(args.dataset or "WEO", args.country or "CHN"),
            "fred": lambda: fetch_fred(
                [s.strip() for s in args.series.split(";") if s.strip()], args.years
            ),
            "china_stats": lambda: fetch_china_stats(args.indicator or ""),
            "oecd": lambda: fetch_oecd(args.dataset or "", args.country or "OECD"),
            "eurostat": lambda: fetch_eurostat(args.dataset or ""),
            "clinical_trials": lambda: fetch_clinical_trials(
                condition=args.condition, status=args.status
            ),
            "epa": lambda: fetch_epa(query=args.query, state=args.state),
            "data_gov": lambda: fetch_data_gov(args.query),
            "un_comtrade": lambda: fetch_un_comtrade(
                reporter=args.reporter, partner=args.partner, year=args.year
            ),
        }

        if source in dispatch:
            try:
                all_results = dispatch[source]()
            except Exception as e:
                errors.append(f"{source}: {e}")
        else:
            print(f"[GOV_DATA] 未知数据源: {source}")
            print(f"[GOV_DATA] 支持的数据源: {', '.join(dispatch.keys())}")
            sys.exit(1)
    else:
        print("[GOV_DATA] 请指定 --source 或 --plan")
        parser.print_help()
        sys.exit(1)

    # 输出
    output = {
        "fetch_time": datetime.now().isoformat(),
        "source_count": len(set(r["source"] for r in all_results)),
        "total_records": len(all_results),
        "data": all_results,
        "errors": errors,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[GOV_DATA] 完成: {len(all_results)} 条数据, {len(errors)} 个错误")
    print(f"[GOV_DATA] 输出 → {args.output}")
    if errors:
        for e in errors:
            print(f"  [错误] {e}")


if __name__ == "__main__":
    main()

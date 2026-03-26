#!/usr/bin/env python3
"""
金融结构化数据获取脚本 — 腾讯财经 → Tushare 自动降级

用法：
  python fetch_financial_data.py \
    --finance-context finance_context.json \
    --output financial_data.json

输入格式（finance_context.json）：
  {
    "stock_codes": ["sh600519", "03690.HK"],
    "data_types": ["quote", "kline", "financial_report"],
    "period": "daily",
    "days": 365
  }
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# 腾讯财经
# ---------------------------------------------------------------------------


def fetch_tencent_quote(symbol: str) -> dict:
    """获取腾讯财经实时行情"""
    import requests

    resp = requests.get(f"http://qt.gtimg.cn/q={symbol}", timeout=10)
    text = resp.content.decode("gbk")
    fields = text.split("~")
    if len(fields) < 50:
        raise ValueError(f"腾讯财经返回数据字段不足: {len(fields)} 个（需要 50+）")

    return {
        "symbol": symbol,
        "name": fields[1],
        "price": float(fields[3]) if fields[3] else 0,
        "pre_close": float(fields[4]) if fields[4] else 0,
        "open": float(fields[5]) if fields[5] else 0,
        "change_pct": fields[32],
        "high": float(fields[33]) if fields[33] else 0,
        "low": float(fields[34]) if fields[34] else 0,
        "volume": fields[36],
        "amount": fields[37],
        "pe_ttm": fields[39],
        "pb": fields[46],
        "circ_mkt_cap": fields[44],
        "total_mkt_cap": fields[45],
        "source": "tencent",
    }


def fetch_tencent_kline(
    symbol: str, period: str = "day", count: int = 30, fq: str = "qfq"
) -> list:
    """获取腾讯财经历史K线"""
    import requests

    # 腾讯 API 使用 day/week/month，映射常见变体
    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    api_period = period_map.get(period, period)

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{symbol},{api_period},,,{count},{fq}"}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    key = f"{fq}{api_period}" if fq else api_period
    klines = data.get("data", {}).get(symbol, {}).get(key, [])
    return [
        {
            "date": k[0],
            "open": k[1],
            "close": k[2],
            "high": k[3],
            "low": k[4],
            "volume": k[5] if len(k) > 5 else "",
        }
        for k in klines
    ]


# ---------------------------------------------------------------------------
# Tushare 降级
# ---------------------------------------------------------------------------


def fetch_tushare_data(
    ts_code: str, data_type: str, start_date: str, end_date: str
) -> list:
    """Tushare 降级获取"""
    import tushare as ts

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN 未设置")
    ts.set_token(token)
    pro = ts.pro_api()

    if data_type == "daily":
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    elif data_type == "income":
        df = pro.income(ts_code=ts_code, start_date=start_date, end_date=end_date)
    elif data_type == "balancesheet":
        df = pro.balancesheet(ts_code=ts_code, start_date=start_date, end_date=end_date)
    else:
        return []

    return df.to_dict("records") if df is not None and not df.empty else []


def convert_to_tushare_code(symbol: str) -> str:
    """
    将腾讯格式转为 Tushare 格式。
    sh600519 → 600519.SH
    sz000001 → 000001.SZ
    000001.SZ → 000001.SZ（已是 Tushare 格式）
    """
    symbol = symbol.strip()
    if "." in symbol:
        return symbol.upper()
    if symbol.startswith("sh"):
        return symbol[2:] + ".SH"
    if symbol.startswith("sz"):
        return symbol[2:] + ".SZ"
    return symbol


def is_tencent_format(symbol: str) -> bool:
    """检查是否为腾讯财经支持的格式（sh/sz 前缀）"""
    s = symbol.strip().lower()
    return s.startswith("sh") or s.startswith("sz")


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------


def fetch_stock_data(
    symbol: str, data_types: list, period: str, days: int, errors: list
) -> dict:
    """获取单只股票的数据"""
    stock_data = {}

    # 日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    # 尝试腾讯财经
    tencent_ok = is_tencent_format(symbol)

    if tencent_ok:
        # 腾讯财经
        for dt in data_types:
            if dt == "quote":
                try:
                    stock_data["quote"] = fetch_tencent_quote(symbol)
                except Exception as e:
                    errors.append(f"腾讯行情 {symbol}: {e}")
                    # 降级到 Tushare
                    ts_code = convert_to_tushare_code(symbol)
                    try:
                        records = fetch_tushare_data(
                            ts_code, "daily", start_str, end_str
                        )
                        if records:
                            latest = records[0]
                            stock_data["quote"] = {
                                "symbol": symbol,
                                "name": "",
                                "price": latest.get("close", 0),
                                "source": "tushare",
                            }
                    except Exception as e2:
                        errors.append(f"Tushare 行情降级 {symbol}: {e2}")

            elif dt == "kline":
                try:
                    stock_data["kline"] = fetch_tencent_kline(
                        symbol, period=period, count=days, fq="qfq"
                    )
                except Exception as e:
                    errors.append(f"腾讯K线 {symbol}: {e}")
                    ts_code = convert_to_tushare_code(symbol)
                    try:
                        records = fetch_tushare_data(
                            ts_code, "daily", start_str, end_str
                        )
                        stock_data["kline"] = records
                        stock_data["source"] = "tushare"
                    except Exception as e2:
                        errors.append(f"Tushare K线降级 {symbol}: {e2}")

            elif dt in ("income", "balancesheet", "financial_report"):
                ts_code = convert_to_tushare_code(symbol)
                try:
                    actual_type = "income" if dt == "financial_report" else dt
                    records = fetch_tushare_data(
                        ts_code, actual_type, start_str, end_str
                    )
                    stock_data[dt] = records
                except Exception as e:
                    errors.append(f"Tushare {dt} {symbol}: {e}")

        if "source" not in stock_data:
            stock_data["source"] = "tencent"
    else:
        # 非腾讯格式 → 直接使用 Tushare
        ts_code = convert_to_tushare_code(symbol)
        for dt in data_types:
            actual_type = dt
            if dt == "quote":
                actual_type = "daily"
            elif dt == "financial_report":
                actual_type = "income"

            try:
                records = fetch_tushare_data(ts_code, actual_type, start_str, end_str)
                if dt == "quote" and records:
                    latest = records[0]
                    stock_data["quote"] = {
                        "symbol": symbol,
                        "name": "",
                        "price": latest.get("close", 0),
                        "source": "tushare",
                    }
                else:
                    stock_data[dt] = records
            except Exception as e:
                errors.append(f"Tushare {dt} {symbol}: {e}")

        stock_data["source"] = "tushare"

    return stock_data


def main():
    parser = argparse.ArgumentParser(
        description="金融结构化数据获取（腾讯财经 → Tushare 自动降级）"
    )
    parser.add_argument(
        "--finance-context", required=True, help="金融上下文 JSON 文件路径"
    )
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    # 加载上下文
    try:
        with open(args.finance_context, "r", encoding="utf-8") as f:
            ctx = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FINANCE] 上下文文件加载失败: {e}")
        output = {
            "fetch_time": datetime.now().isoformat(),
            "stocks": {},
            "errors": [str(e)],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return

    stock_codes = ctx.get("stock_codes", [])
    data_types = ctx.get("data_types", ["quote", "kline"])
    period = ctx.get("period", "daily")
    days = ctx.get("days", 365)

    print(f"[FINANCE] 股票代码: {stock_codes}")
    print(f"[FINANCE] 数据类型: {data_types} 周期: {period} 天数: {days}")

    errors = []
    stocks = {}

    for symbol in stock_codes:
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        symbol = symbol.strip()
        print(f"[FINANCE] 获取 {symbol}...")
        stock_data = fetch_stock_data(symbol, data_types, period, days, errors)
        if stock_data:
            stocks[symbol] = stock_data
            print(f"  → 获取成功（source={stock_data.get('source', 'unknown')}）")
        else:
            print(f"  → 无数据")

    output = {
        "fetch_time": datetime.now().isoformat(),
        "stocks": stocks,
        "errors": errors,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[FINANCE] 完成: {len(stocks)} 只股票, {len(errors)} 个错误")
    print(f"[FINANCE] 输出 → {args.output}")
    if errors:
        for e in errors:
            print(f"  [错误] {e}")


if __name__ == "__main__":
    main()

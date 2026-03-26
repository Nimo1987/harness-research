#!/usr/bin/env python3
"""
信源全文获取脚本 (v5.0 新增)

核心逻辑：
  1. 输入：通过初筛的 top N 信源 URL 列表
  2. 使用 requests + BeautifulSoup 获取页面
  3. 正文提取（去除导航栏/广告/页脚），使用 readability 算法
  4. 编码自动检测（GBK/UTF-8/ISO-8859-1）
  5. 限制每篇 3000 字
  6. JavaScript 渲染页面标记为「无法获取全文」
  7. 并行获取（ThreadPoolExecutor, max_workers=5）
  8. 遵守 robots.txt
  9. 输出：{url_hash}.json

用法：
  # 从 URL 列表文件获取
  python fetch_full_content.py --urls-file top_sources.json --output-dir sources/full_content --output-summary full_content.json

  # 从标准输入获取单个 URL
  python fetch_full_content.py --url "https://example.com/article" --output full_content.json

用途：CRAAP 评估和章节分析将使用全文替代 snippet，显著提升评估和分析质量。
"""

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


TIMEOUT = 15
MAX_CHARS = 3000
MAX_WORKERS = 5
USER_AGENT = "DeepResearchPro/5.0 (research-tool)"

# 已知付费墙/反爬严格的域名 — 这些域名大概率返回 403 或空内容
# 全文获取时降低优先级，优先抓取可访问的信源
PAYWALL_DOMAINS = {
    "sciencedirect.com",
    "elsevier.com",  # Elsevier 系
    "onlinelibrary.wiley.com",
    "wiley.com",  # Wiley
    "tandfonline.com",  # Taylor & Francis
    "sagepub.com",  # SAGE
    "mdpi.com",  # MDPI (部分开放但反爬严格)
    "ieeexplore.ieee.org",  # IEEE
    "dl.acm.org",  # ACM
    "jstor.org",  # JSTOR
    "cnki.net",  # 知网
    "wanfangdata.com.cn",  # 万方
    "cqvip.com",  # 维普
    "ft.com",  # 金融时报
    "wsj.com",  # 华尔街日报
    "economist.com",  # 经济学人
    "theinformation.com",  # The Information
    "bloomberg.com",  # 彭博 (部分)
}


def is_paywall_domain(url):
    """检查 URL 是否属于已知付费墙域名"""
    try:
        domain = urlparse(url).netloc.lower()
        return any(pw in domain for pw in PAYWALL_DOMAINS)
    except Exception:
        return False


def url_hash(url):
    """URL 的短 hash，用于文件名"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def check_robots_txt(url):
    """检查 robots.txt 是否允许爬取"""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True  # 无法获取 robots.txt 时默认允许


def detect_encoding(response):
    """自动检测页面编码"""
    # 1. 优先使用 HTTP 头中的编码
    content_type = response.headers.get("content-type", "")
    if "charset=" in content_type.lower():
        charset = content_type.lower().split("charset=")[-1].strip().split(";")[0]
        return charset

    # 2. 从 HTML meta 标签检测
    raw = response.content[:4096]
    meta_match = re.search(rb'<meta[^>]+charset=["\']?([^"\'\s>]+)', raw, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1).decode("ascii", errors="ignore")

    # 3. 尝试常见编码
    for enc in ["utf-8", "gbk", "gb2312", "big5", "euc-jp", "euc-kr", "iso-8859-1"]:
        try:
            response.content.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    return "utf-8"


def extract_text_content(html, url=""):
    """
    从 HTML 提取正文内容（去除导航栏/广告/页脚）

    使用简化版 readability 算法：
    1. 移除 script/style/nav/footer/header/aside 标签
    2. 根据文本密度评分每个块级元素
    3. 选择得分最高的区域作为正文
    """
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "lxml")

    # 移除不需要的标签
    for tag in soup.find_all(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "noscript",
            "iframe",
            "svg",
            "form",
        ]
    ):
        tag.decompose()

    # 移除注释
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 移除常见广告/导航 class/id
    noise_patterns = re.compile(
        r"(nav|menu|sidebar|footer|header|banner|advert|social|share|comment|"
        r"related|recommend|breadcrumb|pagination|copyright|disclaimer)",
        re.IGNORECASE,
    )
    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        if noise_patterns.search(classes) or noise_patterns.search(tag_id):
            tag.decompose()

    # 尝试找 article 或 main 标签
    article = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"content|article|post|entry", re.I))
    )

    if article:
        text = article.get_text(separator="\n", strip=True)
    else:
        # 降级：找文本最密集的 div
        candidates = []
        for div in soup.find_all(["div", "section", "td"]):
            text = div.get_text(separator=" ", strip=True)
            if len(text) > 200:
                # 计算文本密度：文本长度 / HTML 长度
                html_len = len(str(div))
                density = len(text) / max(html_len, 1)
                candidates.append((density * len(text), text))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            text = candidates[0][1]
        else:
            text = soup.get_text(separator="\n", strip=True)

    # 清理文本
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()

    return text


def is_js_rendered_page(html):
    """
    检测是否为 JavaScript 渲染页面（内容极少但有大量 JS）
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    body = soup.find("body")
    if not body:
        return True

    text = body.get_text(strip=True)
    scripts = soup.find_all("script")

    # 如果文本很少但 JS 很多，可能是 SPA
    if len(text) < 200 and len(scripts) > 5:
        return True

    # 检查常见 SPA 框架标识
    for script in scripts:
        src = script.get("src", "")
        if any(fw in src for fw in ["react", "vue", "angular", "next", "nuxt"]):
            if len(text) < 500:
                return True

    return False


def fetch_single_url(url, respect_robots=True):
    """
    获取单个 URL 的全文

    返回:
    {
      "url": "...",
      "url_hash": "...",
      "title": "...",
      "full_text": "...",
      "char_count": 1234,
      "encoding": "utf-8",
      "status": "success" | "robots_blocked" | "js_rendered" | "error",
      "error": "",
      "fetch_time": "..."
    }
    """
    import requests

    result = {
        "url": url,
        "url_hash": url_hash(url),
        "title": "",
        "full_text": "",
        "char_count": 0,
        "encoding": "",
        "status": "error",
        "error": "",
        "fetch_time": datetime.now().isoformat(),
    }

    try:
        # 检查 robots.txt
        if respect_robots and not check_robots_txt(url):
            result["status"] = "robots_blocked"
            result["error"] = "robots.txt 不允许爬取"
            print(f"    [{url_hash(url)}] robots.txt 阻止: {url[:60]}")
            return result

        # 获取页面
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
        }
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)

        # 付费墙快速失败：403/401/payment required
        if resp.status_code in (401, 403, 407, 451):
            result["status"] = "paywall_or_forbidden"
            result["error"] = f"HTTP {resp.status_code}（可能是付费墙或访问限制）"
            print(f"    [{url_hash(url)}] {resp.status_code} 拒绝: {url[:60]}")
            return result

        resp.raise_for_status()

        # 检测编码
        encoding = detect_encoding(resp)
        result["encoding"] = encoding

        try:
            html = resp.content.decode(encoding, errors="replace")
        except (UnicodeDecodeError, LookupError):
            html = resp.content.decode("utf-8", errors="replace")

        # 检查 JS 渲染页面
        if is_js_rendered_page(html):
            result["status"] = "js_rendered"
            result["error"] = "JavaScript 渲染页面，无法获取全文"
            print(f"    [{url_hash(url)}] JS 渲染: {url[:60]}")
            return result

        # 提取标题
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else ""

        # 提取正文
        text = extract_text_content(html, url)

        # 限制字数
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n\n[全文截断，共 " + str(len(text)) + " 字]"

        result["full_text"] = text
        result["char_count"] = len(text)
        result["status"] = "success"

        print(f"    [{url_hash(url)}] 成功: {len(text)}字 - {url[:60]}")

    except Exception as e:
        result["error"] = str(e)
        print(f"    [{url_hash(url)}] 失败: {e} - {url[:60]}")

    return result


def fetch_batch(urls, max_workers=MAX_WORKERS, respect_robots=True, output_dir=None):
    """
    批量并行获取多个 URL 的全文

    Args:
        urls: URL 列表
        max_workers: 并行线程数
        respect_robots: 是否遵守 robots.txt
        output_dir: 可选，每个 URL 单独输出到此目录

    Returns:
        list[dict]: 获取结果列表
    """
    results = []

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 智能排序：可访问的 URL 优先，付费墙域名放后面
    free_urls = [u for u in urls if not is_paywall_domain(u)]
    paywall_urls = [u for u in urls if is_paywall_domain(u)]
    sorted_urls = free_urls + paywall_urls

    if paywall_urls:
        print(f"[FULL_CONTENT] {len(paywall_urls)} 个已知付费墙域名置于队列末尾")

    print(
        f"[FULL_CONTENT] 开始获取 {len(sorted_urls)} 个 URL（{max_workers} 并行线程）"
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(fetch_single_url, url, respect_robots): url
            for url in sorted_urls
        }

        for future in as_completed(future_map):
            url = future_map[future]
            try:
                result = future.result()
                results.append(result)

                # 单独输出到文件
                if output_dir and result["status"] == "success":
                    filepath = os.path.join(output_dir, f"{result['url_hash']}.json")
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

            except Exception as e:
                results.append(
                    {
                        "url": url,
                        "url_hash": url_hash(url),
                        "status": "error",
                        "error": str(e),
                    }
                )

    # 统计
    success = sum(1 for r in results if r.get("status") == "success")
    blocked = sum(1 for r in results if r.get("status") == "robots_blocked")
    js_page = sum(1 for r in results if r.get("status") == "js_rendered")
    failed = sum(1 for r in results if r.get("status") == "error")
    print(
        f"[FULL_CONTENT] 完成: 成功={success} 阻止={blocked} JS渲染={js_page} 失败={failed}"
    )

    return results


# ===========================================================================
# CLI 入口
# ===========================================================================


def main():
    parser = argparse.ArgumentParser(description="信源全文获取 (v5.0)")
    parser.add_argument("--url", help="单个 URL")
    parser.add_argument(
        "--urls-file", help="URL 列表 JSON 文件路径（JSON 数组或对象数组含 url 字段）"
    )
    parser.add_argument(
        "--output-dir", default=None, help="单独输出目录（每个 URL 一个文件）"
    )
    parser.add_argument("--output", required=True, help="汇总输出 JSON 文件路径")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_WORKERS,
        help=f"并行线程数（默认 {MAX_WORKERS}）",
    )
    parser.add_argument(
        "--max-sources", type=int, default=20, help="最大获取数量（默认 20）"
    )
    parser.add_argument("--no-robots", action="store_true", help="忽略 robots.txt")
    args = parser.parse_args()

    print("[FULL_CONTENT] v5.0 信源全文获取")

    urls = []

    if args.url:
        urls = [args.url]
    elif args.urls_file:
        try:
            with open(args.urls_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        urls.append(item)
                    elif isinstance(item, dict) and "url" in item:
                        urls.append(item["url"])
            elif isinstance(data, dict):
                # 可能是带信源信息的对象
                for key, val in data.items():
                    if isinstance(val, str) and val.startswith("http"):
                        urls.append(val)
        except Exception as e:
            print(f"[FULL_CONTENT] URL 文件加载失败: {e}")
            sys.exit(1)
    else:
        print("[FULL_CONTENT] 请指定 --url 或 --urls-file")
        parser.print_help()
        sys.exit(1)

    # 去重 + 限制数量
    seen = set()
    unique_urls = []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            unique_urls.append(u)
    urls = unique_urls[: args.max_sources]

    print(f"[FULL_CONTENT] {len(urls)} 个唯一 URL（限制 {args.max_sources}）")

    results = fetch_batch(
        urls,
        max_workers=args.max_workers,
        respect_robots=not args.no_robots,
        output_dir=args.output_dir,
    )

    output = {
        "fetch_time": datetime.now().isoformat(),
        "total_urls": len(urls),
        "results": results,
        "stats": {
            "success": sum(1 for r in results if r.get("status") == "success"),
            "robots_blocked": sum(
                1 for r in results if r.get("status") == "robots_blocked"
            ),
            "js_rendered": sum(1 for r in results if r.get("status") == "js_rendered"),
            "error": sum(1 for r in results if r.get("status") == "error"),
            "total_chars": sum(r.get("char_count", 0) for r in results),
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[FULL_CONTENT] 输出 → {args.output}")
    if args.output_dir:
        print(f"[FULL_CONTENT] 单文件输出 → {args.output_dir}/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
搜索结果去重脚本 v5.2
在搜索完成后立即去重，减少无效信源进入评估流水线。

用法：
  python dedup_sources.py \
    --input raw_search_results.json \
    --output raw_search_results_deduped.json \
    --stats dedup_stats.json

去重策略（三级）：
  1. URL 精确去重（规范化后：去 query/fragment、统一 http→https、去尾 /）
  2. 标题模糊去重（编辑距离 < 3 或 Jaccard > 0.8）
  3. 内容指纹去重（snippet 的 SimHash，海明距离 < 5）

保留策略：
  - 同一内容多个来源时，保留 tier 最高的那条
  - 记录被去重的 URL 到 stats，供方法论章节引用
"""

import argparse
import hashlib
import json
import re
from urllib.parse import urlparse, urlunparse


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
    except (json.JSONDecodeError, FileNotFoundError):
        return default


def normalize_url(url):
    """URL 规范化：去 query/fragment、统一 http→https、去尾 /、统一小写"""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = "https"  # 统一为 https
        netloc = parsed.netloc.lower().lstrip("www.")
        path = parsed.path.rstrip("/")
        # 去掉 query 和 fragment
        normalized = urlunparse((scheme, netloc, path, "", "", ""))
        return normalized
    except Exception:
        return url.strip().lower()


def edit_distance(s1, s2):
    """计算两个字符串的编辑距离（Levenshtein）"""
    if not s1:
        return len(s2) if s2 else 0
    if not s2:
        return len(s1)

    # 优化：先检查长度差
    if abs(len(s1) - len(s2)) > 5:
        return abs(len(s1) - len(s2))

    m, n = len(s1), len(s2)
    # 使用一维 DP
    prev = list(range(n + 1))
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev

    return prev[n]


def title_jaccard(t1, t2):
    """计算两个标题的词级 Jaccard 相似度"""
    if not t1 or not t2:
        return 0.0

    # 中英文混合分词
    words1 = set(re.findall(r"[\w\u4e00-\u9fff]+", t1.lower()))
    words2 = set(re.findall(r"[\w\u4e00-\u9fff]+", t2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def simhash(text, bits=64):
    """计算文本的 SimHash 指纹"""
    if not text or not isinstance(text, str):
        return 0

    # 分词（中英混合）
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())
    if not tokens:
        return 0

    v = [0] * bits
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= 1 << i

    return fingerprint


def hamming_distance(h1, h2):
    """计算两个整数的汉明距离"""
    x = h1 ^ h2
    count = 0
    while x:
        count += 1
        x &= x - 1
    return count


def get_tier(source):
    """获取信源 tier，默认 4"""
    tier = source.get("tier")
    if tier is not None:
        try:
            return int(tier)
        except (ValueError, TypeError):
            pass
    return 4


def main():
    parser = argparse.ArgumentParser(description="搜索去重 v5.2")
    parser.add_argument("--input", required=True, help="原始搜索结果 JSON")
    parser.add_argument("--output", required=True, help="去重后输出 JSON")
    parser.add_argument("--stats", required=True, help="去重统计 JSON")
    args = parser.parse_args()

    sources = safe_load_json(args.input, [])
    if not isinstance(sources, list):
        sources = []

    original_count = len(sources)
    print(f"[DEDUP] v5.2 搜索去重开始，原始信源: {original_count}")

    if original_count == 0:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        with open(args.stats, "w", encoding="utf-8") as f:
            json.dump({"original": 0, "deduped": 0, "removed": 0, "details": []}, f)
        print("[DEDUP] 无信源需要去重")
        return

    removed = []
    kept = []

    # 第一级：URL 精确去重
    url_map = {}
    for src in sources:
        if not isinstance(src, dict):
            continue
        url = src.get("url", "")
        norm_url = normalize_url(url)
        if not norm_url:
            kept.append(src)
            continue

        if norm_url in url_map:
            existing = url_map[norm_url]
            # 保留 tier 更高（数字更小）的
            if get_tier(src) < get_tier(existing):
                removed.append(
                    {
                        "url": existing.get("url", ""),
                        "reason": "URL 重复",
                        "kept": url,
                    }
                )
                url_map[norm_url] = src
            else:
                removed.append(
                    {
                        "url": url,
                        "reason": "URL 重复",
                        "kept": existing.get("url", ""),
                    }
                )
        else:
            url_map[norm_url] = src

    stage1_sources = list(url_map.values()) + kept
    url_dedup_count = original_count - len(stage1_sources)
    print(f"[DEDUP] URL 精确去重: 移除 {url_dedup_count} 条")

    # 第二级：标题模糊去重
    stage2_sources = []
    title_dedup_count = 0

    for i, src in enumerate(stage1_sources):
        title = src.get("title", "")
        is_dup = False

        for kept_src in stage2_sources:
            kept_title = kept_src.get("title", "")
            if not title or not kept_title:
                continue

            # 检查编辑距离和 Jaccard
            if len(title) < 10 and len(kept_title) < 10:
                continue  # 标题太短，跳过模糊匹配

            ed = edit_distance(title, kept_title)
            jac = title_jaccard(title, kept_title)

            if ed < 3 or jac > 0.8:
                # 保留 tier 更高的
                if get_tier(src) < get_tier(kept_src):
                    stage2_sources.remove(kept_src)
                    stage2_sources.append(src)
                    removed.append(
                        {
                            "url": kept_src.get("url", ""),
                            "reason": f"标题模糊重复 (ed={ed}, jac={jac:.2f})",
                            "kept": src.get("url", ""),
                        }
                    )
                else:
                    removed.append(
                        {
                            "url": src.get("url", ""),
                            "reason": f"标题模糊重复 (ed={ed}, jac={jac:.2f})",
                            "kept": kept_src.get("url", ""),
                        }
                    )
                is_dup = True
                title_dedup_count += 1
                break

        if not is_dup:
            stage2_sources.append(src)

    print(f"[DEDUP] 标题模糊去重: 移除 {title_dedup_count} 条")

    # 第三级：内容指纹去重 (SimHash)
    stage3_sources = []
    content_dedup_count = 0
    fingerprints = []  # (simhash_value, source)

    for src in stage2_sources:
        snippet = src.get("snippet", "") or src.get("description", "")
        if not snippet or len(snippet) < 20:
            stage3_sources.append(src)
            fingerprints.append((0, src))
            continue

        fp = simhash(snippet)
        is_dup = False

        for existing_fp, existing_src in fingerprints:
            if existing_fp == 0:
                continue
            hd = hamming_distance(fp, existing_fp)
            if hd < 5:
                # 保留 tier 更高的
                if get_tier(src) < get_tier(existing_src):
                    if existing_src in stage3_sources:
                        stage3_sources.remove(existing_src)
                    stage3_sources.append(src)
                    removed.append(
                        {
                            "url": existing_src.get("url", ""),
                            "reason": f"内容指纹重复 (hamming={hd})",
                            "kept": src.get("url", ""),
                        }
                    )
                else:
                    removed.append(
                        {
                            "url": src.get("url", ""),
                            "reason": f"内容指纹重复 (hamming={hd})",
                            "kept": existing_src.get("url", ""),
                        }
                    )
                is_dup = True
                content_dedup_count += 1
                break

        if not is_dup:
            stage3_sources.append(src)
            fingerprints.append((fp, src))

    print(f"[DEDUP] 内容指纹去重: 移除 {content_dedup_count} 条")

    # 保存结果
    final_count = len(stage3_sources)
    total_removed = original_count - final_count

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stage3_sources, f, ensure_ascii=False, indent=2)

    stats = {
        "original": original_count,
        "deduped": final_count,
        "removed": total_removed,
        "url_dedup": url_dedup_count,
        "title_dedup": title_dedup_count,
        "content_dedup": content_dedup_count,
        "removal_rate": f"{total_removed / max(original_count, 1) * 100:.1f}%",
        "details": removed,
    }

    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(
        f"[DEDUP] 完成: {original_count} → {final_count} (去除 {total_removed} 条, {stats['removal_rate']})"
    )
    print(f"[DEDUP] 输出 → {args.output}")


if __name__ == "__main__":
    main()

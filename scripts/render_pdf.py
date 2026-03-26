#!/usr/bin/env python3
"""
PDF 渲染脚本 — 将 HTML 报告嵌入模板，用 WeasyPrint 渲染为 PDF

用法：
  python render_pdf.py \
    --input clean_report.html \
    --template report.html \
    --css styles.css \
    --output output_dir/
"""

import argparse
import re
from pathlib import Path

from weasyprint import HTML, CSS


def safe_filename(text: str, max_len: int = 30) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "", text)
    return safe[:max_len].strip()


def extract_title(html: str) -> str:
    """从 HTML 中提取报告标题"""
    import re

    match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    if match:
        return match.group(1).strip()
    return "深度调研报告"


def split_large_tables(html_content, max_rows=15):
    """v5.2: 检测超过 max_rows 行的表格，自动拆分为多个子表。

    每个子表携带「（续）」标记，并使用 CSS page-break 控制跨页。
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    for table in tables:
        tbody = table.find("tbody")
        rows_container = tbody if tbody else table
        rows = rows_container.find_all("tr", recursive=False)

        # 如果 thead 存在，排除 thead 中的行
        thead = table.find("thead")
        if thead:
            thead_rows = thead.find_all("tr")
        else:
            thead_rows = []

        # 数据行（不含 thead 的行）
        data_rows = [r for r in rows if r not in thead_rows]

        if len(data_rows) <= max_rows:
            continue

        # 获取表头行
        header_html = ""
        if thead:
            header_html = str(thead)
        elif data_rows:
            # 如果没有 thead，假定第一行为表头
            header_html = f"<thead>{str(data_rows[0])}</thead>"
            data_rows = data_rows[1:]

        # 获取 caption
        caption = table.find("caption")
        caption_text = caption.get_text(strip=True) if caption else ""

        # 获取 table 的属性
        table_attrs = " ".join(
            f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"'
            for k, v in table.attrs.items()
        )

        # 拆分
        chunks = []
        for i in range(0, len(data_rows), max_rows):
            chunk = data_rows[i : i + max_rows]
            chunks.append(chunk)

        if len(chunks) <= 1:
            continue

        # 构建新的 HTML 片段
        new_html_parts = []
        for idx, chunk in enumerate(chunks):
            suffix = "" if idx == 0 else "（续）"
            cap_html = ""
            if caption_text:
                cap_html = f"<caption>{caption_text}{suffix}</caption>"
            elif idx > 0:
                cap_html = f"<caption>{suffix}</caption>"

            rows_html = "".join(str(r) for r in chunk)
            break_style = ' style="page-break-before: always;"' if idx > 0 else ""
            new_table = (
                f"<table {table_attrs}{break_style}>"
                f"{cap_html}{header_html}<tbody>{rows_html}</tbody></table>"
            )
            new_html_parts.append(new_table)

        # 替换原表格
        new_soup = BeautifulSoup("\n".join(new_html_parts), "html.parser")
        table.replace_with(new_soup)

    return str(soup)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="清理后的 HTML 报告")
    parser.add_argument("--template", required=True, help="HTML 模板文件")
    parser.add_argument("--css", required=True, help="CSS 样式文件")
    parser.add_argument("--output", required=True, help="输出目录")
    args = parser.parse_args()

    # 读取内容
    with open(args.input, "r", encoding="utf-8") as f:
        content = f.read()

    with open(args.template, "r", encoding="utf-8") as f:
        template = f.read()

    title = extract_title(content)

    # v5.2: 表格跨页优化 — 拆分大表格
    content = split_large_tables(content, max_rows=15)

    # 嵌入模板
    full_html = template.replace("{{title}}", title).replace("{{content}}", content)

    # 渲染
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"深度调研报告_{safe_filename(title)}.pdf"

    template_dir = str(Path(args.template).parent)
    html_doc = HTML(string=full_html, base_url=template_dir)
    css = CSS(filename=args.css)
    html_doc.write_pdf(str(pdf_path), stylesheets=[css])

    print(f"[RENDER-PDF] v5.2 完成（含表格跨页优化） → {pdf_path}")


if __name__ == "__main__":
    main()

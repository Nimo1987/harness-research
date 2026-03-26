#!/usr/bin/env python3
"""
交互式 HTML 报告生成脚本 (v5.0 新增)

功能：
  - 左侧固定目录导航（自动从 h2/h3 生成）
  - 可折叠的章节内容
  - Chart.js (CDN) 生成交互式图表（从 <table> 自动生成）
  - 暗色/亮色主题切换
  - 移动端响应式适配
  - 独立 HTML 文件，无需服务器

用法：
  python render_interactive.py \
    --input clean_report.html \
    --css styles.css \
    --output output_dir/
"""

import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup


def safe_filename(text: str, max_len: int = 30) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "", text)
    return safe[:max_len].strip()


def extract_title(html: str) -> str:
    match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    return match.group(1).strip() if match else "深度调研报告"


def generate_toc(soup):
    """从 h2/h3 生成目录 HTML"""
    toc_items = []
    heading_id = 0
    for heading in soup.find_all(["h2", "h3"]):
        heading_id += 1
        anchor_id = f"section-{heading_id}"
        heading["id"] = anchor_id
        level = heading.name
        text = heading.get_text(strip=True)
        css_class = "toc-h3" if level == "h3" else ""
        toc_items.append(
            f'<li><a href="#{anchor_id}" class="{css_class}">{text}</a></li>'
        )
    return "\n".join(toc_items)


def generate_chart_scripts(soup):
    """为每个 <table> 生成对应的 Chart.js 图表"""
    scripts = []
    chart_id = 0

    for table in soup.find_all("table"):
        # 检查表格是否有数字数据
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # 提取表头
        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True))
        elif rows:
            for th in rows[0].find_all(["th", "td"]):
                headers.append(th.get_text(strip=True))

        if len(headers) < 2:
            continue

        # 提取数据行
        data_rows = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells and len(cells) >= 2:
                data_rows.append(cells)

        if not data_rows:
            continue

        # 检查是否有数字列
        has_numbers = False
        for row in data_rows:
            for cell in row[1:]:
                cleaned = re.sub(r"[%,，$¥€£]", "", cell)
                try:
                    float(cleaned)
                    has_numbers = True
                    break
                except ValueError:
                    continue
            if has_numbers:
                break

        if not has_numbers:
            continue

        chart_id += 1
        canvas_id = f"chart-{chart_id}"
        caption = table.find("caption")
        chart_title = (
            caption.get_text(strip=True) if caption else f"数据图表 {chart_id}"
        )

        # 在表格后插入图表容器
        chart_div = soup.new_tag("div", attrs={"class": "chart-container"})
        title_div = soup.new_tag("div", attrs={"class": "chart-title"})
        title_div.string = chart_title
        chart_div.append(title_div)
        canvas = soup.new_tag("canvas", id=canvas_id)
        chart_div.append(canvas)
        table.insert_after(chart_div)

        # 生成 Chart.js 配置
        labels = [row[0] for row in data_rows]
        datasets = []
        colors = ["#2b6cb0", "#c05621", "#276749", "#c53030", "#805ad5", "#d69e2e"]

        for col_idx in range(1, len(headers)):
            values = []
            for row in data_rows:
                if col_idx < len(row):
                    cleaned = re.sub(r"[%,，$¥€£]", "", row[col_idx])
                    try:
                        values.append(float(cleaned))
                    except ValueError:
                        values.append(0)
                else:
                    values.append(0)

            color = colors[(col_idx - 1) % len(colors)]
            datasets.append(
                {
                    "label": headers[col_idx]
                    if col_idx < len(headers)
                    else f"列{col_idx}",
                    "data": values,
                    "backgroundColor": color + "40",
                    "borderColor": color,
                    "borderWidth": 2,
                }
            )

        import json

        chart_config = {
            "type": "bar" if len(data_rows) <= 10 else "line",
            "data": {
                "labels": labels,
                "datasets": datasets,
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"position": "top"},
                },
            },
        }

        scripts.append(f"""
        (function() {{
          var ctx = document.getElementById('{canvas_id}');
          if (ctx) {{
            new Chart(ctx.getContext('2d'), {json.dumps(chart_config, ensure_ascii=False)});
          }}
        }})();
        """)

    return "\n".join(scripts)


def build_interactive_html(content_html, css_content, title):
    """构建完整的交互式 HTML 报告"""
    soup = BeautifulSoup(content_html, "html.parser")

    # 生成目录
    toc_html = generate_toc(soup)

    # 生成图表脚本
    chart_scripts = generate_chart_scripts(soup)

    # 更新后的内容
    updated_content = str(soup)

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — 交互式报告</title>
  <style>{css_content}</style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
  <!-- 移动端菜单按钮 -->
  <button class="mobile-menu-btn" onclick="toggleSidebar()" aria-label="目录">&#9776;</button>

  <!-- 主题切换 -->
  <button class="theme-toggle" onclick="toggleTheme()" aria-label="切换主题">&#9788;</button>

  <!-- 左侧目录 -->
  <nav class="toc-sidebar" id="tocSidebar">
    <div class="toc-title">目录导航</div>
    <ul>{toc_html}</ul>
  </nav>

  <!-- 主内容 -->
  <main class="interactive-content">
    <div class="report-container">
      {updated_content}
    </div>
  </main>

  <script>
    // 主题切换
    function toggleTheme() {{
      var html = document.documentElement;
      var current = html.getAttribute('data-theme');
      html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
      localStorage.setItem('theme', html.getAttribute('data-theme'));
    }}

    // 恢复保存的主题
    (function() {{
      var saved = localStorage.getItem('theme');
      if (saved) document.documentElement.setAttribute('data-theme', saved);
    }})();

    // 移动端侧边栏
    function toggleSidebar() {{
      document.getElementById('tocSidebar').classList.toggle('open');
    }}

    // 点击目录项关闭移动端侧边栏
    document.querySelectorAll('.toc-sidebar a').forEach(function(a) {{
      a.addEventListener('click', function() {{
        if (window.innerWidth <= 768) {{
          document.getElementById('tocSidebar').classList.remove('open');
        }}
      }});
    }});

    // 滚动高亮当前章节
    var tocLinks = document.querySelectorAll('.toc-sidebar a');
    var headings = document.querySelectorAll('h2[id], h3[id]');
    window.addEventListener('scroll', function() {{
      var current = '';
      headings.forEach(function(h) {{
        if (h.getBoundingClientRect().top <= 100) current = h.id;
      }});
      tocLinks.forEach(function(a) {{
        a.classList.remove('active');
        if (a.getAttribute('href') === '#' + current) a.classList.add('active');
      }});
    }});

    // 可折叠章节（点击 h2 折叠/展开内容）
    document.querySelectorAll('h2').forEach(function(h2) {{
      h2.classList.add('collapsible-header');
      h2.addEventListener('click', function() {{
        var next = h2.nextElementSibling;
        while (next && next.tagName !== 'H2') {{
          if (next.style.display === 'none') {{
            next.style.display = '';
            h2.classList.remove('collapsed');
          }} else {{
            next.style.display = 'none';
            h2.classList.add('collapsed');
          }}
          next = next.nextElementSibling;
        }}
      }});
    }});

    // v5.2: 表格列排序功能（点击表头排序）
    document.querySelectorAll('table').forEach(function(table) {{
      var headers = table.querySelectorAll('thead th, thead td');
      if (!headers.length) return;
      headers.forEach(function(header, colIndex) {{
        header.style.cursor = 'pointer';
        header.title = '点击排序';
        header.setAttribute('data-sort-dir', 'none');
        header.addEventListener('click', function() {{
          var tbody = table.querySelector('tbody') || table;
          var rows = Array.from(tbody.querySelectorAll('tr'));
          var dir = header.getAttribute('data-sort-dir');
          var newDir = (dir === 'asc') ? 'desc' : 'asc';
          // Reset all headers
          headers.forEach(function(h) {{
            h.setAttribute('data-sort-dir', 'none');
            h.textContent = h.textContent.replace(/ [▲▼]/g, '');
          }});
          header.setAttribute('data-sort-dir', newDir);
          header.textContent += (newDir === 'asc') ? ' ▲' : ' ▼';
          rows.sort(function(a, b) {{
            var cellA = a.querySelectorAll('td, th')[colIndex];
            var cellB = b.querySelectorAll('td, th')[colIndex];
            if (!cellA || !cellB) return 0;
            var valA = cellA.textContent.trim();
            var valB = cellB.textContent.trim();
            // Try numeric comparison
            var numA = parseFloat(valA.replace(/[%,，$¥€£]/g, ''));
            var numB = parseFloat(valB.replace(/[%,，$¥€£]/g, ''));
            if (!isNaN(numA) && !isNaN(numB)) {{
              return newDir === 'asc' ? numA - numB : numB - numA;
            }}
            // String comparison
            return newDir === 'asc' ? valA.localeCompare(valB, 'zh') : valB.localeCompare(valA, 'zh');
          }});
          rows.forEach(function(row) {{ tbody.appendChild(row); }});
        }});
      }});
    }});

    // Chart.js 图表生成
    {chart_scripts}
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="交互式 HTML 报告生成 (v5.0)")
    parser.add_argument("--input", required=True, help="清理后的 HTML 报告")
    parser.add_argument("--css", required=True, help="CSS 样式文件")
    parser.add_argument("--output", required=True, help="输出目录")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        content = f.read()

    with open(args.css, "r", encoding="utf-8") as f:
        css_content = f.read()

    title = extract_title(content)

    interactive_html = build_interactive_html(content, css_content, title)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"深度调研报告_{safe_filename(title)}_交互版.html"

    with open(str(html_path), "w", encoding="utf-8") as f:
        f.write(interactive_html)

    print(f"[RENDER-INTERACTIVE] 完成 → {html_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ideaHub Markdown 轉 HTML 工具（2026 版）
專為你的固定 HTML+CSS 框架設計（基於 post1.html 結構 + style.css）
一次安裝，之後每天 0 token 就能生成完整文章頁
"""

import argparse
import re
import sys
from pathlib import Path

# Windows 終端機強制 UTF-8 輸出，避免 emoji UnicodeEncodeError
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup, NavigableString
from jinja2 import Template
from markdown import markdown


def parse_frontmatter_and_body(md_text: str):
    """解析 frontmatter（可選），沒有就從第一個 # 抓標題"""
    metadata = {
        "title": "未命名文章",
        "date": "2026 年 4 月 9 日",
        "read_time": "5 分鐘閱讀",
        "author": "Sunny",
        "featured_image": None,      # 可選，例如 static/xxx.jpg
        "excerpt": "",               # 可選，首頁卡片摘要；空白時自動取第一段
        "prev_url": "index.html",    # 可選
        "next_url": "#",             # 可選
    }

    body = md_text.strip()

    # 支援 frontmatter
    if body.startswith("---"):
        try:
            # --- 前言 --- 正文
            parts = body.split("---", 2)
            if len(parts) >= 3:
                front = parts[1].strip()
                body = parts[2].strip()

                for line in front.split("\n"):
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip().strip("\"'")
                        if key == "featured_image" and value:
                            metadata[key] = value
                        elif key in metadata:
                            metadata[key] = value
        except:
            pass  # 解析失敗就用預設值

    # 沒有 frontmatter 時，自動抓第一行 # 標題
    if metadata["title"] == "未命名文章":
        match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
        if match:
            metadata["title"] = match.group(1).strip()

    return metadata, body


def process_markdown_to_html_and_toc(body_md: str):
    """Markdown → HTML + 自動生成左側 TOC（支援中文、h2~h4）"""
    # Markdown 轉 HTML（支援表格、程式碼區塊、圖片、YouTube iframe 等）
    html_body = markdown(
        body_md,
        extensions=[
            "tables",          # 表格
            "fenced_code",     # ``` 程式碼
            "codehilite",      # 程式碼高亮（即使沒有額外 CSS 也正常顯示）
            "nl2br",           # 換行
            "sane_lists",      # 列表
            "attr_list",       # {: #id} 自訂 id
        ],
        output_format="html5",
    )

    # 用 BeautifulSoup 產生 TOC + 自動補 id（讓連結能跳轉）
    soup = BeautifulSoup(html_body, "html.parser")
    toc_items = []

    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text().strip()
        if not text:
            continue

        # 簡單 slugify（支援中文）
        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")
        if not heading.get("id"):
            heading["id"] = slug

        level = int(heading.name[1])
        toc_items.append({
            "level": level,
            "text": text,
            "id": slug,
            "short": heading.get("data-toc", ""),  # 來自 {: data-toc="..."} 語法
        })

    if not toc_items:
        return "", str(soup)

    def auto_shorten(text: str, limit: int = 10) -> str:
        """自動從標題推導精簡 TOC 標籤"""
        t = re.sub(r'^\d+\.\s*', '', text)                   # 移除 "1. " 數字編號
        t = re.sub(r'\([^)]+\)', '', t)                       # 移除半型括號 (English)
        t = re.sub(r'（[^）]*[A-Za-z][^）]*）', '', t)          # 移除全型括號含英文
        t = t.strip()

        parts = re.split(r'[：:]', t, maxsplit=1)
        before = parts[0].strip()
        after = parts[1].strip() if len(parts) > 1 else ''

        # 冒號前若是序號標籤（末尾為數字/中文數字，且 ≤8 字），改用冒號後的內容
        is_label = bool(re.search(r'[一二三四五六七八九十\d]$', before)) and len(before) <= 8
        summary = (after if (is_label and after) else before) or t

        # 若摘要開頭仍為英文（如 "Oracle Agile PLM：..."），跳過找中文起點
        summary = re.sub(r'^[A-Za-z0-9\s]+[：:\s]*', '', summary).strip() or summary

        return summary[:limit] + '…' if len(summary) > limit else summary

    # 產生巢狀 TOC HTML（與 post1.html 左側欄一致）
    toc_html = '<nav class="toc" aria-label="文章目錄">\n<h4>本文目錄</h4>\n<ul>'
    prev_level = 2

    for item in toc_items:
        level = item["level"]
        if level > prev_level:
            toc_html += "<ul>" * (level - prev_level)
        elif level < prev_level:
            toc_html += "</ul>" * (prev_level - level)
        # 優先用 {: data-toc="..."} 手動標籤，否則自動推導
        label = item.get("short") or auto_shorten(item["text"])
        toc_html += f'<li><a href="#{item["id"]}" title="{item["text"]}">{label}</a></li>'
        prev_level = level

    toc_html += "</ul>" * (prev_level - 1) + "\n</nav>"

    return toc_html, str(soup)


POSTS_DIR = Path(__file__).parent / "content" / "posts"
OUTPUT_DIR = Path(__file__).parent


def update_index_card(post_filename: str, metadata: dict, content_html: str):
    """在 index.html 的近期文章區塊自動插入或更新文章卡片（最新排第一）"""
    index_path = OUTPUT_DIR / "index.html"
    if not index_path.exists():
        print("[SKIP] 找不到 index.html，略過首頁卡片更新")
        return

    # 決定摘要：frontmatter excerpt > 正文第一段前 120 字
    excerpt = metadata["excerpt"]
    if not excerpt:
        first_p = BeautifulSoup(content_html, "html.parser").find("p")
        if first_p:
            text = first_p.get_text().strip()
            excerpt = text[:120] + "…" if len(text) > 120 else text

    soup = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser")

    recent_section = soup.find("section", class_="recent-posts")
    if not recent_section:
        print("[SKIP] index.html 沒有 <section class='recent-posts'>，略過更新")
        return

    # 檢查此文章卡片是否已存在
    existing_link = recent_section.find("a", href=post_filename)
    if existing_link:
        # 更新現有卡片的標題、日期、閱讀時間、摘要
        card = existing_link.find_parent("div", class_="post-card")
        if card:
            existing_link.string = metadata["title"]
            spans = card.find("div", class_="post-card-meta").find_all("span")
            spans[0].string = metadata["date"]
            spans[2].string = metadata["read_time"]
            excerpt_el = card.find("p", class_="post-card-excerpt")
            if excerpt_el and excerpt:
                excerpt_el.string = excerpt
        print(f"🔄 index.html 卡片已更新：{metadata['title']}")
    else:
        # 建立新卡片 HTML
        new_card_html = (
            f'<div class="post-card">\n'
            f'                <div class="post-card-meta">\n'
            f'                    <span>{metadata["date"]}</span>\n'
            f'                    <span>•</span>\n'
            f'                    <span>{metadata["read_time"]}</span>\n'
            f'                </div>\n'
            f'                <h3><a href="{post_filename}">{metadata["title"]}</a></h3>\n'
            f'                <p class="post-card-excerpt">{excerpt}</p>\n'
            f'            </div>'
        )
        new_card = BeautifulSoup(new_card_html, "html.parser")

        # 插到第一張卡片前面（最新文章排最上）
        first_card = recent_section.find("div", class_="post-card")
        if first_card:
            first_card.insert_before(new_card)
            first_card.insert_before(NavigableString("\n\n            "))
        else:
            recent_section.append(new_card)
        print(f"✅ index.html 已新增卡片：{metadata['title']}")

    index_path.write_text(str(soup), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="ideaHub MD → HTML 轉檔工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例：\n"
            "  python md_to_html.py post3.md           # content/posts/post3.md → post3.html\n"
            "  python md_to_html.py content/posts/post3.md post3.html  # 完整路徑\n"
        ),
    )
    parser.add_argument("input_md", help="Markdown 檔名（自動在 content/posts/ 尋找）或完整路徑")
    parser.add_argument("output_html", nargs="?", help="輸出 HTML 路徑（預設：同檔名放專案根目錄）")
    args = parser.parse_args()

    # 解析輸入路徑：優先完整路徑，否則在 content/posts/ 尋找
    input_path = Path(args.input_md)
    if not input_path.exists():
        candidate = POSTS_DIR / input_path.name
        if candidate.exists():
            input_path = candidate
        else:
            print(f"[ERROR] 找不到檔案：{args.input_md}")
            print(f"        也嘗試過：{candidate}")
            return

    # 解析輸出路徑：預設為根目錄同名 .html
    if args.output_html:
        output_path = Path(args.output_html)
    else:
        output_path = OUTPUT_DIR / input_path.with_suffix(".html").name

    md_text = input_path.read_text(encoding="utf-8")

    metadata, body_md = parse_frontmatter_and_body(md_text)

    # 偵測最後一行是否為 hashtag 關鍵字（如 #WFH #RemoteWork）
    hashtag_html = ""
    lines = body_md.rstrip().splitlines()
    if lines:
        last_line = lines[-1].strip()
        # 每個 token 都是 #英數字 格式（無空格），才視為 hashtag 行
        tokens = last_line.split()
        if tokens and all(re.match(r"^#[A-Za-z\u4e00-\u9fff]\w*$", t) for t in tokens):
            body_md = "\n".join(lines[:-1]).rstrip()
            tag_links = " ".join(
                f'<span class="post-tag">{t}</span>' for t in tokens
            )
            hashtag_html = f'<p class="post-tags">{tag_links}</p>'

    toc_html, content_html = process_markdown_to_html_and_toc(body_md)
    if hashtag_html:
        content_html += "\n" + hashtag_html

    # === 你的完整文章模板（直接從 post1.html 客製化）===
    template_str = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ideaHub | {{ title }}</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%2290%22 font-size=%2290%22>🌿</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400&family=Noto+Serif+TC:wght@700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <nav>
        <a href="index.html" class="logo">ideaHub</a>
        <div class="nav-links">
            <a href="index.html">首頁</a>
            <a href="archive.html">所有文章</a>
            <a href="about.html">關於我</a>
            <a href="https://github.com/AH431" target="_blank" rel="noopener">GitHub</a>
        </div>
    </nav>

    <main class="article-container">
        <article>
            <header class="post-header">
                <h1>{{ title }}</h1>
                <div class="post-meta">
                    <span>{{ date }}</span>
                    <span>•</span>
                    <span>{{ read_time }}</span>
                    <span>•</span>
                    <span>作者：{{ author }}</span>
                    <span id="busuanzi_container_page_pv" style="display:none;">
                        • 本文閱讀量 <span id="busuanzi_value_page_pv"></span> 次
                    </span>
                </div>
            </header>

            <!-- Featured Image -->
            <figure class="featured-image">
                <img src="{{ featured_image if featured_image else 'static/' }}" alt="{{ title }}">
                <figcaption>{{ title }}</figcaption>
            </figure>

            <div class="content-layout">

            <!-- HackMD 風格：左側 TOC -->
            <div class="toc-sidebar">
                {{ toc_html | safe }}
            </div>

            <!-- 正文區域 -->
            <div class="post-main-content">
                <section class="post-content">
                    {{ content_html | safe }}
                </section>

                <!-- ==================== 文末區塊 ==================== -->
                <div class="post-footer">
                    <div class="post-navigation">
                        <div class="nav-buttons">
                            <a href="{{ prev_url }}" class="btn btn-secondary">← 回到首頁</a>
                            <a href="#" class="btn btn-top">↑ 回到頂端</a>
                            <a href="{{ next_url }}" class="btn btn-primary">下一篇文章 →</a>
                        </div>
                    </div>

                    <div class="visitor-stats-group">
                        <div class="visitor-stats">
                            本站總訪問量：<span id="busuanzi_value_site_pv"></span> 次
                        </div>
                        <div class="visitor-stats">
                            本文閱讀量：<span id="busuanzi_value_page_pv"></span> 次
                        </div>
                    </div>
                </div>

                <section id="comment-section">
                    <h3>交流與討論</h3>
                    <br>
                    <p style="font-size: 0.9rem; color: var(--secondary-text);">（留言系統載入中... 請參考下方說明設定）</p>
                </section>
            </div><!-- end post-main-content -->
            </div><!-- end content-layout -->
        </article>
    </main>

    <footer>
        <p>&copy; 2026 ideaHub • Made with ❤️ in Taipei • Powered by GitHub Pages</p>
    </footer>

    <script async src="//busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>
</body>
</html>"""

    # 渲染模板
    template = Template(template_str)
    html_output = template.render(
        title=metadata["title"],
        date=metadata["date"],
        read_time=metadata["read_time"],
        author=metadata["author"],
        featured_image=metadata["featured_image"],
        toc_html=toc_html,
        content_html=content_html,
        prev_url=metadata["prev_url"],
        next_url=metadata["next_url"],
    )

    # 寫入文章 HTML
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")

    # 自動更新 index.html 近期文章卡片
    update_index_card(output_path.name, metadata, content_html)

    print(f"✅ 轉檔完成！")
    print(f"   輸入：{input_path}")
    print(f"   輸出：{output_path}")
    print(f"   標題：{metadata['title']}")
    print(f"   特色圖片：{'有' if metadata['featured_image'] else '無'}")
    print("\n💡 使用範例（MD 檔前言）：")
    print("""---
title: 你的文章標題
date: 2026 年 4 月 10 日
read_time: 8 分鐘閱讀
featured_image: static/你的圖片.jpg
prev_url: post2.html
next_url: post4.html
---""")


if __name__ == "__main__":
    main()
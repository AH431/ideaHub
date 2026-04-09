# GitHub Pages
ideaHub - HTML/CSS

post-template.html 建立完成。

往後新增文章的流程：

複製 post-template.html → 改名為 post3.html、post4.html...
改 ①②③④ 四個標記處
在內文裡填入.keywords 積木
在 index.html 加一張 .post-card

(本地端先瀏覽../ideaHub/postX.html)

---
把HTML+CSS 框架整個當成 template 檔

轉檔工具：
- 輸入：任意 .md 檔案
- 輸出：完整的 .html 檔案（把 MD 轉成 HTML 內容後，塞進 template 的 <article> 或指定區塊）
- 要支援：Markdown 標題、圖片、程式碼區塊、表格、內嵌 YouTube 等
- 使用 markdown + jinja2（或 beautifulsoup）實現
- 加上簡單的 CLI：python md_to_html.py input.md output.html
- 請輸出完整可直接執行的程式碼

把 AI 給的程式碼存成 md_to_html.py，

使用前一次設定（只需執行一次）：
pip install markdown jinja2 beautifulsoup4
每天使用超簡單：
python md_to_html.py 今天文章.md 今天文章.html

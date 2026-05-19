import html
import os
import tempfile
from pathlib import Path
from typing import Optional

import bleach
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pdfminer.high_level import extract_text

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

app = FastAPI(title="PDF to HTML Converter")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TAGS = [
    "article", "section", "h1", "h2", "h3", "p", "br", "strong", "em",
    "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "pre", "code"
]
ALLOWED_ATTRIBUTES = {}


def text_to_basic_html(text: str) -> str:
    """Convert extracted PDF text into simple, safe HTML."""
    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            body = " ".join(html.escape(x.strip()) for x in paragraph if x.strip())
            if body:
                blocks.append(f"<p>{body}</p>")
            paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue

        # Very simple heading guess: short lines without sentence punctuation.
        if len(stripped) <= 40 and not stripped.endswith(("。", ".", "、", ",")):
            flush_paragraph()
            blocks.append(f"<h2>{html.escape(stripped)}</h2>")
        else:
            paragraph.append(stripped)

    flush_paragraph()
    return "\n".join(blocks) if blocks else "<p>PDFからテキストを抽出できませんでした。</p>"


def wrap_html(body: str, title: str = "Converted PDF") -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{safe_title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; max-width: 860px; margin: 40px auto; padding: 0 20px; color: #222; }}
    h1 {{ font-size: 1.8rem; border-bottom: 2px solid #ddd; padding-bottom: .4rem; }}
    h2 {{ font-size: 1.3rem; margin-top: 2rem; }}
    p {{ margin: 1rem 0; }}
    article {{ background: #fff; }}
    .notice {{ color: #666; font-size: .9rem; }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  <p class=\"notice\">PDFから抽出した内容をHTML化しました。レイアウトは完全再現ではありません。</p>
  <article>
{body}
  </article>
</body>
</html>"""


def improve_html_with_ai(raw_text: str) -> Optional[str]:
    """Optionally improve HTML structure with OpenAI API when OPENAI_API_KEY is set."""
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return None

    client = OpenAI()
    prompt = f"""
以下のPDF抽出テキストを、意味のまとまりごとに整理したHTML本文に変換してください。
条件:
- body内に入れるHTML断片だけを返す
- script, style, iframeは使わない
- h2, h3, p, ul, ol, li, tableを適切に使う
- 原文にない内容は追加しない

--- PDF抽出テキスト ---
{raw_text[:12000]}
"""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content or None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>PDF to HTML Converter</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.8; }
    form { border: 1px solid #ddd; border-radius: 16px; padding: 24px; }
    button { padding: 10px 18px; border-radius: 10px; border: 0; cursor: pointer; }
    .hint { color: #666; font-size: .9rem; }
  </style>
</head>
<body>
  <h1>PDF to HTML Converter</h1>
  <p>PDFファイルをアップロードすると、テキストを抽出してHTMLに変換します。</p>
  <form action=\"/convert\" method=\"post\" enctype=\"multipart/form-data\">
    <p><input type=\"file\" name=\"file\" accept=\"application/pdf,.pdf\" required /></p>
    <label><input type=\"checkbox\" name=\"use_ai\" value=\"true\" /> AIでHTML構造を整える</label>
    <p class=\"hint\">AI機能はOPENAI_API_KEYを設定した場合のみ有効です。</p>
    <button type=\"submit\">HTMLに変換</button>
  </form>
</body>
</html>"""


@app.post("/convert", response_class=HTMLResponse)
async def convert_pdf(file: UploadFile = File(...), use_ai: Optional[str] = Form(None)) -> str:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルをアップロードしてください。")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="ファイルサイズは10MB以下にしてください。")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        raw_text = extract_text(str(tmp_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDFの読み取りに失敗しました: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if not raw_text.strip():
        return wrap_html("<p>テキストを抽出できませんでした。画像だけのPDFの場合はOCR機能が必要です。</p>", file.filename)

    body = None
    if use_ai == "true":
        body = improve_html_with_ai(raw_text)

    if body is None:
        body = text_to_basic_html(raw_text)

    clean_body = bleach.clean(body, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    return wrap_html(clean_body, file.filename)


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"

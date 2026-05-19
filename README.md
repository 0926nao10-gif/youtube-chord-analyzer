# PDF to HTML Converter

Python / FastAPIで、アップロードされたPDFをHTMLに変換するWebアプリです。

## できること

- `.pdf` ファイルをアップロード
- PDF内のテキストを抽出
- HTMLとしてブラウザ表示
- 任意でOpenAI APIを使い、見出し・段落・表などのHTML構造を整理

## 構成

```text
ブラウザ
  ↓ PDFアップロード
FastAPI
  ↓
pdfminer.sixでテキスト抽出
  ↓
HTML生成
  ↓
ブラウザにHTML表示
```

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 起動

```bash
uvicorn app.main:app --reload
```

ブラウザで以下を開きます。

```text
http://127.0.0.1:8000
```

## AI機能を使う場合

OpenAI APIキーを環境変数に設定します。

macOS / Linux:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

その後、画面の「AIでHTML構造を整える」にチェックを入れて変換します。

## 注意点

- 画像だけのPDFは、このコードだけでは文字を抽出できません。OCR機能が別途必要です。
- PDFのレイアウトを完全再現するものではありません。
- 一般公開する場合は、サーバー代・API利用料・セキュリティ対策が必要です。
- このサンプルでは、アップロードサイズを10MBに制限しています。

## ライセンス面の考え方

このサンプルではPDF処理に `pdfminer.six` を使っています。PyMuPDFなど、商用利用時にライセンス確認が必要なライブラリは避けた構成です。

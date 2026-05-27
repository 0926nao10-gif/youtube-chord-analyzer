# M4A Chord Analyzer

Python / FastAPIで、アップロードされた`.m4a`音声ファイルからコード進行を簡易推定するWebアプリです。

YouTube URLからの解析ではなく、手元のm4a音声ファイルを解析元にします。歌詞解析は行いません。

## できること

- `.m4a` ファイルをアップロード
- 音声特徴量からコードを簡易推定
- 開始時刻・終了時刻・推定コードを表で表示
- 歌詞解析は行わず、コード解析のみに集中

## 構成

```text
ブラウザ
  ↓ m4aアップロード
FastAPI
  ↓
librosaで音声読み込み・特徴量抽出
  ↓
クロマ特徴量からコードを簡易推定
  ↓
ブラウザに解析結果を表示
```

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
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

## 使い方

1. トップページで `.m4a` ファイルを選択
2. 「コードを解析」を押す
3. 解析結果として、時刻ごとの推定コードが表示される

## 注意点

- このアプリは歌詞解析を行いません。
- YouTube URLの入力・動画ダウンロード処理は行いません。
- コード推定はクロマ特徴量を使った簡易推定です。完全な耳コピ精度を保証するものではありません。
- m4aの読み込みには、環境によって `ffmpeg` が必要になる場合があります。
- このサンプルでは、アップロードサイズを50MBに制限しています。

## ffmpegが必要な場合

macOS:

```bash
brew install ffmpeg
```

Windowsの場合は、ffmpegをインストールしてPATHを通してください。

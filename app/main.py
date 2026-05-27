import html
import tempfile
from pathlib import Path

import librosa
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

app = FastAPI(title="M4A Chord Analyzer")

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
SUPPORTED_EXTENSIONS = (".m4a",)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR_TEMPLATE = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=float)
MINOR_TEMPLATE = np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float)


def normalize_template(template: np.ndarray) -> np.ndarray:
    return template / np.linalg.norm(template)


MAJOR_TEMPLATE = normalize_template(MAJOR_TEMPLATE)
MINOR_TEMPLATE = normalize_template(MINOR_TEMPLATE)


def estimate_chord(chroma_vector: np.ndarray) -> str:
    """Estimate a simple major/minor chord from a 12-bin chroma vector."""
    if np.max(chroma_vector) <= 1e-6:
        return "N.C."

    vector = chroma_vector / np.linalg.norm(chroma_vector)
    best_chord = "N.C."
    best_score = -1.0

    for root_index, root_name in enumerate(NOTE_NAMES):
        major_score = float(np.dot(vector, np.roll(MAJOR_TEMPLATE, root_index)))
        minor_score = float(np.dot(vector, np.roll(MINOR_TEMPLATE, root_index)))

        if major_score > best_score:
            best_score = major_score
            best_chord = root_name
        if minor_score > best_score:
            best_score = minor_score
            best_chord = f"{root_name}m"

    return best_chord


def seconds_to_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def merge_same_chords(rows: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    if not rows:
        return []

    merged = [rows[0].copy()]
    for row in rows[1:]:
        if row["chord"] == merged[-1]["chord"]:
            merged[-1]["end"] = row["end"]
        else:
            merged.append(row.copy())
    return merged


def analyze_chords(audio_path: Path) -> list[dict[str, float | str]]:
    """Analyze an m4a audio file and return time-aligned chord estimates.

    This app does not analyze lyrics. It only estimates chords from audio features.
    """
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "音声ファイルの読み込みに失敗しました。"
                "m4aの読み込みにはローカル環境にffmpegが必要な場合があります。"
                f" 詳細: {exc}"
            ),
        ) from exc

    if y.size == 0:
        raise HTTPException(status_code=400, detail="音声データを読み込めませんでした。")

    duration = float(librosa.get_duration(y=y, sr=sr))
    hop_length = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop_length)

    window_seconds = 2.0
    rows: list[dict[str, float | str]] = []
    start = 0.0

    while start < duration:
        end = min(start + window_seconds, duration)
        frame_mask = (frame_times >= start) & (frame_times < end)
        if np.any(frame_mask):
            average_chroma = np.mean(chroma[:, frame_mask], axis=1)
            chord = estimate_chord(average_chroma)
            rows.append({"start": start, "end": end, "chord": chord})
        start = end

    return merge_same_chords(rows)


def render_result(filename: str, chord_rows: list[dict[str, float | str]]) -> str:
    escaped_filename = html.escape(filename)
    table_rows = "\n".join(
        f"""
        <tr>
          <td>{seconds_to_timestamp(float(row["start"]))}</td>
          <td>{seconds_to_timestamp(float(row["end"]))}</td>
          <td><strong>{html.escape(str(row["chord"]))}</strong></td>
        </tr>
        """
        for row in chord_rows
    )

    if not table_rows:
        table_rows = "<tr><td colspan=\"3\">コードを推定できませんでした。</td></tr>"

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>解析結果 - M4A Chord Analyzer</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 48px auto; padding: 0 20px; line-height: 1.8; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 10px 12px; text-align: left; }}
    th {{ background: #f6f6f6; }}
    .notice {{ color: #666; font-size: .92rem; }}
    a {{ display: inline-block; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>コード解析結果</h1>
  <p><strong>解析ファイル:</strong> {escaped_filename}</p>
  <p class="notice">歌詞解析は行わず、m4a音声ファイルからコードのみを推定しています。結果は簡易推定のため、耳コピや楽譜作成の下書きとして確認してください。</p>
  <table>
    <thead>
      <tr><th>開始</th><th>終了</th><th>推定コード</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  <a href="/">別のm4aを解析する</a>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>M4A Chord Analyzer</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.8; color: #222; }
    form { border: 1px solid #ddd; border-radius: 16px; padding: 24px; }
    button { padding: 10px 18px; border-radius: 10px; border: 0; cursor: pointer; }
    .hint { color: #666; font-size: .9rem; }
  </style>
</head>
<body>
  <h1>M4A Chord Analyzer</h1>
  <p>m4a音声ファイルをアップロードすると、歌詞解析は行わず、音声からコード進行だけを推定します。</p>
  <form action="/analyze" method="post" enctype="multipart/form-data">
    <p><input type="file" name="file" accept="audio/mp4,audio/x-m4a,.m4a" required /></p>
    <p class="hint">対応形式: .m4a / 最大50MB</p>
    <button type="submit">コードを解析</button>
  </form>
</body>
</html>"""


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_audio(file: UploadFile = File(...)) -> str:
    filename = file.filename or "uploaded.m4a"
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="m4aファイルをアップロードしてください。")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="ファイルサイズは50MB以下にしてください。")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        chord_rows = analyze_chords(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return render_result(filename, chord_rows)


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"

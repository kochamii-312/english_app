# pages/3_🗣️_アウトプット練習.py
import io
import json
import os
import time
import wave
import datetime as dt
import streamlit as st
import base64
import random
import hashlib
# from dotenv import load_dotenv
from openai import OpenAI
from st_audiorec import st_audiorec  # pip install streamlit-audiorec

# =============== 基本設定 ===============
st.set_page_config(page_title="アウトプット練習", layout="wide")
st.markdown("## 🗣️ アウトプット練習")

# .env → OPENAI_API_KEY
# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 保存先（録音音声 / ログJSON）
RECORDINGS_DIR_CANDIDATES = [
    "./recordings",
    os.path.join(os.path.dirname(__file__), "recordings"),
    "/mnt/data/recordings",
]
LOG_JSON_CANDIDATES = [
    "./json/recordings_output.json",                               # 新しい録音ログ（出力要件）
    os.path.join(os.path.dirname(__file__), "./json/recordings_output.json"),
    "/mnt/data/json/recordings_output.json",
]
OUTPUT_JSON_PATHS = [
    "./json/output.json",                                          # 既存の出題保存（サンプル）に対応
    os.path.join(os.path.dirname(__file__), "./json/output.json"),
    "/mnt/data/json/output.json",
]
DESC_IMG_DIR_CANDIDATES = [
    "./desc_images",
    os.path.join(os.path.dirname(__file__), "desc_images"),
    "/mnt/data/desc_images",
]

def ensure_dir() -> str:
    for d in RECORDINGS_DIR_CANDIDATES:
        try:
            os.makedirs(d, exist_ok=True)
            # 書き込み検証
            p = os.path.join(d, ".touch")
            with open(p, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(p)
            return d
        except Exception:
            continue
    os.makedirs("./recordings", exist_ok=True)
    return "./recordings"

def resolve_path(cands) -> str:
    # 既存 or 作成可能な最初のパスを返す
    for p in cands:
        parent = os.path.dirname(p) or "."
        if os.path.exists(p) or os.path.isdir(parent):
            return p
    return cands[0]

RECORDING_DIR = ensure_dir()
RECORD_LOG_PATH = resolve_path(LOG_JSON_CANDIDATES)
OUTPUT_JSON_PATH = resolve_path(OUTPUT_JSON_PATHS)

# =============== ユーティリティ ===============
def save_bytes_to_file(b: bytes, path: str) -> None:
    with open(path, "wb") as f:
        f.write(b)

def compute_wav_duration_seconds(wav_bytes: bytes) -> float:
    # st_audiorec は WAV ヘッダ付与済み
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return float(frames) / float(rate) if rate else 0.0

def append_json(path: str, item: dict) -> None:
    data = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append(item)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =============== 出題生成（任意） ===============
def generate_toefl_question() -> str:
    """TOEFLレベルのディスカッション質問を1つ生成（必要なら output.json にも保存可能）。"""
    prompt = """Generate ONE TOEFL-style discussion question (B2–C1) in one sentence.
Return only the question text."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        messages=[
            {"role": "system", "content": "You create concise TOEFL-style prompts."},
            {"role": "user", "content": prompt}
        ]
    )
    q = resp.choices[0].message.content.strip().strip('"')
    # 既存方針：output.json にも保存しておく（必要なら）
    try:
        # { "key": int, "question": "..." } の配列想定（サンプル準拠）
        # 新規 key は連番で採番
        dat = []
        if os.path.exists(OUTPUT_JSON_PATH):
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                dat = json.load(f)
        next_key = (max([d.get("key", 0) for d in dat]) + 1) if dat else 1
        dat.append({"key": next_key, "question": q})
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(dat, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return q

# =============== 文字起こし & 評価 ===============
def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    """OpenAI Whisperで文字起こし（要APIキー）。"""
    # OpenAI API はファイルlikeを受け付ける
    audio_f = io.BytesIO(wav_bytes)
    audio_f.name = "audio.wav"
    r = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_f
    )
    return r.text.strip()

def evaluate_speaking(question: str, transcript: str) -> dict:
    """文法/内容/流暢さを5点満点で評価し、短い講評と改善提案をJSONで返す。"""
    user = f"""
Question: {question}
Learner's response (transcribed): {transcript}

Rate on 0–5 scale:
- grammar
- content_relevance
- fluency

Return strict JSON:
{{
  "scores": {{"grammar": <int>, "content_relevance": <int>, "fluency": <int>}},
  "comment": "<one-paragraph natural feedback>",
  "tips": ["<short fix 1>", "<short fix 2>", "<short fix 3>"]
}}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "You are a precise English speaking evaluator for TOEFL practice."},
            {"role": "user", "content": user}
        ]
    )
    content = resp.choices[0].message.content
    # JSON抽出
    start = content.find("{"); end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end+1]
    return json.loads(content)

# =============== 録音ハンドラ ===============
def handle_recording(category: str, mode: str, question: str, wav_audio_data: bytes, image_file: str | None = None):
    """録音データを保存→長さ計算→文字起こし→評価→録音ログJSONへ追記。"""
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{category}_{mode}_{ts}"
    audio_path = os.path.join(RECORDING_DIR, f"{base}.wav")

    # 1) 保存
    save_bytes_to_file(wav_audio_data, audio_path)

    # 2) 長さ
    dur = compute_wav_duration_seconds(wav_audio_data)

    # 3) 文字起こし
    transcript = ""
    try:
        transcript = transcribe_wav_bytes(wav_audio_data)
    except Exception as e:
        transcript = ""
        st.warning(f"文字起こしに失敗しました: {e}")

    # 4) 評価
    evaluation = {}
    try:
        evaluation = evaluate_speaking(question, transcript or "(no transcript)")
    except Exception as e:
        evaluation = {"scores": {"grammar": 0, "content_relevance": 0, "fluency": 0},
                      "comment": f"Evaluation failed: {e}", "tips": []}

    # 5) ログJSONへ追記（画像パスも含める）
    log_item = {
        "timestamp": ts,
        "category": "output",            # 要件どおり固定
        "mode": mode,                    # "discussion" / "description"
        "question": question,
        "audio_file": audio_path,
        "duration_sec": round(dur, 2),
        "transcript": transcript,
        "evaluation": evaluation
    }
    if image_file:
        log_item["image_file"] = image_file

    append_json(RECORD_LOG_PATH, log_item)

    # 6) 画面表示
    st.success("録音・保存が完了しました。")
    st.audio(audio_path)
    if image_file:
        st.image(image_file, caption="Saved picture for DESCRIPTION", use_container_width=True)
    st.json({
        "saved_to": RECORD_LOG_PATH,
        "duration_sec": round(dur, 2),
        "evaluation_summary": evaluation.get("scores", {})
    })
    # 👉 追加：呼び出し側で詳細表示できるよう返す
    return {
        "audio_path": audio_path,
        "image_path": image_file,
        "duration_sec": round(dur, 2),
        "transcript": transcript,
        "evaluation": evaluation,
        "log_path": RECORD_LOG_PATH,
    }

def _ensure_desc_img_dir() -> str:
    for d in DESC_IMG_DIR_CANDIDATES:
        try:
            os.makedirs(d, exist_ok=True)
            # 書き込み検証
            p = os.path.join(d, ".touch")
            with open(p, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(p)
            return d
        except Exception:
            continue
    os.makedirs("./desc_images", exist_ok=True)
    return "./desc_images"

DESC_IMG_DIR = _ensure_desc_img_dir()

def _description_categories() -> list[str]:
    # 多様な日常/公共シーン
    return [
        "modern open-plan office",
        "cozy living room at home",
        "airplane cabin during boarding",
        "busy train station concourse",
        "university classroom with projector",
        "quiet library interior",
        "coffee shop counter and seating area",
        "suburban kitchen interior",
        "hotel lobby reception area",
        "tech startup workspace with whiteboards"
    ]

def generate_description_image(client: OpenAI) -> tuple[str, str]:
    """
    説明タスク用の写真を1枚生成して保存。
    戻り値: (image_path, prompt_used)
    """
    category = random.choice(_description_categories())
    prompt = (
        f"Photorealistic, high-resolution interior or public scene: {category}. "
        "Natural lighting, realistic textures, rich details. No text or watermarks."
    )

    # OpenAI Images API（base64で受け取りPNG保存）
    img_resp = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="high",
        n=1,
    )
    b64 = img_resp.data[0].b64_json
    img_bytes = base64.b64decode(b64)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(DESC_IMG_DIR, f"description_{ts}.png")
    with open(out_path, "wb") as f:
        f.write(img_bytes)

    return out_path, prompt

# モード選択（DISCUSSION / DESCRIPTION）
mode = st.radio("モードを選んでください", ["DISCUSSION", "DESCRIPTION"], horizontal=True)

if "discussion_q" not in st.session_state:
    st.session_state.discussion_q = "What is your hobby?"
if "auto_eval" not in st.session_state:
    st.session_state.auto_eval = True
if "last_audio_fingerprint" not in st.session_state:
    st.session_state.last_audio_fingerprint = None

def _fingerprint_audio(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()

if mode == "DISCUSSION":
    st.subheader("Question")
    colq1, colq2 = st.columns([3,1])
    with colq1:
        st.write(st.session_state.discussion_q)
    with colq2:
        if st.button("🔄 設問を生成"):
            st.session_state.discussion_q = generate_toefl_question()
            st.rerun()
    current_question = st.session_state.discussion_q
    current_image_path = None  # DISCUSSIONでは画像なし

else:
    st.subheader("Description Task")
    st.caption("オフィス/家/飛行機/駅など、日常や公共のシーン写真が自動生成されます。1分ほどで明快に説明してみましょう。")
    # 画像の自動生成（初回のみ）
    if "desc_image_path" not in st.session_state or st.session_state.desc_image_path is None:
        with st.spinner("写真を生成中..."):
            try:
                img_path, used_prompt = generate_description_image(client)
                st.session_state.desc_image_path = img_path
                st.session_state.desc_image_prompt = used_prompt
            except Exception as e:
                st.error(f"画像生成に失敗しました: {e}")
                st.session_state.desc_image_path = None
                st.session_state.desc_image_prompt = None

    # 再生成ボタン
    regen = st.button("🔄 別の画像を生成")
    if regen:
        with st.spinner("写真を生成中..."):
            try:
                img_path, used_prompt = generate_description_image(client)
                st.session_state.desc_image_path = img_path
                st.session_state.desc_image_prompt = used_prompt
            except Exception as e:
                st.error(f"画像生成に失敗しました: {e}")

    # 表示
    current_image_path = st.session_state.get("desc_image_path")
    if current_image_path:
        st.image(current_image_path, caption="Generated picture", use_container_width=True)
        with st.expander("画像生成プロンプト（参考）"):
            st.code(st.session_state.get("desc_image_prompt", ""), language="text")

    # 評価用の “擬似質問文”
    current_question = "Describe the given picture or situation in about one minute with clear structure."

st.divider()
st.caption("※ 録音ウィジェットはページに1つだけです。モードを切り替えて使ってください。")

st.session_state.auto_eval = st.checkbox(
    "録音停止したら自動で採点する", value=st.session_state.auto_eval
)

# 録音（唯一のst_audiorec）
wav_audio_data = st_audiorec()

if wav_audio_data is not None:
    st.subheader("録音した音声")
    st.audio(wav_audio_data, format="audio/wav")

    # ★ ここで自動採点：新しい録音なら一度だけ走らせる
    fp = _fingerprint_audio(wav_audio_data)
    if st.session_state.auto_eval and fp != st.session_state.last_audio_fingerprint:
        result = handle_recording(
            category="output",
            mode=mode.lower(),                       # "discussion"/"description"
            question=current_question,
            wav_audio_data=wav_audio_data,
            image_file=current_image_path if mode == "DESCRIPTION" else None
        )
        st.session_state.last_audio_fingerprint = fp

        # 既存の評価表示ロジック（ボタンと同じ表示）を流用したい場合はこの下に転記してOK
        if result and "evaluation" in result:
            ev = result["evaluation"]
            scores = ev.get("scores", {})
            grammar = int(scores.get("grammar", 0))
            content_rel = int(scores.get("content_relevance", 0))
            fluency = int(scores.get("fluency", 0))

            st.markdown("### 📝 評価結果（自動）")
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Grammar", grammar)
            with m2: st.metric("Content Relevance", content_rel)
            with m3: st.metric("Fluency", fluency)

            st.progress(min((grammar/5), 1.0))
            st.progress(min((content_rel/5), 1.0))
            st.progress(min((fluency/5), 1.0))

            st.markdown("#### 総評")
            st.write(ev.get("comment", ""))

            tips = ev.get("tips", [])
            if tips:
                st.markdown("#### 改善のヒント")
                for t in tips:
                    st.write(f"- {t}")

            st.markdown("#### 補助情報")
            st.write(f"- 音声の長さ: **{result.get('duration_sec', 0)} sec**")
            if result.get("transcript"):
                with st.expander("文字起こしを表示"):
                    st.write(result["transcript"])
            st.caption(f"保存先: `{result.get('log_path')}`")

    # 手動でも走らせたい人向けのボタンは残す（従来通り）
    c1, c2, _ = st.columns([1,1,2])
    with c1:
        if st.button("💾 保存してAI評価"):
            result = handle_recording(
                category="output",
                mode=mode.lower(),
                question=current_question,
                wav_audio_data=wav_audio_data,
                image_file=current_image_path if mode == "DESCRIPTION" else None
            )
            # 手動実行でも指紋を更新して二重実行を防ぐ
            st.session_state.last_audio_fingerprint = _fingerprint_audio(wav_audio_data)

    with c2:
        st.download_button("⬇️ ダウンロード", wav_audio_data,
                           file_name="recorded_voice.wav", mime="audio/wav")

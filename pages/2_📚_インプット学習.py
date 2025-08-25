# pages/2_📚_インプット学習.py
import streamlit as st
import json
import io
import os
import re
import wave
import datetime as dt
from typing import Dict, Any, List, Optional
# from dotenv import load_dotenv
from openai import OpenAI
from st_audiorec import st_audiorec

# メモ：オーディオを生成、オーディオファイルに保存、パスをjsonに保存、画面上で音声を再生できる
# 既存DB関数群はそのまま利用（UI動作維持）
from database import (
    get_folders,
    add_folder,
    get_phrases_by_folder,
    add_phrase,
    update_phrase,
    delete_phrase
)

# =========================
# 設定：ファイルパス & OpenAI
# =========================
DEFAULT_JSON_CANDIDATES = [
    "./json/weekly_input.json",          # 推奨配置
    "weekly_input.json",                 # ルート直下
    os.path.join(os.path.dirname(__file__), "json", "weekly_input.json"),
    "/mnt/data/weekly_input.json",       # 実行環境フォールバック
]
AUDIO_DIR_CANDIDATES = [
    "./audio",
    os.path.join(os.path.dirname(__file__), "audio"),
    "/mnt/data/audio",
]
LOG_JSON_CANDIDATES = [
    "./json/recordings_input.json",                               # 新しい録音ログ（出力要件）
    os.path.join(os.path.dirname(__file__), "./json/recordings_input.json"),
    "/mnt/data/json/recordings_input.json",
]
RECORDINGS_DIR_CANDIDATES = [
    "./recordings",
    os.path.join(os.path.dirname(__file__), "recordings"),
    "/mnt/data/recordings",
]

def _find_json_path(candidates: List[str]) -> Optional[str]:
    for p in candidates:
        parent = os.path.dirname(p) or "."
        if os.path.exists(p) or os.path.isdir(parent):
            return p
    return None

def _ensure_audio_dir(cands) -> str:
    for d in cands:
        try:
            os.makedirs(d, exist_ok=True)
            # 書き込みテスト
            test_path = os.path.join(d, ".touch")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(test_path)
            return d
        except Exception:
            continue
    # 最後の手段：作業ディレクトリ直下
    os.makedirs("./audio", exist_ok=True)
    return "./audio"

def record_ensure_dir() -> str:
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

def _resolve_writable_json_path(candidates: List[str]) -> str:
    for p in candidates:
        parent = os.path.dirname(p) or "."
        try:
            os.makedirs(parent, exist_ok=True)  # 親フォルダを作る
            # 既存 or 新規どちらでも返す
            return p
        except Exception:
            continue
    # 最後の手段
    os.makedirs("./json", exist_ok=True)
    return "./json/recordings_input.json"

JSON_PATH  = _find_json_path(DEFAULT_JSON_CANDIDATES)
AUDIO_DIR  = _ensure_audio_dir(AUDIO_DIR_CANDIDATES)
RECORD_LOG_PATH = _resolve_writable_json_path(LOG_JSON_CANDIDATES)
RECORDING_DIR = record_ensure_dir()

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

# OpenAI 初期化 (.env から取得)
# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =========================
# データ読み込み/保存ユーティリティ
# =========================
@st.cache_data(show_spinner=False)
def load_weekly_data(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_weekly_data(path: str, data: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def to_week_dict(items: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    wk = {}
    for item in items:
        try:
            wk[int(item["week_num"])] = item
        except Exception:
            continue
    return wk

def next_week_number(wk_dict: Dict[int, Any]) -> int:
    return (max(wk_dict.keys()) + 1) if wk_dict else 1

def is_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9faf]", text))

def audio_path_for_week(week_num: int, ext: str = "mp3") -> str:
    fname = f"week_{week_num:02d}.{ext}"
    return os.path.join(AUDIO_DIR, fname)

# =========================
# TTS（gTTS優先 → pyttsx3フォールバック）
# =========================
def synthesize_audio(english_text: str, week_num: int) -> Optional[str]:
    """
    英文を音声にして保存。基本は gTTS で MP3、失敗したら pyttsx3 で WAV。
    成功したら音声ファイルの相対パスを返す。失敗なら None。
    """
    # 1) gTTS (オンライン)
    try:
        from gtts import gTTS
        out_path = audio_path_for_week(week_num, "mp3")
        tts = gTTS(english_text)  # 言語自動判定。英語ならOK
        tts.save(out_path)
        return out_path
    except Exception as e:
        st.info(f"gTTSでの生成に失敗しました（{e}）。pyttsx3にフォールバックします。")

    # 2) pyttsx3 (オフライン, 形式は環境依存・WAV推奨)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        # 英語声に切替（環境によっては未対応）
        try:
            voices = engine.getProperty("voices")
            for v in voices:
                if "en" in (v.languages[0].decode() if v.languages else "").lower() or "english" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass
        out_path = audio_path_for_week(week_num, "wav")
        engine.save_to_file(english_text, out_path)
        engine.runAndWait()
        return out_path
    except Exception as e:
        st.error(f"pyttsx3でも音声生成に失敗しました: {e}")
        return None

# =========================
# 生成 & 翻訳（OpenAI）
# =========================
def generate_toefl_passage(client: OpenAI) -> Dict[str, str]:
    sys = "You are an expert ESL content writer for TOEFL preparation."
    user = """
Return ONLY valid compact JSON. No markdown. Keys: {"english": "...", "japanese": "..."}. 

Requirements for "english":
- Level: TOEFL iBT reading/listening passage difficulty (B2–C1).
- Length: about 150 words (±20%).
- Topic: academic or social (technology & society, environment, psychology, education, culture).
- Style: clear, neutral, coherent, with 2–4 sentences or short paragraphs.

Requirements for "japanese":
- Provide a natural and faithful Japanese translation of the English passage.

Again, output strict JSON with keys "english" and "japanese" only.
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.8,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user}
        ]
    )
    content = resp.choices[0].message.content.strip()
    start = content.find("{"); end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end+1]
    data = json.loads(content)
    return {"english": data["english"], "japanese": data["japanese"]}

def translate_text(client: OpenAI, text: str) -> Dict[str, str]:
    src_is_jp = is_japanese(text)
    sys = "You are a professional translator for English↔Japanese study."
    if src_is_jp:
        user = f"""
Translate the following Japanese text into natural, concise, study-friendly English.
Keep meaning faithful; don't add info.

Return ONLY JSON: {{"english":"...","japanese":"..."}}.
- "japanese" MUST be the original input (unchanged).
Text: {text}
"""
    else:
        user = f"""
Translate the following English text into natural, concise, study-friendly Japanese.
Keep meaning faithful; don't add info.

Return ONLY JSON: {{"english":"...","japanese":"..."}}.
- "english" MUST be the original input (unchanged).
Text: {text}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user}
        ]
    )
    content = resp.choices[0].message.content.strip()
    start = content.find("{"); end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end+1]
    data = json.loads(content)
    return {"english": data["english"], "japanese": data["japanese"]}

def handle_recording(category: str, eng_txt: str, jpn_txt: str, wav_audio_data: bytes | None = None):
    """録音データを保存→長さ計算→録音ログJSONへ追記。"""
    if not wav_audio_data:
        st.warning("音声データがありません。もう一度録音してください。")
        return

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{category}_weekly_{ts}"  # ← 未定義だった base をここで定義
    audio_path = os.path.join(RECORDING_DIR, f"{base}.wav")

    # 1) 保存
    save_bytes_to_file(wav_audio_data, audio_path)

    # 2) 長さ
    dur = compute_wav_duration_seconds(wav_audio_data)

    # 3) ログJSONへ追記（category は引数をそのまま保存）
    log_item = {
        "timestamp": ts,
        "category": category,     # ← "output" で固定せず、渡された値を使う
        "eng_txt": eng_txt,
        "jpn_txt": jpn_txt,
        "audio_file": audio_path,
        "duration_sec": round(dur, 2),
    }
    append_json(RECORD_LOG_PATH, log_item)

    # 4) 画面表示
    st.success("録音・保存が完了しました。")
    st.audio(audio_path)
    st.json({
        "saved_to": RECORD_LOG_PATH,
        "duration_sec": round(dur, 2),
    })

# =========================
# アプリ本体
# =========================
st.set_page_config(page_title="📚 インプット学習", page_icon="📚", layout="centered")
st.header("📚 インプット練習")

if JSON_PATH is None:
    st.error("`weekly_input.json` の保存先を見つけられませんでした。`./json/weekly_input.json` を作成するか、書き込み可能なパスを用意してください。")
    st.stop()

weekly_list = load_weekly_data(JSON_PATH)
weekly_dict = to_week_dict(weekly_list)
available_weeks = sorted(weekly_dict.keys())

if "generated_preview" not in st.session_state:
    st.session_state.generated_preview = None

tab1, tab2 = st.tabs(["weeklyインプット教材", "dailyリスニング教材"])

# ===========================
# weeklyインプット教材
# ===========================
with tab1:
    st.header("weeklyインプット教材")

    if not available_weeks:
        st.warning("表示できる週がありません。下の『新しく生成する』で作成するか、`weekly_input.json` にデータを追加してください。")
        st.stop()
    else:
        # 週選択
        options = [f"WEEK {n}" for n in available_weeks]
        selected = st.selectbox("学習する週を選択してください", options, index=len(options)-1)
        num = int(selected.split()[-1])
        item = weekly_dict[num]

        english_text = item.get("english_text", "")
        japanese_text = item.get("japanese_text", "")
        audio_file = item.get("audio_file", None)

        # 表示トグル
        show_jp = st.toggle("日本語訳を表示", value=False)
        st.write(english_text)
        if show_jp and japanese_text:
            st.write(japanese_text)

        # 音声
        if audio_file:
            if isinstance(audio_file, str) and (audio_file.startswith("http://") or audio_file.startswith("https://") or os.path.exists(audio_file)):
                st.audio(audio_file)
            else:
                st.info("音声ファイルのパスが無効か、存在しません。")
        # 選択週の音声を再生成するボタン
        if st.button("🔊 この週の音声を再生成（英語→TTS）", use_container_width=True):
            if english_text.strip():
                out_path = synthesize_audio(english_text, num)
                if out_path:
                    # JSON更新
                    for i, rec in enumerate(weekly_list):
                        if str(rec.get("week_num")) == str(num):
                            weekly_list[i]["audio_file"] = out_path
                            break
                    write_weekly_data(JSON_PATH, weekly_list)
                    load_weekly_data.clear()
                    weekly_list = load_weekly_data(JSON_PATH)
                    weekly_dict = to_week_dict(weekly_list)
                    available_weeks = sorted(weekly_dict.keys())
                    st.success(f"音声を生成しました：{out_path}")
                    st.audio(out_path)
                else:
                    st.error("音声の生成に失敗しました。")
            else:
                st.warning("英語テキストが空です。")

    # -----------------------
    # MYフレーズ登録 + 翻訳
    # -----------------------
    st.subheader("この教材からMYフレーズを登録")
    with st.form(key="phrase_form"):
        try:
            folder_choices = get_folders()
            if not folder_choices:
                folder_choices = ["MYフレーズ集", "言えなかったフレーズ", "環境問題", "単語"]
        except Exception:
            folder_choices = ["MYフレーズ集", "言えなかったフレーズ", "環境問題", "単語"]

        selected_folder = st.multiselect("どちらのフレーズ集に追加しますか？", folder_choices)

        col_a, col_b = st.columns(2)
        with col_a:
            jp_input = st.text_area("日本語", key="jp_input", placeholder="例：それは素晴らしい考えです。")
        with col_b:
            en_input = st.text_area("英語", key="en_input", placeholder="例：That's a great idea.")

        do_translate = st.checkbox("翻訳する（片方だけ入力でOK：自動で日↔英を判定）")
        translate_btn = st.form_submit_button("翻訳する")
        submit_btn = st.form_submit_button("登録する")

        if do_translate and translate_btn:
            try:
                src = (jp_input or "").strip() or (en_input or "").strip()
                if not src:
                    st.warning("翻訳するテキストを日本語または英語のどちらかに入力してください。")
                else:
                    tr = translate_text(client, src)
                    if not jp_input:
                        jp_input = tr["japanese"]
                    if not en_input:
                        en_input = tr["english"]
                    st.success("翻訳しました。必要に応じて編集してから『登録する』を押してください。")
                    st.markdown("**翻訳結果（英語）**"); st.write(tr["english"])
                    st.markdown("**翻訳結果（日本語）**"); st.write(tr["japanese"])
            except Exception as e:
                st.error(f"翻訳中にエラーが発生しました: {e}")

        if submit_btn:
            if not selected_folder:
                st.warning("追加先のフォルダを1つ以上選んでください。")
            elif not ((jp_input or "").strip() and (en_input or "").strip()):
                st.warning("日本語と英語の両方を入力してください（翻訳ボタンで自動補完も可能です）。")
            else:
                ok = 0
                for f in selected_folder:
                    try:
                        add_phrase(f, jp_input.strip(), en_input.strip())
                        ok += 1
                    except Exception as e:
                        st.error(f"'{f}' への追加でエラー: {e}")
                if ok:
                    st.success(f"{ok} 件のフォルダにフレーズを登録しました！")
    st.divider()
    st.subheader("")
    
    # 録音
    wav_audio_data = st_audiorec()

    if wav_audio_data is not None:
        st.subheader("録音した音声")
        st.audio(wav_audio_data, format="audio/wav")

        c1, c2, _ = st.columns([1,1,2])
        with c1:
            if st.button("保存"):
                handle_recording(
                    category="input",              # ← 入力側なので "input"
                    eng_txt=english_text,          # ← 選択中の英語本文
                    jpn_txt=japanese_text,         # ← 選択中の日本語訳
                    wav_audio_data=wav_audio_data,
                )
        with c2:
            st.download_button("⬇️ ダウンロード", wav_audio_data,
                            file_name="input_recorded.wav", mime="audio/wav")

    st.divider()
    st.subheader("教材生成")
    st.caption("TOEFLレベルの英文＋日本語訳をAPIで自動生成し、音声も作って weekly_input.json に追記保存します。")

    # 生成ボタン
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        gen_btn = st.button("🔁 新しく生成（保存まで自動）", use_container_width=True)
    with c2:
        only_preview = st.button("📝 プレビューのみ（保存しない）", use_container_width=True)
    with c3:
        gen_audio = st.checkbox("同時に音声も作る", value=True)

    progress = st.progress(0)

    if gen_btn or only_preview:
        try:
            progress.progress(15)
            data = generate_toefl_passage(client)
            progress.progress(55)
            st.session_state.generated_preview = data

            with st.expander("生成結果プレビュー（保存前）", expanded=True):
                st.markdown("**English**")
                st.write(data["english"])
                st.markdown("**日本語訳**")
                st.write(data["japanese"])

            audio_path = None
            new_week_num = next_week_number(weekly_dict) if gen_btn else None

            # 音声も作成
            if gen_btn and gen_audio:
                progress.progress(70)
                audio_path = synthesize_audio(data["english"], new_week_num)
                progress.progress(80)

            if gen_btn:
                # 追記保存
                new_item = {
                    "week_num": str(new_week_num),
                    "english_text": data["english"],
                    "japanese_text": data["japanese"],
                    "audio_file": audio_path,
                }
                weekly_list.append(new_item)
                write_weekly_data(JSON_PATH, weekly_list)

                # キャッシュ更新
                load_weekly_data.clear()
                weekly_list = load_weekly_data(JSON_PATH)
                weekly_dict = to_week_dict(weekly_list)
                available_weeks = sorted(weekly_dict.keys())

                progress.progress(100)
                st.success(
                    f"WEEK {new_week_num} を保存しました！"
                    + (f"（音声: {audio_path}）" if audio_path else "（音声なし）")
                )
                if audio_path:
                    st.audio(audio_path)

        except Exception as e:
            st.error(f"生成・保存中にエラーが発生しました: {e}")

# ===========================
# Dailyリスニング教材（プレースホルダ）
# ===========================
with tab2:
    st.header("Dailyリスニング教材")
    st.info("将来: 日次教材APIやDBに接続予定。")

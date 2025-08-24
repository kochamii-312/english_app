# pages/3_🗣️_アウトプット練習.py

import streamlit as st
from st_audiorec import st_audiorec

st.set_page_config(page_title="アウトプット練習", layout="wide")

st.markdown("## 🗣️ アウトプット練習")
st.write("お手本のフレーズを参考に、あなたの発音を録音して確認してみましょう。")
st.divider()

# --- 練習したいフレーズの表示 ---
st.subheader("練習用フレーズ")
st.markdown("##### In terms of cost, this option is the most efficient.")
st.caption("費用の面では、この選択肢が最も効率的です。")

# お手本の音声を再生（ダミーの音声ファイルパス）
# st.audio("path/to/model_voice.mp3") # 必要であればお手本音声も配置

st.divider()

# --- 録音ウィジェット ---
st.subheader("マイクで録音")
st.info("下のaアイコンをクリックして録音を開始・停止します。")

# st_audiorecコンポーネントを呼び出す
wav_audio_data = st_audiorec() # 録音が完了すると、ここに音声データがbytes形式で入ります

# --- 録音後の処理 ---
if wav_audio_data is not None:
    st.subheader("録音した音声")
    # 録音された音声を再生
    st.audio(wav_audio_data, format='audio/wav')

    # ダウンロードボタン
    st.download_button(
        label="音声をダウンロード",
        data=wav_audio_data,
        file_name="recorded_voice.wav",
        mime="audio/wav"
    )
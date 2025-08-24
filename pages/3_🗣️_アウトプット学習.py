# pages/3_🗣️_アウトプット練習.py

import streamlit as st
from st_audiorec import st_audiorec

st.set_page_config(page_title="アウトプット練習", layout="wide")

st.markdown("## 🗣️ アウトプット練習")

tab1, tab2 = st.tabs(["discuss", "description"])

with tab1:
    st.subheader("Question")
    st.markdown("#### What is your hobby?")

    st.divider()

    # --- タイマー ---
    # メモ：自動で録音を開始し、30秒経ったら録音停止
    # 3回繰り返す

    # --- 録音ウィジェット ---
    st.subheader("マイクで録音")
    st.info("下のアイコンをクリックして録音を開始・停止します。")

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

with tab2:
    # --- 写真の表示 ---
    st.subheader("写真")
    st.markdown("Explain the picture below.")
    # メモ：情報量多めの写真生成

    # お手本の音声を再生（ダミーの音声ファイルパス）
    # st.audio("path/to/model_voice.mp3") # 必要であればお手本音声も配置

    st.divider()

    # --- タイマー ---
    # メモ：自動で録音を開始し、30秒経ったら録音停止
    # 3回繰り返す

    # --- 録音ウィジェット ---
    st.subheader("マイクで録音")
    st.info("下のアイコンをクリックして録音を開始・停止します。")

    # st_audiorecコンポーネントを呼び出す
    wav_audio_data_ = st_audiorec() # 録音が完了すると、ここに音声データがbytes形式で入ります

    # --- 録音後の処理 ---
    if wav_audio_data_ is not None:
        st.subheader("録音した音声")
        # 録音された音声を再生
        st.audio(wav_audio_data_, format='audio/wav')

        # ダウンロードボタン
        st.download_button(
            label="音声をダウンロード",
            data=wav_audio_data_,
            file_name="recorded_voice.wav",
            mime="audio/wav"
        )
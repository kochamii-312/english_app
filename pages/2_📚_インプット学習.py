# pages/2_📚_インプット学習.py (サンプルコード)
import streamlit as st
from database import (
    get_folders,
    add_folder,
    get_phrases_by_folder,
    add_phrase,
    update_phrase,
    delete_phrase
)

tab1, tab2 = st.tabs(["Weeklyインプット教材", "Dailyリスニング教材"])

with tab1:
    st.header("Weeklyインプット教材")
    """
    新しく生成するボタンを押すと、テーマを自動で選んで自分の話を生成
    """
    # メモ：新しく生成するボタン
    # 生成された文章はdictionaryに蓄積
    generate_btn = st.button("Weeklyインプット教材を生成します")
    progress = st.progress(0)

    # 教材選択
    week = st.selectbox("学習する週を選択してください", ["WEEK 9", "WEEK 10", "WEEK 11"])

    if week == "WEEK 9":
        num = 9
        # メモ：numはweekからWEEKを切り取ってintに変換したもの
    
    if num == 9:
        # メモ: dictionary型でkeyはnumにする
        # numをもとにしてデータを取得してくる
        # english_text = dict[num]
        english_text = "One of the issues I am particularly concerned about is the high level of stress..."
        japanese_text = "私が特に懸念している問題の一つは、高いレベルのストレスと睡眠不足です..."
        # audio_file = "path/to/week9_audio.mp3"

        # 日本語/英語の表示切り替え
        show_japanese = st.toggle("日本語訳を表示")
        if show_japanese:
            st.write(english_text)
            st.write(japanese_text)
        else:
            st.write(english_text)

        # 音声再生
        # st.audio(audio_file)

    # MYフレーズ登録
    st.subheader("この教材からMYフレーズを登録")
    
    translate = st.checkbox("フレーズ入力後、翻訳文を自動取得する")
    if translate:
        st.write("日本語か英語のフレーズを入力して「翻訳する」ボタンを押しましょう")
        if st.button("翻訳する"):
            # メモ：翻訳処理を書く
            st.markdown("#### 翻訳結果")
            st.info("翻訳結果をここに表示")

    with st.form(key="phrase_form"):

        selected_folder = st.multiselect(
            "どちらのフレーズ集に追加しますか？",
            ["MYフレーズ集", "言えなかったフレーズ", "環境問題", "単語"]
        )
        
        japanese_input = st.text_area("日本語", placeholder="例：それは素晴らしい考えです。")
        english_input = st.text_area("英語", placeholder="例：That's a great idea.")
        submit_button = st.form_submit_button(label="登録")

        if submit_button:
            if japanese_input and english_input:
                add_phrase(selected_folder, japanese_input, english_input)
                st.success(f"'{selected_folder}' フォルダにフレーズを登録しました！")
            else:
                st.warning("日本語と英語の両方を入力してください。")
        # st.switch_page("pages/5_✍️_MYフレーズ.py")

with tab2:
    st.header("Dailyリスニング教材")
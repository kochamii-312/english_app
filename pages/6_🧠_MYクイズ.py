# pages/6_🧠_MYクイズ.py (サンプルコード)
import streamlit as st
import pandas as pd

# st.session_stateを初期化
if 'current_q' not in st.session_state:
    st.session_state.current_q = 0

# (データベースからクイズデータを読み込む処理)
quiz_df = pd.DataFrame({
    "japanese": ["情報を伝える", "予想する"],
    "english": ["impart information", "foresee"]
})

st.header("MYクイズ")

# 現在の問題を表示
question = quiz_df.iloc[st.session_state.current_q]
st.write(f"問題 {st.session_state.current_q + 1}/{len(quiz_df)}")
st.subheader(question["japanese"])

# 解答表示エリア
with st.expander("解答を確認する"):
    st.write(question["english"])

# 次へ進むボタン
if st.button("次に進む"):
    if st.session_state.current_q < len(quiz_df) - 1:
        st.session_state.current_q += 1
        st.rerun() # ページを再読み込みして次の問題を表示
    else:
        st.success("クイズ終了！お疲れ様でした！")
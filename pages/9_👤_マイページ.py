import streamlit as st
import pandas as pd

st.set_page_config(page_title="マイページ", layout="centered")

# --- プロフィールデータ (デモ用) ---
profile_data = {
    "name": "Kaoru Yoshida",
    "image_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=400",
    "phase": 6,
    "details": {
        "音声性別": "Female",
        "性別": "女性",
        "年齢": 18,
        "職業": "学生",
        "職位": "大学1年生",
        "職業詳細": "理学部1年生で、数学、物理、化学、生物、情報を含めた教養科目を広く学んでいます...",
        "性格": "好奇心が旺盛で、様々なワークショップに参加することが好きです...",
        "趣味": "旅行、スキー、ドラマ鑑賞、ラジオ",
    },
    "skills": {
        "実施日": "11/29",
        "リスニング": 6,
        "正確性": 5,
        "流暢性": 4,
        "明瞭さ": 6
    }
}

# --- UI ---
st.title("👤 マイページ")
st.image(profile_data["image_url"], width=150)
st.header(profile_data["name"])

# 総合英語力フェーズ
st.subheader(f"総合英語力 Phase: {profile_data['phase']}")

with st.expander("詳細なスキルレベルを見る"):
    skill_df = pd.DataFrame([profile_data["skills"]]).set_index("実施日")
    st.table(skill_df)
    st.progress(profile_data["phase"] / 10.0) # 最大フェーズを10と仮定

st.divider()

# 詳細プロフィール
st.subheader("プロフィール詳細")
for key, value in profile_data["details"].items():
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"**{key}**")
    with col2:
        st.write(value)
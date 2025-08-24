import streamlit as st
import pandas as pd
from database import (
    get_folders,
    add_folder,
    get_phrases_by_folder,
    add_phrase,
    update_phrase,
    delete_phrase
)

st.set_page_config(page_title="MYフレーズ", layout="wide")

st.title("✍️ MYフレーズ管理")

# --- フォルダ管理 ---
st.sidebar.header("📁 フォルダ管理")

# フォルダ一覧を取得
folders = get_folders()

# フォルダの新規作成
with st.sidebar.expander("新しいフォルダを作成"):
    new_folder_name = st.text_input("フォルダ名", key="new_folder_name")
    if st.button("作成", key="create_folder"):
        if new_folder_name and new_folder_name not in folders:
            add_folder(new_folder_name)
            st.sidebar.success(f"フォルダ '{new_folder_name}' を作成しました。")
            st.rerun() # フォルダリストを更新するために再実行
        elif not new_folder_name:
            st.sidebar.warning("フォルダ名を入力してください。")
        else:
            st.sidebar.error("そのフォルダ名は既に使用されています。")

# 表示するフォルダをセレクトボックスで選択
selected_folder = st.selectbox("表示または追加したいフォルダを選択してください", folders)


# --- フレーズの新規登録 ---
st.header("➕ 新しいフレーズを登録")

with st.form(key="phrase_form", clear_on_submit=True):
    japanese_input = st.text_area("日本語", placeholder="例：それは素晴らしい考えです。")
    english_input = st.text_area("英語", placeholder="例：That's a great idea.")
    submit_button = st.form_submit_button(label="登録")

    if submit_button:
        if japanese_input and english_input:
            add_phrase(selected_folder, japanese_input, english_input)
            st.success(f"'{selected_folder}' フォルダにフレーズを登録しました！")
        else:
            st.warning("日本語と英語の両方を入力してください。")

st.divider()


# --- 登録済みフレーズの一覧と編集 ---
st.header(f"📘 「{selected_folder}」のフレーズ一覧")

# 選択されたフォルダのフレーズを取得
phrases_df = get_phrases_by_folder(selected_folder)

if not phrases_df.empty:
    # 削除ボタン用の列を追加
    phrases_df["delete"] = [False] * len(phrases_df)
    
    # st.data_editorで表形式で表示・編集
    edited_df = st.data_editor(
        phrases_df,
        column_config={
            "id": None, # ID列は非表示
            "japanese": st.column_config.TextColumn("日本語", width="large"),
            "english": st.column_config.TextColumn("英語", width="large"),
            "delete": st.column_config.CheckboxColumn("削除")
        },
        hide_index=True,
        key="phrase_editor"
    )

    # 変更をデータベースに反映
    # 削除処理
    deleted_ids = edited_df[edited_df["delete"]]["id"]
    if not deleted_ids.empty:
        for phrase_id in deleted_ids:
            delete_phrase(phrase_id)
        st.success(f"{len(deleted_ids)}件のフレーズを削除しました。")
        st.rerun()

    # 更新処理 (元のデータと比較して変更があった行を特定)
    try:
        # 元のデータと編集後のデータをIDでマージして比較
        comparison_df = pd.merge(phrases_df, edited_df, on='id', suffixes=('_orig', '_new'))
        
        # 内容が変更された行をフィルタリング
        changed_rows = comparison_df[
            (comparison_df['japanese_orig'] != comparison_df['japanese_new']) |
            (comparison_df['english_orig'] != comparison_df['english_new'])
        ]

        if not changed_rows.empty:
            for _, row in changed_rows.iterrows():
                update_phrase(row['id'], row['japanese_new'], row['english_new'])
            st.success(f"{len(changed_rows)}件のフレーズを更新しました。")
            st.rerun()

    except Exception as e:
        st.error(f"データの更新中にエラーが発生しました: {e}")

else:
    st.info("このフォルダにはまだフレーズが登録されていません。")
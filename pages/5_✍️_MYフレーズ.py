import json
import os
import re
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from database import (
    get_folders,
    add_folder,
    get_phrases_by_folder,
    add_phrase,
    update_phrase,
    delete_phrase
)
from pathlib import Path

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _is_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9faf]", text))

def translate_text(client: OpenAI, text: str) -> dict:
    """日↔英を自動判定して、{"english": "...", "japanese": "..."} を返す"""
    src_is_jp = _is_japanese(text)
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
    import json
    data = json.loads(content)
    return {"english": data["english"], "japanese": data["japanese"]}

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
selected_folder = st.selectbox("表示するフォルダを選択してください", folders)  # ← 文字列になる
add_target_folders = st.multiselect("追加先フォルダを選択（複数可）", folders)


# --- フレーズの新規登録 ---
st.header("➕ 新しいフレーズを登録")

with st.form(key="phrase_form", clear_on_submit=False):
    # 入力欄（キー付きに変更：翻訳結果を流し込める）
    col_a, col_b = st.columns(2)
    with col_a:
        japanese_input = st.text_area("日本語", key="jp_input", placeholder="例：それは素晴らしい考えです。")
    with col_b:
        english_input = st.text_area("英語", key="en_input", placeholder="例：That's a great idea.")

    do_translate = st.checkbox("翻訳する（片方だけ入力でOK：自動で日↔英を判定）")
    translate_button = st.form_submit_button("翻訳する")
    submit_button = st.form_submit_button("登録")

# 翻訳ハンドリング（フォーム外で state を更新して反映）
if do_translate and translate_button:
    src = (st.session_state.get("jp_input","").strip() or
           st.session_state.get("en_input","").strip())
    if not src:
        st.warning("翻訳するテキストを日本語または英語のどちらかに入力してください。")
    else:
        try:
            tr = translate_text(client, src)
            # 片方だけ入力だった場合は、空欄側を自動補完
            if not st.session_state.get("jp_input"):
                st.session_state.jp_input = tr["japanese"]
            if not st.session_state.get("en_input"):
                st.session_state.en_input = tr["english"]
            st.success("翻訳しました。必要に応じて編集してから『登録』を押してください。")
            st.markdown("**翻訳結果（英語）**"); st.write(tr["english"])
            st.markdown("**翻訳結果（日本語）**"); st.write(tr["japanese"])
        except Exception as e:
            st.error(f"翻訳中にエラーが発生しました: {e}")

# 登録ボタン（既存ロジックを state 参照に変更）
if submit_button:
    jp = (st.session_state.get("jp_input") or "").strip()
    en = (st.session_state.get("en_input") or "").strip()
    if not jp or not en:
        st.warning("日本語と英語の両方を入力してください（翻訳ボタンで自動補完も可能です）。")
    elif not add_target_folders:
        st.warning("追加先フォルダを1つ以上選んでください。")
    else:
        ok = 0
        for f in add_target_folders:
            add_phrase(f, jp, en)
            ok += 1
        st.success(f"{ok} 件のフォルダにフレーズを登録しました！")
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

if st.button("🗂️ すべてをJSONにエクスポート"):
    export = []
    for f in get_folders():
        df = get_phrases_by_folder(f)
        if not df.empty:
            for _, row in df.iterrows():
                export.append({
                    "id": int(row["id"]),
                    "folder": f,
                    "japanese": row["japanese"],
                    "english": row["english"],
                })
    out_path = Path("./json/phrases_export.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    st.success(f"JSONに書き出しました：{out_path}")
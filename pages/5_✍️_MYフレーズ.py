import json
import io
import os
import re
import streamlit as st
import pandas as pd
# from dotenv import load_dotenv
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

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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

# ===== CSV から MYフレーズへ一括追加 =====
st.markdown("---")
st.header("📥 CSVからMYフレーズに追加")

col0, col1, col2 = st.columns([2, 1, 1])
with col0:
    csv_file = st.file_uploader("CSVファイルをアップロード（Excel→CSVで書き出したものでもOK）", type=["csv"])
with col1:
    enc = st.selectbox("文字コード", ["utf-8-sig", "utf-8", "cp932(Shift_JIS)"], index=0)
with col2:
    sep_label = st.selectbox("区切り", ["カンマ(,)", "タブ(\\t)", "セミコロン(;)"], index=0)
sep_map = {"カンマ(,)": ",", "タブ(\\t)": "\t", "セミコロン(;)": ";"}
sep = sep_map[sep_label]

if "csv_preview" not in st.session_state:
    st.session_state.csv_preview = None
if "csv_mapped_cols" not in st.session_state:
    st.session_state.csv_mapped_cols = {"en": None, "jp": None, "folder": None}

if csv_file is not None:
    # 読み込み（失敗したらエラー表示）
    try:
        df = pd.read_csv(io.BytesIO(csv_file.read()), encoding=enc, sep=sep)
        st.session_state.csv_preview = df
    except Exception as e:
        st.error(f"CSVの読み込みに失敗しました: {e}")
        st.stop()

# プレビュー & マッピング
if st.session_state.csv_preview is not None:
    df = st.session_state.csv_preview
    st.caption("読み込んだ先頭行（プレビュー）")
    st.dataframe(df.head(20), use_container_width=True)

    cols = df.columns.tolist()
    # それっぽい列名を推測
    def _guess(cands):
        for c in cols:
            lc = str(c).lower()
            if any(k in lc for k in cands):
                return c
        return cols[0] if cols else None

    col_en = st.selectbox("英語の列", cols, index=cols.index(_guess(["english","en","eng"])) if cols else 0)
    col_jp = st.selectbox("日本語の列", cols, index=cols.index(_guess(["japanese","jp","ja","jpn"])) if cols else 0)
    col_folder = st.selectbox("フォルダ列（任意/1列）", ["(なし)"] + cols, index=0)

    st.session_state.csv_mapped_cols = {"en": col_en, "jp": col_jp, "folder": None if col_folder=="(なし)" else col_folder}

    st.write("—")

    # 追加先フォルダ（CSVにフォルダ列が無い場合は全行このフォルダへ）
    try:
        all_folders = get_folders()
    except Exception:
        all_folders = ["MYフレーズ集", "言えなかったフレーズ", "単語"]

    if st.session_state.csv_mapped_cols["folder"] is None:
        default_targets = st.multiselect("追加先フォルダ（CSVにフォルダ列が無い場合は全行このフォルダへ）", all_folders)
    else:
        default_targets = []  # フォルダ列を使う

    # オプション
    cA, cB, cC = st.columns(3)
    with cA:
        do_translate = st.checkbox("空欄は翻訳で補完（英↔日を自動判定）", value=True)
    with cB:
        create_missing = st.checkbox("存在しないフォルダは自動作成", value=True)
    with cC:
        dedupe = st.checkbox("既存と重複する行はスキップ", value=True)

    # 取込対象の作成（プレビュー）
    if st.button("👀 取込プレビューを作成", use_container_width=True):
        en_col = st.session_state.csv_mapped_cols["en"]
        jp_col = st.session_state.csv_mapped_cols["jp"]
        f_col = st.session_state.csv_mapped_cols["folder"]

        if en_col is None or jp_col is None:
            st.error("英語列と日本語列を指定してください。")
            st.stop()
        if f_col is None and not default_targets:
            st.warning("フォルダ列が無い場合は、追加先フォルダを1つ以上選んでください。")
            st.stop()

        # 既存DBの重複集合を用意
        existing_pairs_by_folder = {}
        if dedupe:
            try:
                for f in (all_folders if f_col is None else df[f_col].dropna().unique().tolist()):
                    if not f or str(f).strip() == "":
                        continue
                    try:
                        cur = get_phrases_by_folder(str(f))
                        if cur is not None and not cur.empty:
                            # 正規化（余分な空白除去）
                            s = set((str(r["japanese"]).strip(), str(r["english"]).strip()) for _, r in cur.iterrows())
                            existing_pairs_by_folder[str(f)] = s
                        else:
                            existing_pairs_by_folder[str(f)] = set()
                    except Exception:
                        existing_pairs_by_folder[str(f)] = set()
            except Exception:
                # フォルダ列がない場合の default_targets
                for f in default_targets:
                    try:
                        cur = get_phrases_by_folder(str(f))
                        if cur is not None and not cur.empty:
                            s = set((str(r["japanese"]).strip(), str(r["english"]).strip()) for _, r in cur.iterrows())
                            existing_pairs_by_folder[str(f)] = s
                        else:
                            existing_pairs_by_folder[str(f)] = set()
                    except Exception:
                        existing_pairs_by_folder[str(f)] = set()

        # 行を走査して取込候補を生成
        preview_rows = []
        for _, row in df.iterrows():
            en = str(row.get(en_col, "")).strip()
            jp = str(row.get(jp_col, "")).strip()

            # どのフォルダに入れるか
            targets = [str(row.get(f_col)).strip()] if (f_col is not None and str(row.get(f_col, "")).strip()) else default_targets
            if not targets:
                continue

            # 翻訳補完
            if do_translate and (not en or not jp):
                try:
                    tr = translate_text(client, en or jp)  # どちらか片方を渡す（関数側で自動判定）
                    if not en:
                        en = tr["english"].strip()
                    if not jp:
                        jp = tr["japanese"].strip()
                except Exception as e:
                    st.warning(f"翻訳補完に失敗した行があります: {e}")

            # 空行スキップ
            if not en and not jp:
                continue

            # 重複チェック（対象フォルダごとに）
            dup_in = []
            if dedupe:
                for f in targets:
                    ex = existing_pairs_by_folder.get(str(f), set())
                    if (jp, en) in ex:
                        dup_in.append(str(f))

            preview_rows.append({
                "english": en,
                "japanese": jp,
                "folders": ", ".join(targets),
                "duplicate_in": ", ".join(dup_in) if dup_in else ""
            })

        if not preview_rows:
            st.warning("取込対象がありません（空行のみ/フォルダ未指定/すべて重複の可能性）。")
        else:
            st.session_state.csv_import_preview = pd.DataFrame(preview_rows)
            st.success(f"{len(preview_rows)} 行をプレビューに追加しました。下で確認して『インポート実行』を押してください。")

    # プレビュー表示 & インポート実行
    if "csv_import_preview" in st.session_state and isinstance(st.session_state.csv_import_preview, pd.DataFrame):
        st.dataframe(st.session_state.csv_import_preview, use_container_width=True)

        if st.button("📥 インポート実行", type="primary", use_container_width=True):
            dfp = st.session_state.csv_import_preview
            done = 0
            skipped = 0
            created_folders = 0

            # 存在しないフォルダを作成（オプション）
            if create_missing:
                # プレビューの folders 列から候補抽出
                want_folders = set()
                for fs in dfp["folders"]:
                    for f in [x.strip() for x in str(fs).split(",") if str(fs).strip()]:
                        want_folders.add(f)
                # 既存との差分を作成
                try:
                    cur_folders = set(get_folders())
                except Exception:
                    cur_folders = set()
                for f in (want_folders - cur_folders):
                    try:
                        add_folder(f)
                        created_folders += 1
                    except Exception:
                        pass

            # 実インポート
            progress = st.progress(0)
            for i, row in dfp.iterrows():
                en = str(row["english"]).strip()
                jp = str(row["japanese"]).strip()
                targets = [x.strip() for x in str(row["folders"]).split(",") if str(row["folders"]).strip()]
                dups = [x.strip() for x in str(row.get("duplicate_in","")).split(",") if str(row.get("duplicate_in","")).strip()]

                for f in targets:
                    if dedupe and f in dups:
                        skipped += 1
                        continue
                    try:
                        add_phrase(f, jp, en)
                        done += 1
                    except Exception as e:
                        st.error(f"『{f}』への追加でエラー: {e}")
                progress.progress(int((i+1)/len(dfp)*100))

            st.success(f"インポート完了：追加 {done} 件 / スキップ(重複) {skipped} 件 / 新規フォルダ作成 {created_folders} 件")
            # 後片付け
            del st.session_state["csv_import_preview"]

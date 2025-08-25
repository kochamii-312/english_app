# pages/6_🧠_MYクイズ.py
import random
import re
import streamlit as st

# 既存DBユーティリティ
from database import get_folders, get_phrases_by_folder

st.set_page_config(page_title="🧠 MYクイズ", page_icon="🧠", layout="centered")
st.header("🧠 MYクイズ")

# ---------------- ヘルパー ----------------
def _norm_text(s: str) -> str:
    """大文字小文字・余分な空白・句読点差を吸収する簡易正規化（英日両対応）"""
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    # 句読点など広めに除去（ひらカナ漢字は残す／- ' は残す）
    s = re.sub(r"[^\w\s'\-ぁ-んァ-ン一-龥]", "", s, flags=re.UNICODE)
    return s.lower()

def _overlap_ratio(a: str, b: str) -> float:
    """英語の単語Jaccard重なりで緩め採点（日本語は正規化一致を優先）"""
    a_n = _norm_text(a)
    b_n = _norm_text(b)
    if not a_n or not b_n:
        return 1.0 if a_n == b_n else 0.0
    aw = set(re.findall(r"[a-zA-Z']+", a_n))
    bw = set(re.findall(r"[a-zA-Z']+", b_n))
    if not aw or not bw:
        return 1.0 if a_n == b_n else 0.0
    return len(aw & bw) / len(aw | bw)

# --------------- セッション ---------------
if "quiz_items" not in st.session_state:
    st.session_state.quiz_items = []   # [{id, q, a}]
if "quiz_meta" not in st.session_state:
    st.session_state.quiz_meta = {"folder": None, "direction": "日→英", "num_q": 10}
if "quiz_results" not in st.session_state:
    st.session_state.quiz_results = {} # idx -> {"checked": bool, "correct": bool, "ratio": float}

# --------------- 設定UI -------------------
try:
    folders = get_folders()
except Exception as e:
    folders = []
    st.error(f"フォルダの取得に失敗しました: {e}")

if not folders:
    st.info("まずは『MYフレーズ』に単語を登録してください。")
    st.stop()

colA, colB, colC = st.columns([2, 2, 1])
with colA:
    init_idx = folders.index(st.session_state.quiz_meta["folder"]) if st.session_state.quiz_meta["folder"] in folders else 0
    quiz_folder = st.selectbox("出題するフォルダ", folders, index=init_idx)
with colB:
    direction = st.radio("出題方向", ["日→英", "英→日"], horizontal=True, index=0 if st.session_state.quiz_meta["direction"]=="日→英" else 1)
with colC:
    num_q = st.number_input("出題数", min_value=1, max_value=100, value=st.session_state.quiz_meta["num_q"], step=1)

c1, c2 = st.columns([1,1])
with c1:
    make_btn = st.button("📝 問題を作成 / 再生成", use_container_width=True)
with c2:
    reset_btn = st.button("🧹 クリア", use_container_width=True)

if reset_btn:
    st.session_state.quiz_items = []
    st.session_state.quiz_results = {}
    st.rerun()

# --------------- 問題作成 -----------------
if make_btn:
    try:
        df = get_phrases_by_folder(quiz_folder)  # ※ multiselectは不可。文字列を渡す
    except Exception as e:
        df = None
        st.error(f"単語の取得に失敗しました: {e}")

    if df is None or df.empty:
        st.warning("このフォルダにはまだ単語がありません。")
    else:
        need = {"id", "japanese", "english"}
        if not need.issubset(set(df.columns)):
            st.error("データの列名が不足しています（id, japanese, english が必要）。")
        else:
            items = df[["id","japanese","english"]].to_dict("records")
            random.shuffle(items)
            items = items[: int(num_q)]

            quiz_items = []
            for it in items:
                if direction == "日→英":
                    quiz_items.append({"id": it["id"], "q": it["japanese"], "a": it["english"]})
                else:
                    quiz_items.append({"id": it["id"], "q": it["english"], "a": it["japanese"]})

            st.session_state.quiz_items = quiz_items
            st.session_state.quiz_results = {}  # クリア
            st.session_state.quiz_meta = {"folder": quiz_folder, "direction": direction, "num_q": int(num_q)}
            st.success(f"『{quiz_folder}』から {len(quiz_items)} 問を作成しました。下のエクスパンダーで解いてください。")

# --------------- 全問エクスパンダー表示 ---------------
items = st.session_state.quiz_items
if items:
    st.caption(f"出題元: 『{st.session_state.quiz_meta['folder']}』 / 方向: {st.session_state.quiz_meta['direction']} / 全{len(items)}問")

    # 各問題を独立したエクスパンダーで表示
    for idx, item in enumerate(items):
        # エクスパンダーのタイトルに問題の先頭を少し載せる
        title_snippet = item["q"] if len(item["q"]) <= 20 else item["q"][:20] + " ..."
        with st.expander(f"問題 {idx+1}：{title_snippet}", expanded=(idx==0)):
            st.markdown("**問題**")
            st.write(item["q"])

            # 回答欄（キーで個別管理）
            ans_key = f"ans_{idx}"
            user_ans = st.text_area("あなたの解答", key=ans_key, placeholder="ここに回答を入力", height=120)

            # ボタン群（個別キー）
            colx, coly = st.columns([1,1])
            with colx:
                check = st.button("答え合わせ", key=f"check_{idx}")
            with coly:
                reveal = st.button("正解を見る", key=f"reveal_{idx}")

            # 既に採点済みかどうか
            res = st.session_state.quiz_results.get(idx, {"checked": False})

            # 採点処理
            if check:
                gold = item["a"]
                exact = (_norm_text(user_ans) == _norm_text(gold))
                ratio = _overlap_ratio(user_ans, gold)
                is_correct = exact or (ratio >= 0.8)
                st.session_state.quiz_results[idx] = {"checked": True, "correct": is_correct, "ratio": float(ratio)}

            # 結果表示（採点済みなら表示）
            res = st.session_state.quiz_results.get(idx, {"checked": False})
            if res.get("checked"):
                gold = item["a"]
                if res.get("correct"):
                    st.success("✅ 正解！")
                else:
                    st.error("❌ 不正解")
                st.markdown("**模範解答**")
                st.write(gold)
                st.caption(f"一致度: {int(res.get('ratio',0.0)*100)}%")

            # 正解だけ見る
            if reveal and not res.get("checked"):
                st.info("**模範解答** を表示します。")
                st.write(item["a"])

    # --------------- スコア集計 ---------------
    checked = [v for v in st.session_state.quiz_results.values() if v.get("checked")]
    correct = [v for v in checked if v.get("correct")]
    st.markdown("---")
    cA, cB, cC = st.columns(3)
    with cA:
        st.metric("回答済み", len(checked))
    with cB:
        st.metric("正解数", len(correct))
    with cC:
        st.metric("正答率", f"{(len(correct)/len(checked)*100):.0f}%" if checked else "—")

    # 再挑戦ボタン
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("同じ設定でもう一度作り直す"):
            st.session_state.quiz_items = []
            st.session_state.quiz_results = {}
            st.rerun()
    with c2:
        if st.button("この問題群を保持してスコアだけリセット"):
            st.session_state.quiz_results = {}
            st.rerun()

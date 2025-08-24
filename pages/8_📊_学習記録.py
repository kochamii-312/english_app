import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from database import get_study_log, log_study_session

st.set_page_config(page_title="学習記録", layout="wide")
st.title("📊 学習記録")

# --- 記録フォーム ---
with st.sidebar:
    st.header("📝 学習時間を記録")
    # st.formでウィジェットを囲む
    with st.form(key="log_form"):
        duration = st.number_input("今日の学習時間（分）", min_value=0, value=30, step=5)
        
        # ボタンをst.form_submit_buttonに変更
        submitted = st.form_submit_button("記録する")
        
        if submitted:
            log_study_session(duration)
            st.success(f"{duration}分の学習を記録しました！")
            
            # キャッシュをクリアしてグラフを更新
            st.cache_data.clear() 
            st.rerun()
            
# データベースから学習記録を取得
df = get_study_log()

# データがない場合の初期表示
if df.empty:
    st.info("まだ学習記録がありません。サイドバーから今日の学習時間を記録してみましょう！")
    # ダミーデータを作成して表示
    st.subheader("表示例")
    today = datetime.now()
    dates = [today - timedelta(days=x) for x in range(20)]
    minutes = np.random.randint(15, 60, size=20)
    df = pd.DataFrame({'session_date': dates, 'duration_minutes': minutes})

# --- UI ---
tab1, tab2 = st.tabs(["📈 学習グラフ", "🗓️ カレンダー"])

with tab1:
    st.header("学習グラフ")
    period_options = ["日別", "週別", "月別", "全期間"]
    selected_period = st.radio("表示期間を選択", period_options, horizontal=True)

    # 日付をインデックスに設定
    df_indexed = df.set_index('session_date')

    # 集計
    if selected_period == "日別":
        data_to_show = df_indexed.resample('D').sum()
        st.bar_chart(data_to_show['duration_minutes'])
    elif selected_period == "週別":
        data_to_show = df_indexed.resample('W-MON').sum()
        st.bar_chart(data_to_show['duration_minutes'])
    elif selected_period == "月別":
        data_to_show = df_indexed.resample('M').sum()
        st.bar_chart(data_to_show['duration_minutes'])
    else: # 全期間
        total_minutes = df['duration_minutes'].sum()
        total_hours = total_minutes / 60
        st.metric(label="累計学習時間", value=f"{total_hours:.1f} 時間", delta=f"{total_minutes} 分")
        st.bar_chart(df.set_index('session_date')['duration_minutes'])

with tab2:
    st.header("学習カレンダー")
    
    # カレンダー用のイベントデータを作成
    calendar_events = []
    if not df.empty:
        # 日付ごとに学習時間を集計
        daily_summary = df.groupby('session_date')['duration_minutes'].sum().reset_index()
        for _, row in daily_summary.iterrows():
            calendar_events.append({
                "title": f"{row['duration_minutes']} min",
                "start": row['session_date'].strftime("%Y-%m-%d"),
                "allDay": True, # 終日イベントとして表示
            })
            
    calendar_options = {
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
        "initialView": "dayGridMonth",
    }

    # カレンダーコンポーネント
    cal = calendar(
        events=calendar_events,
        options=calendar_options,
        custom_css="""
        .fc-event-past { opacity: 0.8; }
        .fc-event-time { font-style: italic; }
        .fc-event-title { font-weight: 700; }
        .fc-toolbar-title { font-size: 1.5rem; }
        """
    )
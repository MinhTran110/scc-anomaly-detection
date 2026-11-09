# dashboard_monitor.py
"""
SCC Outbound: Real-time Anomaly Detection & Machine Learning Analytics Dashboard
Phiên bản 3.1:
1. Bảng Sự Cố Vận Hành tinh gọn: Loại bỏ các chỉ số học thuật (z-score, ml_score, ML Verdict), tập trung vào chỉ số nghiệp vụ và khuyến nghị xử lý.
2. Machine Learning thực thụ: 
   - Phân tích chu kỳ sinh học 24h (Seasonality Decomposition) từ dữ liệu lịch sử.
   - Dự báo khả năng gặp sự cố / Nguy cơ bất thường theo từng khung giờ (Historical Risk Forecasting).
3. Tự động nhận diện ngày trực tiếp đa ngày, chuyển ngày mượt mà sau 17:30.
4. Mở trang tức thì (< 0.5s), hiệu năng cao.
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

st.set_page_config(
    page_title="SCC Outbound - Realtime Anomaly & ML Monitor",
    page_icon="📞",
    layout="wide"
)

# ==============================================================================
# QUẢN LÝ THEME GIAO DIỆN: SÁNG ☀️ / TỐI 🌙
# ==============================================================================
if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "Sáng ☀️"

theme_mode = st.session_state["theme_mode"]
is_dark = (theme_mode == "Tối 🌙")

bg_main = "#0b0f19" if is_dark else "#f8fafc"
card_bg = "#111827" if is_dark else "#ffffff"
border_col = "#1f2937" if is_dark else "#e2e8f0"
text_main = "#f8fafc" if is_dark else "#0f172a"
text_muted = "#94a3b8" if is_dark else "#64748b"
radio_bg = "#111827" if is_dark else "#ffffff"
tab_active_bg = "#1e293b" if is_dark else "#e0f2fe"
tab_active_text = "#38bdf8" if is_dark else "#0369a1"
plotly_template = "plotly_dark" if is_dark else "plotly_white"
plotly_grid = "#1f2937" if is_dark else "#f1f5f9"
plotly_line = "#374151" if is_dark else "#cbd5e1"
color_scheme = "dark" if is_dark else "light"
cal_text_color = "#ffffff" if is_dark else "#0f172a"

st.markdown(f"""
<style>
:root {{
    color-scheme: {color_scheme} !important;
}}

/* 1. NỀN TOÀN TRANG ĐỒNG NHẤT */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main, .block-container {{
    background-color: {bg_main} !important;
    color: {text_main} !important;
}}
[data-testid="stHeader"] {{
    background-color: {bg_main} !important;
}}

/* ẨN TOÀN BỘ SIDEBAR THEO YÊU CẦU */
[data-testid="stSidebar"], section[data-testid="stSidebar"] {{
    display: none !important;
}}

/* VĂN BẢN VÀ TIÊU ĐỀ SẮC NÉT */
h1, h2, h3, h4, h5, h6, p, span, label {{
    color: {text_main} !important;
}}

/* 2. THANH TAB ĐIỀU HƯỚNG HIỆN ĐẠI */
.stTabs [data-baseweb="tab-list"] {{
    gap: 10px !important;
    background-color: transparent !important;
    border-bottom: 2px solid {border_col} !important;
    padding-bottom: 0px !important;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: {card_bg} !important;
    color: {text_muted} !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    padding: 8px 18px !important;
    border-radius: 6px 6px 0 0 !important;
    border: 1px solid {border_col} !important;
    border-bottom: none !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
}}
.stTabs [aria-selected="true"] {{
    background-color: {tab_active_bg} !important;
    color: {tab_active_text} !important;
    font-weight: 700 !important;
    border-color: {tab_active_text} !important;
    border-bottom: 2px solid {tab_active_text} !important;
}}

/* 3. BỘ LỌC LỊCH (CALENDAR DATE PICKER) & POPUP LỊCH */
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] {{
    background-color: {card_bg} !important;
    border: 1px solid {border_col} !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
}}
div[data-baseweb="input"] input, div[data-baseweb="base-input"] input {{
    background-color: transparent !important;
    color: {text_main} !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
}}
div[data-baseweb="input"] svg {{
    fill: {text_main} !important;
}}

/* POPOVER LỊCH VÀ TOÀN BỘ CÁC THẺ CON BÊN TRONG CALENDAR */
div[data-baseweb="popover"],
div[data-baseweb="popover"] div,
div[data-baseweb="calendar"],
div[data-baseweb="calendar"] div {{
    background-color: {card_bg} !important;
    border-color: {border_col} !important;
    color: {cal_text_color} !important;
}}
div[data-baseweb="popover"] {{
    border-radius: 12px !important;
    border: 1px solid {border_col} !important;
    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.4) !important;
}}

/* TOÀN BỘ CHỮ, NÚT BẤM, THÁNG, NĂM VÀ ICON TRONG LỊCH */
div[data-baseweb="calendar"] *,
div[data-baseweb="calendar"] button,
div[data-baseweb="calendar"] button *,
div[data-baseweb="calendar"] [aria-live="polite"],
div[data-baseweb="calendar"] [aria-live="polite"] * {{
    color: {cal_text_color} !important;
    fill: {cal_text_color} !important;
}}

/* Nút chọn tháng và năm (StyledMonthYearSelectButton) */
div[data-baseweb="calendar"] button {{
    background-color: transparent !important;
    color: {cal_text_color} !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    border: none !important;
    cursor: pointer !important;
}}
div[data-baseweb="calendar"] button:hover {{
    background-color: {tab_active_bg} !important;
    color: {tab_active_text} !important;
}}

/* Nút mũi tên chuyển tháng < và > */
div[data-baseweb="calendar"] button svg,
div[data-baseweb="calendar"] button svg path {{
    fill: {cal_text_color} !important;
    stroke: {cal_text_color} !important;
    color: {cal_text_color} !important;
}}

/* Dropdown menu chọn tháng / năm */
ul[role="listbox"],
ul[role="listbox"] *,
div[role="listbox"],
div[role="listbox"] * {{
    background-color: {card_bg} !important;
    color: {cal_text_color} !important;
}}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
}}

/* TIÊU ĐỀ THỨ (Su, Mo, Tu, We, Th, Fr, Sa) */
div[data-baseweb="calendar"] [role="row"] > div[aria-hidden="true"],
div[data-baseweb="calendar"] [role="columnheader"] {{
    background-color: transparent !important;
    color: {text_muted} !important;
    font-weight: 600 !important;
    font-size: 12px !important;
}}

/* Ô NGÀY TRONG LỊCH */
div[data-baseweb="calendar"] [role="gridcell"] {{
    color: {cal_text_color} !important;
    font-size: 13px !important;
}}
div[data-baseweb="calendar"] [role="gridcell"] > div {{
    color: {cal_text_color} !important;
}}
div[data-baseweb="calendar"] [role="gridcell"]:hover > div {{
    background-color: {tab_active_bg} !important;
    color: {tab_active_text} !important;
}}

/* NGÀY ĐANG ĐƯỢC CHỌN (SELECTED) */
div[data-baseweb="calendar"] [aria-selected="true"],
div[data-baseweb="calendar"] [aria-selected="true"] > div,
div[data-baseweb="calendar"] [aria-selected="true"]:hover > div {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 50% !important;
}}
div[data-baseweb="calendar"] [aria-selected="true"] * {{
    color: #ffffff !important;
}}

/* NGÀY VÔ HIỆU HÓA (NGOÀI DẢI CHỌN) */
div[data-baseweb="calendar"] [aria-disabled="true"],
div[data-baseweb="calendar"] [aria-disabled="true"] * {{
    color: {"#374151" if is_dark else "#cbd5e1"} !important;
    opacity: 0.3 !important;
    cursor: not-allowed !important;
}}

/* 4. ẨN HOÀN TOÀN CÁC NÚT TRIGGER KHỎI GIAO DIỆN MÀN HÌNH */
div[data-testid="stButton"] {{
    position: fixed !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}}

/* 5. NÚT CHỌN RADIO */
div[data-testid="stRadio"] > div {{
    background-color: {card_bg} !important;
    border: 1px solid {border_col} !important;
    border-radius: 8px !important;
    padding: 5px 12px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
}}
div[data-testid="stRadio"] label {{
    color: {text_main} !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}}

/* 5. CÁC KHỐI BIỂU ĐỒ & BẢNG SỰ CỐ */
div[data-testid="stDataFrame"] {{
    background-color: {card_bg} !important;
    border: 1px solid {border_col} !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
}}
div[data-testid="stPlotlyChart"] {{
    background-color: {card_bg} !important;
    border: 1px solid {border_col} !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
    padding: 6px !important;
}}
div[data-testid="stMetric"] {{
    background-color: {card_bg} !important;
    border: 1px solid {border_col} !important;
    border-radius: 8px !important;
    padding: 12px 14px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
}}
div[data-testid="stMetricLabel"] * {{
    color: {text_muted} !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}}
div[data-testid="stMetricValue"] * {{
    color: {text_main} !important;
    font-size: 22px !important;
    font-weight: 700 !important;
}}

/* ĐƯỜNG PHÂN CÁCH TINH TẾ */
hr {{
    border-color: {border_col} !important;
    margin: 16px 0 !important;
}}
</style>
""", unsafe_allow_html=True)


BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STREAM_FILE = DATA_DIR / "stream_buffer.csv"
SEED_FILE = DATA_DIR / "seed_historical_stream.csv"
SIGNAL_FILE = DATA_DIR / "reset_signal.flag"
HIST_FILE = Path(__file__).resolve().parent.parent / "data" / "outbound_calls_timeseries_hourly_may.csv"
if not HIST_FILE.exists():
    HIST_FILE = DATA_DIR / "outbound_calls_timeseries_hourly_may.csv"

from daily_reporter import (
    process_single_date,
    export_and_send_daily_report,
    generate_daily_report_chart,
    compute_dynamic_error_threshold,
    HOURLY_PROFILE,
    ALPHA_PRIOR,
    BETA_PRIOR,
    MIN_CALL_FLOOR,
    MIN_FAIL_FLOOR,
    MIN_SPIKE_VOLUME_FLOOR
)

# ==============================================================================
# 1. CẤU HÌNH BOT TELEGRAM
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8766045148:AAGDiMEkFpS4fZeshHZfMmctwdBXrFnwldc"
TELEGRAM_CHAT_IDS = ["-5321779393", "8112925591"]
TELEGRAM_PROXIES = {
    "http": "http://proxy.fpt.vn:80",
    "https": "http://proxy.fpt.vn:80"
}

def send_telegram_msg(text: str):
    """Gửi tin nhắn văn bản HTML qua Telegram API có hỗ trợ Squid Proxy FPT."""
    if not TELEGRAM_BOT_TOKEN:
        return False, "Chưa điền Token Bot"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    success_count = 0
    errors = []
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            res = requests.post(url, json=payload, proxies=TELEGRAM_PROXIES, timeout=10)
            data = res.json()
            if data.get("ok"):
                success_count += 1
            else:
                errors.append(f"{chat_id}: {data.get('description', 'Unknown error')}")
        except Exception as e:
            errors.append(f"{chat_id}: {str(e)}")
    if success_count > 0:
        return True, f"Thành công ({success_count}/{len(TELEGRAM_CHAT_IDS)} chats)"
    return False, "; ".join(errors)

def notify_red_alert_telegram(bucket_str, calls_total, calls_503, err_rate, threshold, zscore, is_drop, ml_score, bad_call_samples):
    """Thông báo P1: Sự cố hạ tầng (Lỗi 503 vượt ngưỡng động hoặc Sập lưu lượng)."""
    sub_title = "NGHẼN MẠNG SIP TRUNK 503" if not is_drop else "SẬP LƯU LƯỢNG ĐỘT NGỘT (TRAFFIC COLLAPSE)"
    msg = (
        f"🚨🚨🚨 <b>[SCC OUTBOUND - P1 RED ALERT: {sub_title}]</b> 🚨🚨🚨\n\n"
        f"⏰ <b>Khung phát hiện:</b> <code>{bucket_str}</code>\n"
        f"📊 <b>Lưu lượng khung:</b> {calls_total} cuộc gọi\n"
        f"❌ <b>Số cuộc lỗi 503:</b> <b>{calls_503} cuộc</b>\n"
        f"📉 <b>Tỷ lệ lỗi mượt:</b> <b>{err_rate:.1f}%</b> (Ngưỡng động Bayes: {threshold:.1f}%)\n\n"
        "⚠️ <b>NỘI DUNG YÊU CẦU XỬ LÝ (P1 ACTION):</b>\n"
        "1. Kích hoạt kiểm tra Gateway viễn thông và kết nối SIP Trunk ngay lập tức.\n"
        "2. Kiểm tra log định tuyến trung kế SCC Outbound.\n"
        "3. Điều chuyển hướng sang trung kế dự phòng nếu cuộc gọi không thể thiết lập.\n"
    )
    if bad_call_samples is not None and not bad_call_samples.empty:
        msg += "\n🔍 <b>Chi tiết cuộc gọi lỗi 503 trong khung:</b>\n"
        for _, row in bad_call_samples.head(5).iterrows():
            t_str = row['start_time'].strftime('%H:%M:%S') if hasattr(row['start_time'], 'strftime') else str(row['start_time'])
            msg += f"• Call ID <code>{row['call_id']}</code> ({t_str}) - {row['duration']}s\n"
    return send_telegram_msg(msg)

# ==============================================================================
# 2. MACHINE LEARNING ENGINE: PHÂN TÍCH CHU KỲ VÀ DỰ BÁO RỦI RO ĐỘNG TỪ TOÀN BỘ DATA LỊCH SỬ
# ==============================================================================
def compute_dynamic_seasonality_and_risk(past_days_ts: dict, today_completed_ts: pd.DataFrame = None):
    """
    Tính toán động chu kỳ 24h và hồ sơ xác suất rủi ro theo giờ
    dựa trên TOÀN BỘ dữ liệu các ngày lịch sử đã qua + các khung giờ đã chốt hôm nay.
    Không cache tĩnh, tự động cập nhật liên tục theo luồng dữ liệu thực tế trong stream_buffer.csv.
    """
    frames = []
    if past_days_ts:
        frames.extend(list(past_days_ts.values()))
    if today_completed_ts is not None and not today_completed_ts.empty:
        frames.append(today_completed_ts)

    if not frames:
        hourly_stats = {}
        for h in range(24):
            mu_d = HOURLY_PROFILE.get(str(h), {}).get("mu", 0.5)
            sd_d = HOURLY_PROFILE.get(str(h), {}).get("sd", 0.8)
            hourly_stats[h] = {
                "mean_15m": mu_d,
                "sd_15m": sd_d,
                "risk_pct": 5.0,
                "tot_days": 1,
                "day_incidents": 0,
                "p1_count": 0,
                "p2_count": 0
            }
        return hourly_stats, 0, 0

    combined = pd.concat(frames, ignore_index=True)
    combined["has_anomaly"] = combined["is_p1_red"] | combined["is_p2_yellow"]
    combined["date"] = combined["bucket_time"].dt.date

    tot_distinct_days = int(combined["date"].nunique())
    tot_buckets = len(combined)

    hourly_stats = {}
    for h in range(24):
        sub = combined[combined["hour"] == h]
        if not sub.empty:
            m = float(np.round(sub["calls_total"].mean(), 2))
            s = float(np.round(sub["calls_total"].std(ddof=0), 2))
            s = max(s, 0.6)
            h_days = int(sub["date"].nunique())
            day_inc = int(sub.groupby("date")["has_anomaly"].any().sum())
            risk = float(np.round((day_inc / h_days * 100), 1)) if h_days > 0 else 5.0
            p1 = int(sub["is_p1_red"].sum())
            p2 = int(sub["is_p2_yellow"].sum())
        else:
            mu_d = HOURLY_PROFILE.get(str(h), {}).get("mu", 0.2)
            sd_d = HOURLY_PROFILE.get(str(h), {}).get("sd", 0.8)
            m = mu_d
            s = sd_d
            risk = 5.0
            h_days = tot_distinct_days
            day_inc = 0
            p1 = 0
            p2 = 0

        hourly_stats[h] = {
            "mean_15m": m,
            "sd_15m": s,
            "risk_pct": risk,
            "tot_days": h_days,
            "day_incidents": day_inc,
            "p1_count": p1,
            "p2_count": p2
        }

    return hourly_stats, tot_distinct_days, tot_buckets

# ==============================================================================
# 3. ENGINE TỔNG HỢP PIPELINE & STATE
# ==============================================================================
def get_current_pipeline_state():
    """Đọc dữ liệu buffer, tổng hợp theo khung 15 phút."""
    if not STREAM_FILE.exists() or STREAM_FILE.stat().st_size < 100:
        if SEED_FILE.exists():
            try:
                import shutil
                shutil.copyfile(SEED_FILE, STREAM_FILE)
                SIGNAL_FILE.touch()
            except Exception:
                pass

    if not STREAM_FILE.exists():
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()

    try:
        df = pd.read_csv(STREAM_FILE)
    except Exception:
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()

    if len(df) < 2:
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()

    df["start_time"] = pd.to_datetime(df["start_time"])
    df["bucket_time"] = df["start_time"].dt.floor("15min")
    df["date"] = df["start_time"].dt.date

    all_dates = sorted(df["date"].unique())
    # Tự động lấy ngày mới nhất làm ngày mô phỏng trực tiếp
    current_date = all_dates[-1] if all_dates else datetime.now().date()

    # Quét các ngày đã qua (các ngày nhỏ hơn ngày mô phỏng hiện tại)
    past_days_summary = {}
    past_days_ts = {}
    past_dates = [d for d in all_dates if d < current_date]
    for p_date in past_dates:
        p_df = df[df["date"] == p_date].copy()
        if not p_df.empty:
            p_ts = process_single_date(p_df, p_date, is_live_today=False)
            past_days_ts[p_date] = p_ts
            past_days_summary[p_date] = {
                "total_calls": int(p_ts["calls_total"].sum()),
                "calls_503": int(p_ts["calls_503"].sum()),
                "error_rate": (p_ts["calls_503"].sum() / p_ts["calls_total"].sum() * 100) if p_ts["calls_total"].sum() > 0 else 0,
                "p1_alerts": int(p_ts["is_p1_red"].sum()),
                "p2_warnings": int(p_ts["is_p2_yellow"].sum())
            }

    # Xử lý ngày hiện tại (Realtime)
    df_today = df[df["date"] == current_date].copy() if current_date in all_dates else pd.DataFrame(columns=["call_id", "start_time", "end_time", "duration", "result_code", "bucket_time", "date"])
    if not df_today.empty:
        latest_time = df_today["start_time"].max()
        active_bucket = latest_time.floor("15min")
    else:
        active_bucket = pd.Timestamp(current_date).replace(hour=8, minute=0, second=0)

    ts_today = process_single_date(df_today, current_date, is_live_today=True, active_bucket=active_bucket)
    today_bad_calls = df_today[df_today["result_code"] == "503_CONGESTION"].sort_values("start_time", ascending=False) if not df_today.empty else pd.DataFrame()

    return ts_today, today_bad_calls, current_date, past_days_summary, df_today, past_days_ts, df

# ==============================================================================
# 4. GIAO DIỆN CHÍNH STREAMLIT
# ==============================================================================
col_head_title, col_head_theme = st.columns([3.8, 1.2])
with col_head_title:
    st.markdown(f"<h2 style='color:{text_main}; font-weight:800; margin-bottom:14px; letter-spacing:-0.5px;'>SCC Outbound System : Anomaly Detection Dashboard</h2>", unsafe_allow_html=True)
with col_head_theme:
    st.radio(
        "🌓 Giao diện:",
        ["Sáng ☀️", "Tối 🌙"],
        horizontal=True,
        key="theme_mode"
    )

# TẢI TRẠNG THÁI HIỆN TẠI
init_ts, _, init_cur_date, init_past_summary, _, init_past_days_ts, init_df = get_current_pipeline_state()
init_all_dates = sorted(init_df["date"].unique()) if not init_df.empty else ([init_cur_date] if init_cur_date else [datetime.now().date()])
min_hist_date = init_all_dates[0]
max_hist_date = init_cur_date if init_cur_date else init_all_dates[-1]

# Quản lý Session State cho lịch chọn ngày
if "cal_date_picker" not in st.session_state:
    st.session_state["cal_date_picker"] = max_hist_date

init_picked = st.session_state.get("cal_date_picker", max_hist_date)
if hasattr(init_picked, "date"):
    init_picked = init_picked.date()
is_realtime_mode = (init_picked == max_hist_date)

# ==============================================================================
# 5. KHỐI NỘI DUNG HIỂN THỊ CHÍNH
# ==============================================================================
def render_live_monitoring_fragment():
    """Khối hiển thị chính: tự động cập nhật mượt mà mỗi 3.5s."""
    global is_realtime_mode
    ts_today, today_bad_calls, current_date, past_summary, df_today, past_days_ts, full_df = get_current_pipeline_state()

    if ts_today is None or ts_today.empty:
        st.info("⏳ Đang chờ luồng dữ liệu cuộc gọi trực tiếp từ `producer.py`...")
        return False

    all_dates = sorted(full_df["date"].unique()) if not full_df.empty else [current_date]
    min_date = all_dates[0]
    max_date = current_date if current_date else all_dates[-1]

    past_dates = [d for d in all_dates if d < max_date]
    yesterday_date = past_dates[-1] if past_dates else (max_date - timedelta(days=1))

    # XÁC ĐỊNH NGÀY XEM TỪ LỊCH DUY NHẤT
    picked_date = st.session_state.get("cal_date_picker", max_date)
    if hasattr(picked_date, "date"):
        picked_date = picked_date.date()
    view_date = picked_date
    is_realtime_mode = (view_date == max_date)

    # PHÂN LOẠI CHẾ ĐỘ HIỂN THỊ
    if is_realtime_mode:
        active_ts = ts_today
        view_date = current_date
        completed_buckets = ts_today[ts_today["is_completed"]]
        df_view = df_today
        view_bad_calls = today_bad_calls
        is_today_finished = (len(completed_buckets) >= 38)

        if is_today_finished:
            active_time_str = "17:30 (Đã Chốt Toàn Ngày)"
            is_p1 = False
            is_p2 = False
            latest_row = completed_buckets.iloc[-1]
        elif not completed_buckets.empty:
            latest_row = completed_buckets.iloc[-1]
            active_time_str = latest_row["bucket_time"].strftime("%H:%M")
            is_p1 = bool(latest_row["is_p1_red"])
            is_p2 = bool(latest_row["is_p2_yellow"])
        else:
            active_time_str = "08:00 (Starting)"
            is_p1 = False
            is_p2 = False
            latest_row = ts_today.iloc[0]

        # BANNER CẢNH BÁO TRỰC TIẾP (CHỈ HIỂN THỊ KHI CÓ SỰ CỐ KHẨN CẤP)
        if is_p1:
            if latest_row["is_p1_net"]:
                st.error(
                    f"🚨 **[P1 RED ALERT - LỖI HẠ TẦNG SIP TRUNK TẠI {active_time_str}]** | "
                    f"Tỷ lệ lỗi: `{latest_row['smoothed_error_rate']*100:.1f}%` > Ngưỡng Động: `{latest_row['dynamic_threshold']*100:.1f}%` | "
                    f"Lỗi 503: `{latest_row['calls_503']}/{latest_row['calls_total']} cuộc` | Đề nghị kiểm tra Gateway / SIP Trunk!"
                )
            else:
                st.error(
                    f"🚨 **[P1 RED ALERT - SẬP LƯU LƯỢNG ĐỘT NGỘT TẠI {active_time_str}]** | "
                    f"Lưu lượng: `{latest_row['calls_total']}` cuộc (Kỳ vọng: {latest_row['mu']:.1f}) | Nguy cơ đứt kết nối tổng đài PBX!"
                )
        elif is_p2:
            st.warning(
                f"🟡 **[P2 WARNING - ĐỘT BIẾN TẢI CHIẾN DỊCH TẠI {active_time_str}]** | "
                f"Lưu lượng tăng vọt: `{latest_row['calls_total']}` cuộc (Kỳ vọng: {latest_row['mu']:.1f}) | Chú ý theo dõi dung lượng trunk!"
            )
    else:
        # CHẾ ĐỘ XEM LẠI LỊCH SỬ (HÔM QUA HOẶC CHỌN NGÀY THEO LỊCH)
        is_today_finished = True

        if view_date == current_date:
            active_ts = ts_today
            completed_buckets = ts_today[ts_today["is_completed"]]
            df_view = df_today
            view_bad_calls = today_bad_calls
            latest_row = completed_buckets.iloc[-1] if not completed_buckets.empty else ts_today.iloc[0]
            active_time_str = f"Lịch hôm nay: {latest_row['bucket_time'].strftime('%H:%M') if not completed_buckets.empty else '08:00'}"
            is_p1 = False
            is_p2 = False
        else:
            active_ts = past_days_ts.get(view_date)
            if active_ts is None or active_ts.empty:
                p_df = full_df[full_df["date"] == view_date].copy() if not full_df.empty else pd.DataFrame()
                if not p_df.empty:
                    active_ts = process_single_date(p_df, view_date, is_live_today=False)
                    past_days_ts[view_date] = active_ts

            if active_ts is not None and not active_ts.empty:
                completed_buckets = active_ts
                latest_row = completed_buckets.iloc[-1]
                active_time_str = "17:30 (Đã Chốt Toàn Ngày)"
                is_p1 = False
                is_p2 = False
                df_view = full_df[full_df["date"] == view_date] if not full_df.empty else pd.DataFrame()
                view_bad_calls = df_view[df_view["result_code"] == "503_CONGESTION"].sort_values("start_time", ascending=False) if not df_view.empty else pd.DataFrame()
            else:
                completed_buckets = pd.DataFrame()
                active_time_str = "Không có cuộc gọi"
                is_p1 = False
                is_p2 = False
                df_view = pd.DataFrame()
                view_bad_calls = pd.DataFrame()

    # METRICS KPI (4 THẺ TINH GỌN THEO YÊU CẦU: BỎ TIẾN ĐỘ CA TRỰC, RÚT GỌN TỶ LỆ GIÁN ĐOẠN)
    if completed_buckets is not None and not completed_buckets.empty:
        view_total = int(completed_buckets["calls_total"].sum())
        view_503 = int(completed_buckets["calls_503"].sum())
        view_err_rate = (view_503 / view_total * 100) if view_total > 0 else 0.0
        view_p1_count = int(completed_buckets["is_p1_red"].sum())
        view_p2_count = int(completed_buckets["is_p2_yellow"].sum())
    else:
        view_total = 0
        view_503 = 0
        view_err_rate = 0.0
        view_p1_count = 0
        view_p2_count = 0

    # ==============================================================================
    # MULTI-TAB DISPLAY
    # ==============================================================================
    tab_realtime, tab_ml_seasonality, tab_executive_overview = st.tabs([
        "📊 1. Giám Sát Trực Tiếp (Biểu Đồ & Sự Cố)",
        "📈 2. Phân Tích Xu Hướng & Cảnh Báo Sớm",
        "📋 3. Báo Cáo Tổng Hợp Đa Ngày"
    ])
    # Chèn công cụ hỗ trợ chuyển tab tự động qua URL (?tab=1|2|3), phím tắt 1, 2, 3 và tối ưu lịch
    import streamlit.components.v1 as components
    components.html(f"""
    <script>
    (function() {{
        const pDoc = window.parent.document;
        const pWin = window.parent;
        const todayStr = "{current_date.strftime('%Y-%m-%d')}";
        const yestStr = "{yesterday_date.strftime('%Y-%m-%d')}";
        const todayDay = "{current_date.day}";
        const yestDay = "{yesterday_date.day}";

        function isLightRgb(rgbStr) {{
            if (!rgbStr || rgbStr === 'transparent' || rgbStr.startsWith('rgba(0, 0, 0, 0)')) return false;
            const m = rgbStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (!m) return false;
            const r = parseInt(m[1]), g = parseInt(m[2]), b = parseInt(m[3]);
            return (r >= 210 && g >= 210 && b >= 210);
        }}

        // 1. Tự động chuyển tab theo URL query parameter (?tab=1, ?tab=2, ?tab=3)
        let tabFromUrlSwitched = false;
        function checkAndSwitchUrlTab() {{
            if (tabFromUrlSwitched) return;
            try {{
                const searchParams = new URLSearchParams(pWin.location.search);
                const tabParam = searchParams.get('tab');
                if (tabParam && ['1', '2', '3'].includes(tabParam)) {{
                    const tabs = pDoc.querySelectorAll('button[role="tab"]');
                    const targetIdx = parseInt(tabParam) - 1;
                    if (tabs && tabs.length >= 3 && tabs[targetIdx]) {{
                        if (tabs[targetIdx].getAttribute('aria-selected') !== 'true') {{
                            tabs[targetIdx].click();
                        }}
                        tabFromUrlSwitched = true;
                    }}
                }}
            }} catch(e) {{}}
        }}

        // 2. Phím tắt bàn phím 1, 2, 3 để chuyển nhanh tab ngay trên Dashboard
        if (!pWin.__scc_tab_keyboard_registered) {{
            pWin.__scc_tab_keyboard_registered = true;
            pDoc.addEventListener('keydown', function(e) {{
                const tag = (e.target.tagName || '').toLowerCase();
                if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
                if (e.ctrlKey || e.altKey || e.metaKey) return;

                const tabs = pDoc.querySelectorAll('button[role="tab"]');
                if (!tabs || tabs.length < 3) return;

                let targetIdx = -1;
                if (e.key === '1') targetIdx = 0;
                else if (e.key === '2') targetIdx = 1;
                else if (e.key === '3') targetIdx = 2;

                if (targetIdx >= 0 && tabs[targetIdx]) {{
                    tabs[targetIdx].click();
                    try {{
                        const curUrl = new URL(pWin.location.href);
                        curUrl.searchParams.set('tab', targetIdx + 1);
                        pWin.history.replaceState(null, '', curUrl.toString());
                    }} catch(err) {{}}
                }}
            }});
        }}

        if (!pWin.__scc_popstate_registered) {{
            pWin.__scc_popstate_registered = true;
            pWin.addEventListener('popstate', function() {{
                tabFromUrlSwitched = false;
                checkAndSwitchUrlTab();
            }});
        }}

        function fixCalendarDarkAndFooter() {{
            const activeTab = pDoc.querySelector('button[role="tab"][aria-selected="true"]');
            const isTab1 = activeTab && (activeTab.innerText.includes("Giám Sát") || activeTab.innerText.includes("1."));

            const popovers = pDoc.querySelectorAll('div[data-baseweb="popover"]');
            popovers.forEach(popover => {{
                const cal = popover.querySelector('div[data-baseweb="calendar"]');
                if (!cal) return;

                const existingFooter = popover.querySelector('.custom-cal-footer');
                // 1. Quản lý footer: Tab 1 có Hôm nay/Hôm qua, Tab 3 có nút Tổng Hợp
                if (!isTab1) {{
                    if (existingFooter && !existingFooter.dataset.tab3) {{
                        existingFooter.remove();
                    }}
                    if (!popover.querySelector('.custom-cal-footer[data-tab3="true"]')) {{
                        const footer = pDoc.createElement('div');
                        footer.className = 'custom-cal-footer';
                        footer.dataset.tab3 = 'true';
                        footer.style.cssText = 'display:flex;gap:8px;padding:8px 12px;border-top:1px solid {border_col};background:{card_bg};border-radius:0 0 10px 10px;margin-top:4px;';

                        const btnAll = pDoc.createElement('button');
                        btnAll.innerText = '📊 Tổng Hợp';
                        btnAll.style.cssText = 'flex:1;padding:7px 12px;font-size:12.5px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;';
                        btnAll.onclick = (e) => {{
                            e.stopPropagation();
                            const hiddenBtn = pDoc.querySelector('div[data-testid="stButton"] button');
                            if (hiddenBtn) {{
                                hiddenBtn.click();
                                return;
                            }}
                        }};
                        footer.appendChild(btnAll);
                        cal.appendChild(footer);
                    }}
                }} else {{
                    if (existingFooter && existingFooter.dataset.tab3) {{
                        existingFooter.remove();
                    }}
                    if (!popover.querySelector('.custom-cal-footer:not([data-tab3="true"])')) {{
                        const footer = pDoc.createElement('div');
                        footer.className = 'custom-cal-footer';
                        footer.style.cssText = 'display:flex;gap:8px;padding:8px 12px;border-top:1px solid {border_col};background:{card_bg};border-radius:0 0 10px 10px;margin-top:4px;';

                        const btnToday = pDoc.createElement('button');
                        btnToday.innerText = '⚡ Hôm nay (Today)';
                        btnToday.style.cssText = 'flex:1;padding:6px 10px;font-size:12px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;';
                        btnToday.onclick = (e) => {{
                            e.stopPropagation();
                            const cells = cal.querySelectorAll('div[role="gridcell"]');
                            for (let cell of cells) {{
                                if (cell.innerText.trim() === todayDay && !cell.getAttribute('aria-disabled')) {{
                                    cell.click();
                                    return;
                                }}
                            }}
                            const inp = pDoc.querySelector('div[data-testid="stDateInput"] input');
                            if (inp) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                setter.call(inp, todayStr);
                                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }};

                        const btnYest = pDoc.createElement('button');
                        btnYest.innerText = '⏮️ Hôm qua (Yesterday)';
                        btnYest.style.cssText = 'flex:1;padding:6px 10px;font-size:12px;font-weight:600;background:{tab_active_bg};color:{text_main};border:1px solid {border_col};border-radius:6px;cursor:pointer;';
                        btnYest.onclick = (e) => {{
                            e.stopPropagation();
                            const cells = cal.querySelectorAll('div[role="gridcell"]');
                            for (let cell of cells) {{
                                if (cell.innerText.trim() === yestDay && !cell.getAttribute('aria-disabled')) {{
                                    cell.click();
                                    return;
                                }}
                            }}
                            const inp = pDoc.querySelector('div[data-testid="stDateInput"] input');
                            if (inp) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                setter.call(inp, yestStr);
                                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }};

                        footer.appendChild(btnToday);
                        footer.appendChild(btnYest);
                        cal.appendChild(footer);
                    }}
                }}

                // 2. Sửa lỗi màu nền dải range trắng trong Dark Mode
                if ({str(is_dark).lower()}) {{
                    const allDescendants = cal.querySelectorAll('*');
                    allDescendants.forEach(el => {{
                        const bg = window.getComputedStyle(el).backgroundColor;
                        if (isLightRgb(bg)) {{
                            el.style.setProperty('background-color', 'rgba(2, 132, 199, 0.35)', 'important');
                            el.style.setProperty('color', '#ffffff', 'important');
                        }}
                    }});
                }}
            }});
        }}

        setInterval(function() {{
            checkAndSwitchUrlTab();
            fixCalendarDarkAndFooter();
        }}, 120);
    }})();
    </script>
    """, height=0, width=0)


    # ---------------- TAB 1: OPERATIONAL MONITORING ----------------
    with tab_realtime:
        # 4 THẺ KPI CHỈ HIỂN THỊ TRONG TAB 1 THEO YÊU CẦU
        kpi_cards = [
            ("Tổng Số Cuộc Gọi Trong Ngày", f"{view_total:,} cuộc", f"Ngày {view_date.strftime('%Y-%m-%d')} ({active_time_str})", text_muted),
            ("Tỷ Lệ Gián Đoạn", f"{view_err_rate:.2f}%", f"{view_503} cuộc lỗi" if view_total > 0 else "0 cuộc lỗi", "#ef4444" if view_err_rate > 5 else text_muted),
            ("🔴 Sự Cố Khẩn Cấp", f"{view_p1_count} khung giờ", "Cần can thiệp ngay" if view_p1_count > 0 else "Hạ tầng an toàn", "#ef4444" if view_p1_count > 0 else "#10b981"),
            ("🟡 Tăng Tải Đột Biến", f"{view_p2_count} khung giờ", "Cần chú ý nhân sự" if view_p2_count > 0 else "Lưu lượng ổn định", "#f59e0b" if view_p2_count > 0 else "#10b981")
        ]
        k_cols = st.columns(4)
        for col, (title, val, sub, sub_col) in zip(k_cols, kpi_cards):
            col.markdown(f"""
            <div style="background:{card_bg};border:1px solid {border_col};border-radius:8px;padding:14px 16px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
              <div style="font-size:12.5px;font-weight:600;color:{text_muted};margin-bottom:4px;">{title}</div>
              <div style="font-size:24px;font-weight:700;color:{text_main};line-height:1.2;margin-bottom:4px;">{val}</div>
              <div style="font-size:11.5px;color:{sub_col};font-weight:500;">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

        # BỘ LỌC LỊCH CHỌN NGÀY DUY NHẤT (TÍCH HỢP HÔM NAY / HÔM QUA TRỰC TIẾP TRONG LỊCH)
        col_date, _ = st.columns([1.1, 2.9])
        with col_date:
            cur_cal_val = st.session_state.get("cal_date_picker", max_date)
            if hasattr(cur_cal_val, "date"):
                cur_cal_val = cur_cal_val.date()
            if cur_cal_val < min_date or cur_cal_val > max_date:
                cur_cal_val = max_date
            st.date_input(
                "📅 Chọn ngày theo Lịch:",
                value=cur_cal_val,
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD",
                key="cal_date_picker",
                help="Bấm vào để mở lịch. Trong lịch có nút Hôm nay và Hôm qua để chọn nhanh."
            )


        # ==============================================================================
        # 1. BIỂU ĐỒ LƯU LƯỢNG CUỘC GỌI & BẤT THƯỜNG THỂ TÍCH (CHART 1)
        # ==============================================================================
        fig_traffic = go.Figure()

        # Dải hoạt động thông thường (Upper & Lower)
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["upper_limit"].tolist(),
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["lower_limit"].tolist(),
            mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(148, 163, 184, 0.22)",
            name="Vùng hoạt động bình thường",
            hoverinfo="skip"
        ))

        # Đường mức kỳ vọng trung bình mu(t)
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["mu"].tolist(),
            mode="lines", line=dict(color="#64748b", width=1.5, dash="dash"),
            name="Mức kỳ vọng trung bình",
            hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Mức kỳ vọng:</b> %{y:.1f} cuộc<extra></extra>"
        ))

        # Đường cuộc gọi thực tế (Luôn có trong chú thích)
        x_actual = completed_buckets["bucket_time"].tolist() if not completed_buckets.empty else []
        y_actual = completed_buckets["calls_total"].tolist() if not completed_buckets.empty else []
        fig_traffic.add_trace(go.Scatter(
            x=x_actual, y=y_actual,
            mode="lines+markers",
            line=dict(color="#0284c7", width=2.5),
            marker=dict(size=6, color="#0369a1"),
            name="Cuộc gọi thực tế",
            hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Thực tế:</b> %{y} cuộc<extra></extra>",
            showlegend=True
        ))

        # Điểm sự cố khẩn cấp P1 (Bao gồm cả sập tín hiệu tổng đài và nghẽn mạng viễn thông)
        p1_incidents = completed_buckets[completed_buckets["is_p1_red"]].copy() if not completed_buckets.empty else pd.DataFrame()
        if not p1_incidents.empty:
            x_drop = p1_incidents["bucket_time"].tolist()
            y_drop = p1_incidents["calls_total"].tolist()
            desc_drop = [
                f"Sập tín hiệu tổng đài ({int(r['calls_total'])} cuộc, kỳ vọng: {r['mu']:.1f})" if r.get("is_p1_drop", False)
                else f"Nghẽn mạng viễn thông ({int(r['calls_503'])}/{int(r['calls_total'])} lỗi 503 - {r['error_rate']*100:.1f}%)"
                for _, r in p1_incidents.iterrows()
            ]
        else:
            x_drop, y_drop, desc_drop = [], [], []

        fig_traffic.add_trace(go.Scatter(
            x=x_drop if x_drop else [None],
            y=y_drop if y_drop else [None],
            mode="markers",
            marker=dict(color="#dc2626", size=13, symbol="circle", line=dict(color="#ffffff", width=2)),
            name="Sự cố khẩn cấp (🔴)",
            text=desc_drop if desc_drop else [""],
            hovertemplate="<b>🔴 SỰ CỐ KHẨN CẤP!</b><br><b>Chi tiết:</b> %{text}<br><b>Khung:</b> %{x|%H:%M}<br><b>Số cuộc:</b> %{y}<extra></extra>",
            showlegend=True
        ))

        # Điểm lưu lượng tăng đột biến (P2 Spike - Luôn có trong chú thích)
        p2_spike = completed_buckets[completed_buckets["is_p2_yellow"]] if not completed_buckets.empty else pd.DataFrame()
        x_spike = p2_spike["bucket_time"].tolist() if not p2_spike.empty else []
        y_spike = p2_spike["calls_total"].tolist() if not p2_spike.empty else []
        fig_traffic.add_trace(go.Scatter(
            x=x_spike if x_spike else [None],
            y=y_spike if y_spike else [None],
            mode="markers",
            marker=dict(color="#d97706", size=13, symbol="diamond", line=dict(color="#ffffff", width=2)),
            name="Lưu lượng tăng đột biến (🟡)",
            hovertemplate="<b>🟡 CẢNH BÁO: Tăng tải đột biến!</b><br><b>Khung:</b> %{x|%H:%M}<br><b>Số cuộc:</b> %{y}<extra></extra>",
            showlegend=True
        ))

        max_calls_val = max(12, int(active_ts["upper_limit"].max()) + 2)
        if not completed_buckets.empty and completed_buckets["calls_total"].max() > max_calls_val - 2:
            max_calls_val = int(completed_buckets["calls_total"].max()) + 2

        fig_traffic.update_layout(
            template=plotly_template,
            paper_bgcolor=card_bg,
            plot_bgcolor=card_bg,
            height=340,
            margin=dict(l=50, r=20, t=30, b=30),
            hovermode="x unified",
            hoverlabel=dict(bgcolor=card_bg, font_size=12, font_color=text_main, bordercolor=border_col),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=11, color=text_main),
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(0,0,0,0)"
            ),
            yaxis=dict(
                title="Cuộc gọi / 15 phút",
                range=[-0.8, max_calls_val],
                gridcolor=plotly_grid,
                linecolor=plotly_line,
                tickfont=dict(color=text_muted),
                title_font=dict(color=text_main)
            ),
            xaxis=dict(
                tickformat="%H:%M",
                dtick=1800000,
                gridcolor=plotly_grid,
                linecolor=plotly_line,
                tickfont=dict(color=text_muted)
            )
        )

        # ==============================================================================
        # 2. BIỂU ĐỒ TỶ LỆ GIÁN ĐOẠN & NGƯỠNG AN TOÀN TỰ CO GIÃN (CHART 2)
        # ==============================================================================
        fig_error = go.Figure()

        # Đường tỷ lệ gián đoạn thực tế (Luôn có trong chú thích)
        x_err = completed_buckets["bucket_time"].tolist() if not completed_buckets.empty else []
        y_err = (completed_buckets["error_rate"] * 100).round(2).tolist() if not completed_buckets.empty else []
        fig_error.add_trace(go.Scatter(
            x=x_err, y=y_err,
            mode="lines+markers",
            line=dict(color="#ea580c", width=2.5),
            marker=dict(size=6, color="#c2410c"),
            name="Tỷ lệ gián đoạn (%)",
            hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Tỷ lệ lỗi:</b> %{y:.1f}%<extra></extra>",
            showlegend=True
        ))

        # Ngưỡng an toàn tự co giãn (Luôn có trong chú thích)
        if not completed_buckets.empty:
            thresh_x = completed_buckets["bucket_time"].tolist()
            thresh_y = (completed_buckets["dynamic_threshold"] * 100).round(2).tolist()
        else:
            thresh_x = active_ts["bucket_time"].tolist()
            thresh_y = [compute_dynamic_error_threshold(int(m)) * 100 for m in active_ts["mu"]]

        fig_error.add_trace(go.Scatter(
            x=thresh_x, y=thresh_y,
            mode="lines",
            line=dict(color="#dc2626", width=2, dash="dash"),
            name="Ngưỡng an toàn tự co giãn (%)",
            hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Ngưỡng an toàn:</b> %{y:.1f}%<extra></extra>",
            showlegend=True
        ))

        # Điểm sự cố gián đoạn vượt ngưỡng (P1 Outage - Luôn có trong chú thích)
        p1_err = completed_buckets[completed_buckets["is_p1_net"]] if not completed_buckets.empty else pd.DataFrame()
        x_p1_err = p1_err["bucket_time"].tolist() if not p1_err.empty else []
        y_p1_err = (p1_err["error_rate"] * 100).round(2).tolist() if not p1_err.empty else []
        fig_error.add_trace(go.Scatter(
            x=x_p1_err if x_p1_err else [None],
            y=y_p1_err if y_p1_err else [None],
            mode="markers",
            marker=dict(color="#dc2626", size=14, symbol="x", line=dict(color="#ffffff", width=2)),
            name="Sự cố gián đoạn vượt ngưỡng (🚨)",
            hovertemplate="<b>🚨 SỰ CỐ KHẨN CẤP: Vượt ngưỡng an toàn!</b><br><b>Khung:</b> %{x|%H:%M}<br><b>Tỷ lệ lỗi:</b> %{y:.1f}%<extra></extra>",
            showlegend=True
        ))

        # Tự động co giãn trục tung Y để không bao giờ bị cắt điểm lỗi (kể cả khi lỗi vọt lên 100%)
        max_err_display = 60.0
        if not completed_buckets.empty:
            peak_err = float(completed_buckets["error_rate"].max() * 100)
            if peak_err > 50.0:
                max_err_display = min(110.0, peak_err + 10.0)

        fig_error.update_layout(
            template=plotly_template,
            paper_bgcolor=card_bg,
            plot_bgcolor=card_bg,
            height=340,
            margin=dict(l=50, r=20, t=30, b=30),
            hovermode="x unified",
            hoverlabel=dict(bgcolor=card_bg, font_size=12, font_color=text_main, bordercolor=border_col),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=11, color=text_main),
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(0,0,0,0)"
            ),
            yaxis=dict(
                title="Tỷ lệ gián đoạn (%)",
                range=[-2.0, max_err_display],
                gridcolor=plotly_grid,
                linecolor=plotly_line,
                tickfont=dict(color=text_muted),
                title_font=dict(color=text_main)
            ),
            xaxis=dict(
                tickformat="%H:%M",
                dtick=1800000,
                gridcolor=plotly_grid,
                linecolor=plotly_line,
                tickfont=dict(color=text_muted)
            )
        )

        # HIỂN THỊ THEO BỐ CỤC ĐÃ CHỌN (TÁCH TIÊU ĐỀ RA NGOÀI ĐỂ KHÔNG BAO GIỜ BỊ ĐÈ CHÚ THÍCH KHI XẾP NGANG)
        title_c1 = f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>1. Lưu Lượng Cuộc Gọi Phát Sinh So Với Mức Kỳ Vọng Thông Thường</div>"
        title_c2 = f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>2. Tỷ Lệ Cuộc Gọi Bị Gián Đoạn So Với Ngưỡng An Toàn Tự Co Giãn</div>"

        # BỐ CỤC CỐ ĐỊNH XẾP NGANG (2 CỘT SONG SONG) THEO YÊU CẦU
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown(title_c1, unsafe_allow_html=True)
            st.plotly_chart(fig_traffic, use_container_width=True)
        with col_chart2:
            st.markdown(title_c2, unsafe_allow_html=True)
            st.plotly_chart(fig_error, use_container_width=True)

        st.markdown("---")

        # BẢNG TỔNG HỢP SỰ CỐ VẬN HÀNH (ĐẶT LÊN TRÊN ẢNH TỔNG KẾT THEO YÊU CẦU)
        st.subheader(f"⚠️ Nhật Ký Sự Cố Vận Hành Cần Xử Lý — Ngày: {view_date.strftime('%Y-%m-%d')}")
        flagged = completed_buckets[completed_buckets["is_p1_red"] | completed_buckets["is_p2_yellow"]].copy()

        if not flagged.empty:
            def format_incident_desc(row):
                items = []
                if row["is_p1_net"]:
                    items.append("Nghẽn mạng viễn thông (Không kết nối được)")
                if row["is_p1_drop"]:
                    items.append("Sập tín hiệu tổng đài (Cuộc gọi giảm sâu)")
                if row["is_p2_yellow"]:
                    items.append("Lưu lượng tăng đột biến (Cần thêm nhân sự)")
                return " | ".join(items)

            def get_action_recommendation(row):
                if row["is_p1_net"]:
                    return "Kiểm tra cổng kết nối nhà mạng và chuyển hướng sang đường truyền dự phòng"
                elif row["is_p1_drop"]:
                    return "Kiểm tra nguồn phát tổng đài và đường dây trung kế"
                elif row["is_p2_yellow"]:
                    return "Điều phối thêm điện thoại viên trực ca, theo dõi tải kênh gọi"
                return "Theo dõi định kỳ"

            def get_risk_level(row):
                if row["is_p1_red"]:
                    return "🔴 Khẩn cấp"
                elif row["is_p2_yellow"]:
                    return "🟡 Cảnh báo"
                return "🟢 Bình thường"

            flagged["Hiện Tượng"] = flagged.apply(format_incident_desc, axis=1)
            flagged["Mức Độ"] = flagged.apply(get_risk_level, axis=1)
            flagged["Hướng Dẫn Xử Lý"] = flagged.apply(get_action_recommendation, axis=1)

            display_df = pd.DataFrame()
            display_df["Khung Giờ"] = flagged["bucket_time"].dt.strftime("%H:%M")
            display_df["Mức Độ"] = flagged["Mức Độ"]
            display_df["Hiện Tượng Gặp Phải"] = flagged["Hiện Tượng"]
            display_df["Tổng Số Cuộc"] = flagged["calls_total"].astype(int)
            display_df["Số Cuộc Lỗi"] = flagged["calls_503"].astype(int)
            display_df["Tỷ Lệ Bị Lỗi"] = (flagged["error_rate"] * 100).round(1).astype(str) + "%"
            display_df["Ngưỡng Cho Phép"] = (flagged["dynamic_threshold"] * 100).round(1).astype(str) + "%"
            display_df["Hướng Dẫn Xử Lý Nhanh"] = flagged["Hướng Dẫn Xử Lý"]

            n_red = int(flagged["is_p1_red"].sum())
            n_yellow = int(flagged["is_p2_yellow"].sum())
            if n_red > 0:
                st.error(f"🚨 **Phát hiện {len(flagged)} khung giờ có sự cố:** Có {n_red} sự cố khẩn cấp (🔴) và {n_yellow} cảnh báo lưu lượng (🟡). Đề nghị kỹ sư xử lý theo hướng dẫn bên dưới.")
            else:
                st.warning(f"🟡 **Ghi nhận {len(flagged)} khung giờ có biến động lưu lượng:** Đề nghị điều phối nhân sự trực ca phù hợp.")

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Toàn bộ các khung giờ trong ngày hoạt động ổn định, không phát sinh sự cố gián đoạn nào.")

        # DANH SÁCH CUỘC GỌI LỖI THU GỌN VÀO EXPANDER
        with st.expander("🔍 Tra cứu chi tiết từng mã cuộc gọi bị gián đoạn (Dành cho kỹ thuật viên)", expanded=False):
            if not view_bad_calls.empty:
                st.caption(f"Danh sách {min(20, len(view_bad_calls))} cuộc gọi bị lỗi gần nhất:")
                bad_display = view_bad_calls[["call_id", "start_time", "end_time", "duration"]].copy()
                bad_display.columns = ["Mã Cuộc Gọi", "Thời Gian Bắt Đầu", "Thời Gian Kết Thúc", "Thời Lượng (Giây)"]
                st.dataframe(
                    bad_display.head(20),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("✅ Không có cuộc gọi lỗi nào.")

        st.markdown("---")

        # NẾU Ở CHẾ ĐỘ XEM LẠI QUÁ KHỨ HOẶC NGÀY ĐÃ HOÀN TẤT: TRA CỨU & TẢI ẢNH BÁO CÁO TELEGRAM (ẨN TRONG EXPANDER ĐỂ KHÔNG BỊ TRÙNG BIỂU ĐỒ)
        if (not is_realtime_mode) or is_today_finished:
            report_img = DATA_DIR / f"daily_report_{view_date.strftime('%Y-%m-%d')}.png"
            if not report_img.exists() and not completed_buckets.empty:
                generate_daily_report_chart(view_date, completed_buckets, report_img)

            if report_img.exists():
                with st.expander(f"🖼️ Xem & Tải Ảnh Báo Cáo Tổng Kết Ngày Gửi Telegram ({view_date.strftime('%Y-%m-%d')})", expanded=False):
                    col_img, col_info = st.columns([2.5, 1])
                    with col_img:
                        st.image(str(report_img), caption=f"Ảnh báo cáo tổng kết ngày {view_date.strftime('%Y-%m-%d')}", use_column_width=True)
                    with col_info:
                        st.markdown("#### 📥 Tải Báo Cáo PNG")
                        st.caption("Ảnh báo cáo chất lượng cao đã được tự động lưu trữ và gửi tới nhóm NOC Telegram.")
                        with open(report_img, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Tải File Ảnh ({report_img.name})",
                                data=f.read(),
                                file_name=report_img.name,
                                mime="image/png",
                                use_container_width=True
                            )
            st.markdown("---")

    # ---------------- TAB 2: PHÂN TÍCH CHU KỲ & DỰ BÁO RỦI RO ----------------
    with tab_ml_seasonality:
        st.subheader("Phân Tích Chu Kỳ & Dự Báo Rủi Ro Vận Hành")

        # Tính toán động từ toàn bộ dữ liệu lịch sử các ngày đã qua + các khung giờ đã chốt hôm nay
        completed_today_slice = completed_buckets if is_realtime_mode else None
        dyn_hourly_stats, tot_hist_days, tot_hist_buckets = compute_dynamic_seasonality_and_risk(
            past_days_ts, completed_today_slice
        )

        # 4 THẺ KPI TRỌNG TÂM CỦA TAB 2 GIÚP NGƯỜI XEM DỄ TIẾP CẬN VÀ HIỂU SỐ LIỆU BIỂU ĐỒ
        work_hours = list(range(8, 18))
        max_risk_h = max(work_hours, key=lambda h: dyn_hourly_stats.get(h, {}).get("risk_pct", 0.0))
        max_risk_val = dyn_hourly_stats.get(max_risk_h, {}).get("risk_pct", 0.0)

        peak_traffic_h = max(work_hours, key=lambda h: dyn_hourly_stats.get(h, {}).get("mean_15m", 0.0))
        peak_traffic_val = dyn_hourly_stats.get(peak_traffic_h, {}).get("mean_15m", 0.0)

        # Sắp xếp các giờ có nguy cơ quá tải (>=30%) theo xác suất giảm dần và chỉ lấy 2 khung giờ có khả năng nhất
        risky_hours = [h for h in work_hours if dyn_hourly_stats.get(h, {}).get("risk_pct", 0.0) >= 30.0]
        risky_sorted = sorted(risky_hours, key=lambda h: dyn_hourly_stats.get(h, {}).get("risk_pct", 0.0), reverse=True)
        top2_warn_hours = risky_sorted[:2]
        top2_warn_display = sorted(top2_warn_hours)
        warn_str = ", ".join(f"{h}h" for h in top2_warn_display) if top2_warn_display else "An Toàn"
        if top2_warn_display:
            risks_info = ", ".join(f"{dyn_hourly_stats.get(h, {}).get('risk_pct', 0.0):.0f}%" for h in top2_warn_display)
            warn_sub = f"Top 2 khung giờ nguy cơ cao nhất ({risks_info})"
        else:
            warn_sub = "Hạ tầng an toàn (Không quá tải)"

        if completed_buckets is not None and not completed_buckets.empty:
            p1_today = int(completed_buckets["is_p1_red"].sum())
            p2_today = int(completed_buckets["is_p2_yellow"].sum())
            if p1_today > 0:
                stab_val = "Phát Sinh Sự Cố"
                stab_sub = f"Ghi nhận {p1_today} khung vượt ngưỡng an toàn ngày thường"
                stab_col = "#ef4444"
            elif p2_today > 0:
                stab_val = "Tăng Tải Đột Biến"
                stab_sub = f"Ghi nhận {p2_today} khung giờ gọi cao hơn ngày thường"
                stab_col = "#f59e0b"
            else:
                stab_val = "Bình Thường (Đúng Dự Kiến)"
                stab_sub = "Cuộc gọi bám sát mức trung bình lịch sử 12 ngày"
                stab_col = "#10b981"
        else:
            stab_val = "Chuẩn Bị Ca Trực"
            stab_sub = "Đang chờ dữ liệu thực tế hôm nay"
            stab_col = text_muted

        kpi_tab2_cards = [
            ("Khung Giờ Rủi Ro Cao Nhất", f"{max_risk_h:02d}:00 - {max_risk_h+1:02d}:00", f"Xác suất rủi ro: {max_risk_val:.0f}% (Đỉnh nghẽn SIP)", "#ef4444"),
            ("Đỉnh Lưu Lượng Kỳ Vọng", f"{peak_traffic_h:02d}:00 (~{peak_traffic_val:.1f} cuộc)", "Khung giờ tập trung tải gọi ra lớn nhất", "#38bdf8"),
            ("Các Giờ Dễ Nghẽn Mạng", warn_str, warn_sub, "#f59e0b" if top2_warn_hours else "#10b981"),
            ("Lưu Lượng So Với Ngày Thường", stab_val, stab_sub, stab_col)
        ]

        t2_cols = st.columns(4)
        for col, (title, val, sub, sub_col) in zip(t2_cols, kpi_tab2_cards):
            col.markdown(f"""
            <div style="background:{card_bg};border:1px solid {border_col};border-radius:8px;padding:14px 16px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
              <div style="font-size:12.5px;font-weight:600;color:{text_muted};margin-bottom:4px;">{title}</div>
              <div style="font-size:22px;font-weight:700;color:{text_main};line-height:1.2;margin-bottom:4px;">{val}</div>
              <div style="font-size:11.5px;color:{sub_col};font-weight:500;">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

        col_ml1, col_ml2 = st.columns(2)

        with col_ml1:
            st.markdown("#### 1. Chu Kỳ Lịch Sử 24h & Dữ Liệu Thực Tế")
            st.caption(f"Mức gọi trung bình thông thường trong ngày và dải giới hạn an toàn (tổng hợp tự động từ {tot_hist_days} ngày vận hành gần nhất).")
            hours = list(range(24))
            base_means = [dyn_hourly_stats[h]["mean_15m"] for h in hours]
            base_sds = [dyn_hourly_stats[h]["sd_15m"] for h in hours]
            upper_3sd = [m + 2.5 * s for m, s in zip(base_means, base_sds)]
            lower_3sd = [max(0.0, m - 2.5 * s) for m, s in zip(base_means, base_sds)]

            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(x=hours, y=upper_3sd, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig_s.add_trace(go.Scatter(
                x=hours, y=lower_3sd, mode="lines", line=dict(width=0),
                fill="tonexty", fillcolor="rgba(56, 189, 248, 0.15)",
                name="Dải biến động an toàn"
            ))
            fig_s.add_trace(go.Scatter(
                x=hours, y=base_means, mode="lines+markers",
                line=dict(color="#38bdf8", width=2.5),
                name="Kỳ vọng trung bình"
            ))
            if not completed_buckets.empty:
                fig_s.add_trace(go.Scatter(
                    x=completed_buckets["hour"], y=completed_buckets["calls_total"],
                    mode="markers", marker=dict(size=8, color="#10b981"),
                    name="Thực tế hôm nay"
                ))
            fig_s.update_layout(
                template=plotly_template, height=350,
                paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                margin=dict(l=30, r=20, t=30, b=30),
                xaxis=dict(title="Giờ trong ngày", dtick=2, gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                yaxis=dict(title="Cuộc gọi / 15 phút", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center", font=dict(color=text_main))
            )
            st.plotly_chart(fig_s, use_container_width=True)

        with col_ml2:
            st.markdown("#### 2. Dự Báo Nguy Cơ Rủi Ro Theo Giờ")
            st.caption("Xác suất từng khung giờ có thể phát sinh sự cố hoặc quá tải (giúp ca trực chủ động bố trí nhân sự và kiểm soát đường truyền trước).")

            risk_probs = [dyn_hourly_stats[h]["risk_pct"] for h in hours]
            colors = ["#dc2626" if r >= 60 else ("#f59e0b" if r >= 30 else "#10b981") for r in risk_probs]

            fig_risk = go.Figure()
            fig_risk.add_trace(go.Bar(
                x=hours, y=risk_probs,
                marker=dict(color=colors),
                text=[f"{v:.0f}%" if v > 0 and 8 <= h <= 17 else "" for h, v in enumerate(risk_probs)],
                textposition="outside",
                name="Xác suất sự cố (%)"
            ))
            fig_risk.add_shape(
                type="line", x0=0, x1=23, y0=60, y1=60,
                line=dict(color="#dc2626", dash="dash", width=1.5)
            )
            fig_risk.add_shape(
                type="line", x0=0, x1=23, y0=30, y1=30,
                line=dict(color="#f59e0b", dash="dot", width=1.5)
            )
            fig_risk.update_layout(
                template=plotly_template, height=350,
                paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                margin=dict(l=30, r=20, t=30, b=30),
                yaxis=dict(range=[0, 110], title="Xác suất (%)", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                xaxis=dict(title="Giờ trong ngày", dtick=2, gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                showlegend=False
            )
            st.plotly_chart(fig_risk, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 3. Bảng Phân Tích Chi Tiết Chu Kỳ & Khuyến Nghị Ca Trực")
        table_rows = []
        for h in range(8, 18):
            st_h = dyn_hourly_stats.get(h, {})
            m = st_h.get("mean_15m", 2.0)
            s = st_h.get("sd_15m", 0.8)
            inc_days = st_h.get("day_incidents", 0)
            tot_d = st_h.get("tot_days", tot_hist_days)
            p1 = st_h.get("p1_count", 0)
            p2 = st_h.get("p2_count", 0)
            risk = st_h.get("risk_pct", 0.0)

            if risk >= 60:
                level = "🔴 Nguy cơ cao"
                rec = "Sẵn sàng kích hoạt trunk dự phòng, kiểm soát tốc độ auto-dialer"
            elif risk >= 30:
                level = "🟡 Cần chú ý"
                rec = "Theo dõi chặt dung lượng trunk và tỷ lệ lỗi Gateway"
            else:
                level = "🟢 Bình thường"
                rec = "Vận hành ổn định theo kịch bản tiêu chuẩn"

            table_rows.append({
                "Khung Giờ": f"{h:02d}:00 - {h:02d}:59",
                "Lưu Lượng Kỳ Vọng (μ)": f"{m:.1f} cuộc / 15p",
                "Độ Biến Động (σ)": f"±{s:.1f}",
                "Lịch Sử Sự Cố": f"{inc_days}/{tot_d} ngày ({p1} P1, {p2} P2)",
                "Xác Suất Rủi Ro": f"{risk:.1f}%",
                "Mức Độ Cảnh Báo": level,
                "Khuyến Nghị Ca Trực": rec
            })

        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        # ---------------- TAB 3: EXECUTIVE OVERVIEW & MULTI-DAY ANALYTICS ----------------
        with tab_executive_overview:
            all_dates = sorted(full_df["date"].unique()) if not full_df.empty else []

            st.markdown("### 📊 Báo Cáo Tổng Hợp Vận Hành (Executive Operational Summary)")

            # BỘ LỌC KHOẢNG NGÀY THEO LỊCH (TÍCH HỢP NÚT TỔNG HỢP TRỰC TIẾP TRONG LỊCH)
            col_t3_date, _ = st.columns([1.4, 2.6])
            with col_t3_date:
                t3_range_default = (min_date, max_date)
                raw_session_t3 = st.session_state.get("t3_date_range_picker", t3_range_default)

                def get_work_week(day_obj):
                    if hasattr(day_obj, "date"): day_obj = day_obj.date()
                    mon = day_obj - timedelta(days=day_obj.weekday())
                    fri = mon + timedelta(days=4)
                    return max(min_date, mon), min(max_date, fri)

                if isinstance(raw_session_t3, (list, tuple)):
                    if len(raw_session_t3) == 1:
                        s_d, e_d = get_work_week(raw_session_t3[0])
                        st.session_state["t3_date_range_picker"] = (s_d, e_d)
                        t3_val = (s_d, e_d)
                    elif len(raw_session_t3) == 2:
                        v_start, v_end = raw_session_t3[0], raw_session_t3[1]
                        if hasattr(v_start, "date"): v_start = v_start.date()
                        if hasattr(v_end, "date"): v_end = v_end.date()
                        if v_start > v_end: v_start, v_end = v_end, v_start
                        if v_start < min_date: v_start = min_date
                        if v_end > max_date: v_end = max_date
                        t3_val = (v_start, v_end)
                    else:
                        t3_val = t3_range_default
                else:
                    s_d, e_d = get_work_week(raw_session_t3)
                    t3_val = (s_d, e_d)

                t3_range_picked = st.date_input(
                    "📅 Chọn khoảng ngày đối soát (Từ ngày – Đến ngày):",
                    value=t3_val,
                    min_value=min_date,
                    max_value=max_date,
                    format="YYYY-MM-DD",
                    key="t3_date_range_picker",
                    help="Bấm vào ngày thứ bất kỳ trong tuần để tự động chọn tuần đó (Thứ 2 – Thứ 6) hoặc bấm nút 'Tổng Hợp' dưới chân lịch để xem toàn bộ."
                )

            # Xử lý dải ngày được chọn
            if isinstance(t3_range_picked, (list, tuple)):
                if len(t3_range_picked) == 2:
                    t3_start_d, t3_end_d = t3_range_picked[0], t3_range_picked[1]
                elif len(t3_range_picked) == 1:
                    t3_start_d, t3_end_d = get_work_week(t3_range_picked[0])
                else:
                    t3_start_d, t3_end_d = min_date, max_date
            else:
                t3_start_d, t3_end_d = get_work_week(t3_range_picked)

            if t3_start_d > t3_end_d:
                t3_start_d, t3_end_d = t3_end_d, t3_start_d

            # Callback & Nút trigger nội bộ (đã ẩn hoàn toàn qua CSS, chỉ kích hoạt khi bấm nút Tổng Hợp trong lịch)
            def reset_t3_to_all_dates():
                st.session_state["t3_date_range_picker"] = (min_date, max_date)

            st.button("t3_hidden_tong_hop", key="btn_t3_tong_hop_hidden", on_click=reset_t3_to_all_dates)

            is_view_all_active = (t3_start_d == min_date and t3_end_d == max_date)

            # Lọc danh sách ngày và dữ liệu theo khoảng đã chọn, LOẠI TRỪ THỨ 7 VÀ CHỦ NHẬT (d.weekday() < 5)
            filtered_dates = [d for d in all_dates if t3_start_d <= d <= t3_end_d and d.weekday() < 5]
            df_t3 = full_df[full_df["date"].isin(filtered_dates)]
            tot_all_calls = len(df_t3)

            if is_view_all_active:
                st.caption(f"Đang đối soát: **Toàn bộ dữ liệu vận hành ({t3_start_d.strftime('%d/%m/%Y')} ➔ {t3_end_d.strftime('%d/%m/%Y')})** — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")
            else:
                st.caption(f"Đang đối soát: **{t3_start_d.strftime('%d/%m/%Y')} ➔ {t3_end_d.strftime('%d/%m/%Y')}** (Thứ 2 – Thứ 6, trừ T7 & CN) — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")

            # 1. HỆ THỐNG HERO KPIS TÍCH LŨY
            tot_all_503 = int((df_t3["result_code"] == "503_CONGESTION").sum()) if not df_t3.empty else 0
            tot_all_ans = int((df_t3["result_code"] == "ANSWERED").sum()) if not df_t3.empty else 0
            all_asr_pct = (tot_all_ans / tot_all_calls * 100) if tot_all_calls > 0 else 0.0
            all_err_pct = (tot_all_503 / tot_all_calls * 100) if tot_all_calls > 0 else 0.0
            all_acd_sec = float(df_t3[df_t3["result_code"] == "ANSWERED"]["duration"].mean()) if tot_all_ans > 0 else 0.0

            tot_all_p1 = sum(int(past_days_ts[d]["is_p1_red"].sum()) for d in filtered_dates if d in past_days_ts)
            tot_all_p2 = sum(int(past_days_ts[d]["is_p2_yellow"].sum()) for d in filtered_dates if d in past_days_ts)
            if is_realtime_mode and current_date in filtered_dates and not completed_buckets.empty:
                tot_all_p1 += int(completed_buckets["is_p1_red"].sum())
                tot_all_p2 += int(completed_buckets["is_p2_yellow"].sum())

            tot_completed_buckets_all = sum(len(past_days_ts[d]) for d in filtered_dates if d in past_days_ts) + ((len(completed_buckets) if is_realtime_mode else 0) if current_date in filtered_dates else 0)
            sla_compliance_pct = ((tot_completed_buckets_all - tot_all_p1) / tot_completed_buckets_all * 100) if tot_completed_buckets_all > 0 else 100.0

            # Hàng 1: 3 Card chính
            c1, c2, c3 = st.columns(3)
            c1.metric("Tổng Lưu Lượng Cuộc Gọi", f"{tot_all_calls:,} cuộc", f"{len(filtered_dates)} ngày vận hành")
            c2.metric("Tỷ Lệ Bắt Máy Thành Công (ASR)", f"{all_asr_pct:.1f}%", f"{tot_all_ans:,} cuộc nghe máy (Mục tiêu >= 50%)", delta_color="normal" if all_asr_pct >= 50 else "inverse")
            c3.metric("Thời Lượng Đàm Thoại TB (ACD)", f"{all_acd_sec:.0f} giây", "Trung bình cuộc gọi Answered", delta_color="off")

            # Hàng 2: 3 Card chỉ số chất lượng & rủi ro
            c4, c5, c6 = st.columns(3)
            c4.metric("Tỷ Lệ Lỗi Viễn Thông 503", f"{all_err_pct:.2f}%", f"{tot_all_503} lỗi (Mục tiêu SLA <= 5.0%)", delta_color="inverse" if all_err_pct > 5 else "normal")
            c5.metric("Độ Khả Dụng Vận Hành (SLA)", f"{sla_compliance_pct:.1f}%", "Tỷ lệ khung giờ không có sự cố P1", delta_color="normal" if sla_compliance_pct >= 95 else "inverse")
            c6.metric("Tổng Số Sự Cố Ghi Nhận", f"{tot_all_p1} P1  |  {tot_all_p2} P2", "P1 Lỗi mạng / P2 Đột biến tải", delta_color="off")

            st.markdown("---")

            # 2. BIỂU ĐỒ TRỰC QUAN ĐA NGÀY (CENTRAL ANALYTICS CHARTS)

            day_matrix_rows = []
            for d in filtered_dates:
                sub = full_df[full_df["date"] == d]
                tot = len(sub)
                ans = int((sub["result_code"] == "ANSWERED").sum())
                unans = tot - ans
                n_503 = int((sub["result_code"] == "503_CONGESTION").sum())
                asr = round(ans / tot * 100, 1) if tot > 0 else 0.0
                err = round(n_503 / tot * 100, 1) if tot > 0 else 0.0
                diff_gap = round(asr - err, 1)
                ratio_val = round(ans / max(1, n_503), 1)
                acd = round(float(sub[sub["result_code"] == "ANSWERED"]["duration"].mean()), 1) if ans > 0 else 0.0

                ts_d = past_days_ts.get(d)
                if ts_d is None and d == current_date:
                    ts_d = completed_buckets
                p1 = int(ts_d["is_p1_red"].sum()) if ts_d is not None and not ts_d.empty else 0
                p2 = int(ts_d["is_p2_yellow"].sum()) if ts_d is not None and not ts_d.empty else 0

                if p1 > 0 or err >= 10.0:
                    sla = "🔴 Vi phạm SLA"
                elif p2 > 0 or err >= 5.0:
                    sla = "🟡 Cảnh báo"
                else:
                    sla = "🟢 Đạt chuẩn SLA"

                day_matrix_rows.append({
                    "date_obj": d,
                    "date_str": d.strftime("%Y-%m-%d (%a)"),
                    "date_label": d.strftime("%a\n%d/%m"),
                    "total_calls": tot,
                    "calls_answered": ans,
                    "calls_unanswered": unans,
                    "asr_pct": asr,
                    "calls_503": n_503,
                    "error_rate_pct": err,
                    "diff_gap_pct": diff_gap,
                    "ratio_ans_err": ratio_val,
                    "acd_sec": acd,
                    "p1_alerts": p1,
                    "p2_warnings": p2,
                    "sla_status": sla
                })

            df_matrix = pd.DataFrame(day_matrix_rows)

            if not df_matrix.empty:
                col_chart_t3_1, col_chart_t3_2 = st.columns(2)
                with col_chart_t3_1:
                    st.markdown("#### 📈 Lưu Lượng Hoạt Động Theo Ngày")
                    st.caption("So sánh cuộc gọi nghe máy thành công và cuộc gọi bị lỗi viễn thông 503 theo ngày (rê chuột để xem tương tác đa chỉ số).")
                    fig_main = go.Figure()
                    fig_main.add_trace(go.Bar(
                        x=df_matrix["date_str"], y=df_matrix["calls_answered"],
                        name="Kết nối thành công (Nghe máy)",
                        marker_color="#38bdf8",
                        hovertemplate="<b>Nghe máy:</b> %{y:,} cuộc<extra></extra>"
                    ))
                    fig_main.add_trace(go.Bar(
                        x=df_matrix["date_str"], y=df_matrix["calls_503"],
                        name="Cuộc gọi bị lỗi mạng (503)",
                        marker_color="#f85149",
                        text=[f"{int(v):,}" if v > 0 else "" for v in df_matrix["calls_503"]],
                        textposition="outside",
                        hovertemplate="<b>Lỗi mạng 503:</b> %{y:,} cuộc<extra></extra>"
                    ))
                    fig_main.update_layout(
                        template=plotly_template,
                        barmode="group",
                        height=370,
                        hovermode="x unified",
                        paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                        margin=dict(l=30, r=20, t=50, b=30),
                        yaxis=dict(title="Cuộc gọi / Ngày", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                        xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                        legend=dict(orientation="h", y=1.18, x=0.5, xanchor="center", font=dict(color=text_main, size=11))
                    )
                    st.plotly_chart(fig_main, use_container_width=True)

                with col_chart_t3_2:
                    st.markdown("#### 🎯 Xu Hướng Chất Lượng & Tỷ Lệ Chênh Lệch (ASR vs Lỗi 503)")
                    st.caption("Trực quan hóa tỷ lệ ASR, tỷ lệ lỗi 503, vùng chênh lệch an toàn (ASR - Lỗi) cùng các mốc SLA chuẩn.")
                    fig_qual = go.Figure()
                    # 1. Đường tỷ lệ bắt máy ASR
                    fig_qual.add_trace(go.Scatter(
                        x=df_matrix["date_str"], y=df_matrix["asr_pct"],
                        mode="lines+markers",
                        name="Tỷ lệ bắt máy ASR (%)",
                        line=dict(color="#0284c7", width=2.5),
                        marker=dict(size=7, color="#0369a1"),
                        hovertemplate="<b>Tỷ lệ bắt máy ASR:</b> %{y:.1f}%<extra></extra>"
                    ))
                    # 2. Đường tỷ lệ lỗi viễn thông 503 kèm vùng phủ chênh lệch (ASR - Lỗi)
                    fig_qual.add_trace(go.Scatter(
                        x=df_matrix["date_str"], y=df_matrix["error_rate_pct"],
                        mode="lines+markers",
                        name="Tỷ lệ lỗi viễn thông 503 (%)",
                        line=dict(color="#ef4444", width=2.5),
                        marker=dict(size=7, color="#b91c1c"),
                        fill="tonexty",
                        fillcolor="rgba(2, 132, 199, 0.12)",
                        hovertemplate="<b>Tỷ lệ lỗi 503:</b> %{y:.2f}%<extra></extra>"
                    ))
                    # 3. Đường chênh lệch an toàn ASR - Lỗi
                    fig_qual.add_trace(go.Scatter(
                        x=df_matrix["date_str"], y=df_matrix["diff_gap_pct"],
                        mode="lines+markers",
                        name="Chênh lệch (ASR - Lỗi)",
                        line=dict(color="#a855f7", width=2, dash="dashdot"),
                        marker=dict(size=6, symbol="diamond", color="#9333ea"),
                        hovertemplate="<b>Chênh lệch (ASR - Lỗi):</b> +%{y:.1f}%<extra></extra>"
                    ))
                    # 4. Mục tiêu ASR chuẩn (>= 50%)
                    fig_qual.add_trace(go.Scatter(
                        x=df_matrix["date_str"],
                        y=[50.0] * len(df_matrix),
                        mode="lines",
                        name="Mục tiêu ASR (≥ 50%)",
                        line=dict(color="#10b981", width=1.5, dash="dot"),
                        hoverinfo="skip"
                    ))
                    # 5. Ngưỡng an toàn lỗi viễn thông (<= 5%)
                    fig_qual.add_trace(go.Scatter(
                        x=df_matrix["date_str"],
                        y=[5.0] * len(df_matrix),
                        mode="lines",
                        name="Ngưỡng an toàn lỗi (≤ 5%)",
                        line=dict(color="#dc2626", width=1.5, dash="dash"),
                        hoverinfo="skip"
                    ))
                    fig_qual.update_layout(
                        template=plotly_template,
                        height=370,
                        hovermode="x unified",
                        paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                        margin=dict(l=30, r=20, t=50, b=30),
                        yaxis=dict(title="Tỷ lệ (%) / Chênh lệch (%)", range=[-2, max(65, float(df_matrix['asr_pct'].max()) + 10)], gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                        xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                        legend=dict(
                            orientation="h",
                            y=1.18,
                            x=0.5,
                            xanchor="center",
                            font=dict(color=text_main, size=11)
                        )
                    )
                    st.plotly_chart(fig_qual, use_container_width=True)

            st.markdown("---")

            # 2. PHÂN TÍCH CHUYÊN SÂU: PHỄU VẬN HÀNH & PHÂN BỔ THỜI LƯỢNG ĐÀM THOẠI
            col_chart_t3_3, col_chart_t3_4 = st.columns(2)
            with col_chart_t3_3:
                st.markdown("#### 🔻 Phễu Chuyển Đổi Vận Hành Viễn Thông")
                st.caption("Tỷ lệ chuyển đổi qua từng mắt xích vận hành.")

                n_connected = tot_all_calls - tot_all_503
                df_ans = df_t3[df_t3["result_code"] == "ANSWERED"] if not df_t3.empty else pd.DataFrame()
                n_eff_30 = int((df_ans["duration"] >= 30).sum()) if not df_ans.empty else 0
                n_deep_60 = int((df_ans["duration"] >= 60).sum()) if not df_ans.empty else 0

                fig_funnel = go.Figure(go.Funnel(
                    y=[
                        "1. Tổng cuộc gọi phát ra",
                        "2. Kết nối mạng thành công",
                        "3. Khách hàng bắt máy (ASR)",
                        "4. Đàm thoại hiệu quả (≥30s)",
                        "5. Tư vấn chuyên sâu (≥60s)"
                    ],
                    x=[tot_all_calls, n_connected, tot_all_ans, n_eff_30, n_deep_60],
                    textposition="inside",
                    textinfo="value+percent initial",
                    opacity=0.9,
                    marker=dict(
                        color=["#3b82f6", "#06b6d4", "#10b981", "#8b5cf6", "#f59e0b"],
                        line=dict(color=card_bg, width=2)
                    ),
                    connector={"line": {"color": border_col, "dash": "dot", "width": 1.5}},
                    hovertemplate="<b>%{y}</b><br>• Số lượng: <b>%{x:,} cuộc</b><br>• Tỷ trọng so với tổng phát ra: <b>%{percentInitial:.1f}%</b><br>• Chuyển đổi từ tầng trước: <b>%{percentPrevious:.1f}%</b><extra></extra>"
                ))
                fig_funnel.update_layout(
                    template=plotly_template,
                    height=360,
                    paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                    margin=dict(l=20, r=20, t=30, b=25),
                    showlegend=False
                )
                st.plotly_chart(fig_funnel, use_container_width=True)

            with col_chart_t3_4:
                st.markdown("#### ⏱️ Phân Phối Thời Lượng Cuộc Gọi (ACD Breakdown)")
                ans_cnt = len(df_ans)
                st.caption("Đo lường mức độ tương tác và chiều sâu đàm thoại của các cuộc gọi bắt máy.")

                if not df_ans.empty:
                    dur_15 = int((df_ans["duration"] < 15).sum())
                    dur_30 = int(((df_ans["duration"] >= 15) & (df_ans["duration"] <= 30)).sum())
                    dur_60 = int(((df_ans["duration"] > 30) & (df_ans["duration"] <= 60)).sum())
                    dur_120 = int(((df_ans["duration"] > 60) & (df_ans["duration"] <= 120)).sum())
                    dur_plus = int((df_ans["duration"] > 120).sum())
                else:
                    dur_15 = dur_30 = dur_60 = dur_120 = dur_plus = 0

                dur_labels = ["< 15s (Dập máy)", "15s - 30s (Chào hỏi)", "31s - 60s (Trao đổi)", "61s - 120s (Tiềm năng)", "> 120s (Chuyên sâu)"]
                dur_vals = [dur_15, dur_30, dur_60, dur_120, dur_plus]
                dur_colors = ["#f43f5e", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981"]
                dur_texts = [f"{v:,} ({v/max(1, ans_cnt)*100:.1f}%)" if v > 0 else "0" for v in dur_vals]

                fig_hist = go.Figure()
                fig_hist.add_trace(go.Bar(
                    x=dur_labels,
                    y=dur_vals,
                    text=dur_texts,
                    textposition="outside",
                    marker=dict(
                        color=dur_colors,
                        line=dict(color=card_bg, width=1.5)
                    ),
                    hovertemplate="<b>%{x}</b><br>• Số cuộc gọi: <b>%{y:,} cuộc</b><br>• Chiếm: <b>%{text} cuộc nghe máy</b><extra></extra>"
                ))
                fig_hist.update_layout(
                    template=plotly_template,
                    height=360,
                    paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                    margin=dict(l=30, r=20, t=30, b=30),
                    yaxis=dict(title="Số cuộc nghe máy", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    showlegend=False
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown("---")

            # 3. PHÂN VÙNG ĐÁY MASTER-DETAIL (60% BẢNG + 40% DONUT CHART & PHÂN BỔ)
            col_bottom_table, col_bottom_donut = st.columns([1.6, 1.4])

            with col_bottom_table:
                st.markdown("#### 📋 Nhật Ký Đánh Giá Vận Hành Đa Ngày")
                if not df_matrix.empty:
                    display_matrix = pd.DataFrame()
                    display_matrix["Ngày Vận Hành"] = df_matrix["date_str"]
                    display_matrix["Tổng Cuộc"] = df_matrix["total_calls"].astype(int)
                    display_matrix["Nghe Máy"] = df_matrix["calls_answered"].astype(int)
                    display_matrix["Tỷ Lệ ASR"] = df_matrix["asr_pct"].astype(str) + "%"
                    display_matrix["Lỗi 503"] = df_matrix["calls_503"].astype(int).astype(str) + " (" + df_matrix["error_rate_pct"].astype(str) + "%)"
                    display_matrix["ACD"] = df_matrix["acd_sec"].astype(str) + "s"
                    display_matrix["Trạng Thái SLA"] = df_matrix["sla_status"]

                    st.dataframe(
                        display_matrix.iloc[::-1],
                        use_container_width=True,
                        hide_index=True
                    )

            with col_bottom_donut:
                st.markdown("#### 🎯 Cơ Cấu Kết Quả Cuộc Gọi")

                outcome_meta = {
                    "ANSWERED": {
                        "badge": "🔵",
                        "label": "Khách nghe máy",
                        "group": "Thành công",
                        "color": "#2563eb"
                    },
                    "NO_ANSWER": {
                        "badge": "⚪",
                        "label": "Không bắt máy",
                        "group": "Khách hàng",
                        "color": "#94a3b8"
                    },
                    "BUSY": {
                        "badge": "🟡",
                        "label": "Thuê bao bận",
                        "group": "Khách hàng",
                        "color": "#f59e0b"
                    },
                    "503_CONGESTION": {
                        "badge": "🔴",
                        "label": "Lỗi nghẽn mạng (SIP 503)",
                        "group": "Lỗi hạ tầng",
                        "color": "#ef4444"
                    },
                    "CALLBACK_REQUESTED": {
                        "badge": "🟣",
                        "label": "Hẹn gọi lại sau",
                        "group": "Khách hàng",
                        "color": "#8b5cf6"
                    },
                    "VOICEMAIL": {
                        "badge": "🌐",
                        "label": "Hộp thư thoại",
                        "group": "Khách hàng",
                        "color": "#06b6d4"
                    }
                }

                res_counts = df_t3["result_code"].value_counts()
                res_labels = res_counts.index.tolist()
                res_vals = res_counts.values.tolist()

                chart_labels = [outcome_meta.get(k, {}).get("label", k) for k in res_labels]
                chart_colors = [outcome_meta.get(k, {}).get("color", "#cbd5e1") for k in res_labels]

                # Biểu đồ Donut tương tác Plotly (rê chuột hiển thị số cuộc và tỷ trọng %)
                fig_donut = go.Figure(data=[go.Pie(
                    labels=chart_labels,
                    values=res_vals,
                    hole=0.62,
                    sort=False,
                    direction="clockwise",
                    marker=dict(
                        colors=chart_colors,
                        line=dict(color=card_bg, width=2)
                    ),
                    textinfo="percent",
                    textposition="inside",
                    textfont=dict(size=11, color="#ffffff", family="sans-serif"),
                    hovertemplate="<b>%{label}</b><br>• Số cuộc: <b>%{value:,} cuộc</b><br>• Tỷ trọng: <b>%{percent}</b><extra></extra>"
                )])
                fig_donut.update_layout(
                    template=plotly_template,
                    height=330,
                    margin=dict(l=15, r=15, t=15, b=15),
                    paper_bgcolor=card_bg,
                    plot_bgcolor=card_bg,
                    showlegend=False,
                    annotations=[
                        dict(
                            text=f"<b style='font-size:22px;color:{text_main};'>{tot_all_calls:,}</b><br><span style='font-size:11.5px;color:{text_muted};font-weight:500;'>Tổng cuộc gọi</span>",
                            x=0.5, y=0.5,
                            showarrow=False
                        )
                    ]
                )
                st.plotly_chart(fig_donut, use_container_width=True)

        return is_today_finished

# KÍCH HOẠT HIỂN THỊ
is_day_done = render_live_monitoring_fragment()

# Tự động làm mới liên tục khi ở chế độ Thời Gian Thực (để tự động đón nhận ngày mới khi chuyển ngày)
if is_realtime_mode:
    time.sleep(3.5)
    st.rerun()

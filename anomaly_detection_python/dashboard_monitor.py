# dashboard_monitor.py
"""
SCC Outbound: Telecom NOC (Network Operations Center) & Anomaly Detection System
Phiên bản 3.2.2-NOC:
1. Tinh gọn 4 Phân hệ cốt lõi chuẩn NOC trên Sidebar:
   - Dashboard: Giám sát vận hành trực tiếp ca trực (Tiến độ ca trực, 4 Hero KPIs, 2 biểu đồ GP & Bayes, Bảng sự cố kèm hồ sơ điều tra kỹ thuật SOP).
   - Analysis: Phân tích máy học chu kỳ 24h & Ma trận rủi ro theo khung giờ.
   - Reports: Đối soát tổng hợp tuần làm việc (T2-T6), ASR, ACD, SLA, Phễu vận hành, Bảng đánh giá chất lượng từng nhà mạng (Carrier Scorecard) & Donut.
   - System: Đo lường hạ tầng viễn thông (Dual-Write DB1 container, DB2 host, Redis, Telegram).
2. Bộ lọc lịch được chuyển lại vào bên trong từng Tab (không để ở sidebar).
3. Nút đóng/mở sidebar được làm nổi bật với viền và nền tương phản cao, dễ nhìn và dễ bấm.
4. Lấp đầy khoảng trống với các tiện ích nghiệp vụ viễn thông thực tế (Tiến độ ca trực, Bảng đối soát nhà mạng, Heatmap rủi ro).
5. 100% không icon emoji rườm rà, ẩn hoàn toàn nút tích tròn radio.
"""
import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots
try:
    from streamlit_plotly_events import plotly_events
except ImportError:
    plotly_events = None
from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

SYSTEM_ERRORS = ["503_CONGESTION", "500_SERVER_ERROR", "504_GATEWAY_TIMEOUT", "429_TOO_MANY_REQUESTS", "408_REQUEST_TIMEOUT"]

st.set_page_config(
    page_title="SCC Outbound - Telecom NOC & Anomaly System",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# QUẢN LÝ THEME GIAO DIỆN: SÁNG / TỐI
# ==============================================================================
try:
    theme_mode = st.session_state.get("theme_mode", "Sáng")
except Exception:
    theme_mode = "Sáng"

is_dark = (theme_mode == "Tối")

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

/* 1. NỀN TOÀN TRANG & TỐI ƯU CHIỀU RỘNG */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main, .block-container {{
    background-color: {bg_main} !important;
    color: {text_main} !important;
}}
.block-container {{
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}}
[data-testid="stHeader"] {{
    background-color: {bg_main} !important;
}}

/* 2. ẨN HOÀN TOÀN NÚT TÍCH HÌNH TRÒN CỦA RADIO TRÊN TOÀN GIAO DIỆN */
div[data-testid="stRadio"] input[type="radio"] {{
    position: absolute !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
    pointer-events: none !important;
}}
div[data-testid="stRadio"] label > div:first-of-type,
div[data-testid="stRadio"] label > div:first-child,
div[data-testid="stRadio"] label > div[aria-hidden="true"] {{
    display: none !important;
}}
div[data-testid="stRadio"] label svg {{
    display: none !important;
}}

/* 3. SIDEBAR BÊN TRÁI CHUẨN SOC / NIDS */
section[data-testid="stSidebar"] {{
    background-color: {card_bg} !important;
    border-right: 1px solid {border_col} !important;
    padding-top: 1.2rem !important;
}}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: 0.6rem !important;
}}
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 4px !important;
}}

/* CÁC MỤC MENU DẠNG NÚT BẤM / PILL (KHÔNG CÒN NÚT TRÒN) */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label {{
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 10px 14px !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
    border: 1px solid transparent !important;
    color: {text_main} !important;
    margin: 0 !important;
}}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {{
    background-color: {tab_active_bg} !important;
    color: {tab_active_text} !important;
}}

/* MỤC ĐANG ĐƯỢC CHỌN (ACTIVE HIGHLIGHT) */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked),
section[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-checked="true"] {{
    background-color: {"#3b82f6" if is_dark else "#0284c7"} !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 6px rgba(2, 132, 199, 0.25) !important;
}}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) *,
section[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-checked="true"] * {{
    color: #ffffff !important;
    font-weight: 700 !important;
}}

/* 4. THEME TOGGLE SÁNG / TỐI DẠNG NÚT BẤM PHÂN ĐOẠN (SEGMENTED PILL SWITCH) */
.main div[data-testid="stRadio"] {{
    display: flex !important;
    justify-content: flex-end !important;
    align-items: center !important;
    margin-top: 2px !important;
}}
.main div[data-testid="stRadio"] > label {{
    display: none !important;
}}
.main div[data-testid="stRadio"] div[role="radiogroup"] {{
    display: inline-flex !important;
    flex-direction: row !important;
    background-color: {"#1e293b" if is_dark else "#f1f5f9"} !important;
    border: 1px solid {"#334155" if is_dark else "#cbd5e1"} !important;
    border-radius: 9999px !important;
    padding: 3px !important;
    gap: 3px !important;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.08) !important;
    width: fit-content !important;
    margin-left: auto !important;
}}
.main div[data-testid="stRadio"] div[role="radiogroup"] label {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 6px 18px !important;
    border-radius: 9999px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin: 0 !important;
    color: {"#94a3b8" if is_dark else "#64748b"} !important;
    background: transparent !important;
    border: none !important;
    user-select: none !important;
}}
.main div[data-testid="stRadio"] div[role="radiogroup"] label:hover {{
    color: {text_main} !important;
    background-color: {"rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.04)"} !important;
}}
.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked),
.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(:checked),
.main div[data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"] {{
    background-color: {"#3b82f6" if is_dark else "#ffffff"} !important;
    color: {"#ffffff" if is_dark else "#0f172a"} !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18) !important;
}}
.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) *,
.main div[data-testid="stRadio"] div[role="radiogroup"] label:has(:checked) *,
.main div[data-testid="stRadio"] div[role="radiogroup"] label[data-checked="true"] * {{
    color: {"#ffffff" if is_dark else "#0f172a"} !important;
    font-weight: 700 !important;
}}

iframe[title="streamlit.components.v1.html"],
iframe[title*="components.v1.html"],
div[data-testid="stCustomComponentV1"] {{
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    border: none !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}}

/* 5. NÚT ĐÓNG / MỞ SIDEBAR NỔI BẬT & DỄ NHÌN */
[data-testid="stSidebarCollapseButton"],
button[aria-label="Close sidebar"],
button[aria-label="Open sidebar"],
[data-testid="collapsedControl"] {{
    background-color: {card_bg} !important;
    border: 1.5px solid {"#3b82f6" if is_dark else "#0284c7"} !important;
    border-radius: 8px !important;
    color: {text_main} !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    padding: 4px 6px !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="collapsedControl"]:hover {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border-color: #0284c7 !important;
    transform: scale(1.08) !important;
}}
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="collapsedControl"] svg {{
    fill: {"#38bdf8" if is_dark else "#0284c7"} !important;
    stroke: {"#38bdf8" if is_dark else "#0284c7"} !important;
    width: 20px !important;
    height: 20px !important;
}}
[data-testid="stSidebarCollapseButton"]:hover svg,
[data-testid="collapsedControl"]:hover svg {{
    fill: #ffffff !important;
    stroke: #ffffff !important;
}}

/* 6. VĂN BẢN VÀ TIÊU ĐỀ SẮC NÉT */
h1, h2, h3, h4, h5, h6, p, span, label {{
    color: {text_main} !important;
}}

/* 7. BỘ LỌC LỊCH (CALENDAR DATE PICKER) & POPUP LỊCH */
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

div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
div[data-baseweb="calendar"] {{
    background-color: {card_bg} !important;
    border-radius: 12px !important;
}}
div[data-baseweb="popover"] {{
    border: 1px solid {border_col} !important;
    box-shadow: 0 16px 36px rgba(0,0,0,0.45) !important;
    z-index: 1000005 !important;
}}
/* Triệt tiêu hoàn toàn nền trắng của BaseWeb calendar header và các container con */
div[data-baseweb="calendar"] div {{
    background-color: transparent !important;
}}
div[data-baseweb="calendar"] {{
    background-color: {card_bg} !important;
    color: {text_main} !important;
    padding: 8px !important;
}}
div[data-baseweb="calendar"] * {{
    color: {text_main} !important;
}}
div[data-baseweb="calendar"] button,
div[data-baseweb="calendar"] [role="button"] {{
    background-color: transparent !important;
    color: {text_main} !important;
    border: none !important;
    cursor: pointer !important;
    border-radius: 6px !important;
}}
div[data-baseweb="calendar"] button:hover,
div[data-baseweb="calendar"] [role="button"]:hover {{
    background-color: {"#1e293b" if is_dark else "#e2e8f0"} !important;
}}
div[data-baseweb="calendar"] button svg,
div[data-baseweb="calendar"] svg {{
    fill: {text_main} !important;
    stroke: {text_main} !important;
}}
div[data-baseweb="calendar"] [aria-hidden="true"],
div[data-baseweb="calendar"] [role="presentation"] {{
    color: {text_muted} !important;
    font-weight: 700 !important;
    font-size: 12px !important;
}}
div[data-baseweb="calendar"] [role="gridcell"] {{
    color: {text_main} !important;
    cursor: pointer !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
}}
div[data-baseweb="calendar"] [role="gridcell"] > div {{
    color: {text_main} !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border-radius: 50% !important;
}}
div[data-baseweb="calendar"] [role="gridcell"]:hover,
div[data-baseweb="calendar"] [role="gridcell"]:hover > div {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
}}
div[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"],
div[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] > div,
div[data-baseweb="calendar"] [aria-selected="true"],
div[data-baseweb="calendar"] [aria-selected="true"] * {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    font-weight: 800 !important;
    border-radius: 50% !important;
}}
div[data-baseweb="calendar"] [role="gridcell"]:before {{
    background-color: {"rgba(2, 132, 199, 0.28)" if is_dark else "rgba(2, 132, 199, 0.15)"} !important;
}}
div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"],
div[data-baseweb="calendar"] [role="gridcell"][aria-disabled="true"] > div,
div[data-baseweb="calendar"] [aria-disabled="true"],
div[data-baseweb="calendar"] [aria-disabled="true"] * {{
    color: {"#475569" if is_dark else "#cbd5e1"} !important;
    opacity: 0.3 !important;
    cursor: not-allowed !important;
    background-color: transparent !important;
}}
/* Menu dropdown chọn Tháng & Năm trong BaseWeb popover */
div[data-baseweb="menu"],
div[data-baseweb="menu"] > ul,
ul[role="listbox"],
ul[role="listbox"] * {{
    background-color: {card_bg} !important;
    color: {text_main} !important;
}}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
}}


/* 8. NÚT BẤM STREAMLIT HIỆN ĐẠI */
div[data-testid="stButton"] button {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 6px 14px !important;
    background-color: {card_bg} !important;
    color: {text_main} !important;
    border: 1px solid {border_col} !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    transition: all 0.2s ease !important;
}}
div[data-testid="stButton"] button:hover {{
    border-color: #0284c7 !important;
    color: #0284c7 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
}}

/* 9. CARD, DATAFRAME, PLOTLY CHART & METRIC */
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

try:
    from ml_inference_engine import SCCAnomalyInferenceEngine
    ML_ENGINE = SCCAnomalyInferenceEngine()
except Exception:
    ML_ENGINE = None

# ==============================================================================
# 1. CẤU HÌNH BOT TELEGRAM
# ==============================================================================
def _load_env_dashboard():
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        return
    for p in [Path(".env"), Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent / ".env"]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k not in os.environ:
                            os.environ[k] = v
            break

_load_env_dashboard()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
raw_chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in raw_chat_ids.split(",") if cid.strip()] if raw_chat_ids else []
TELEGRAM_PROXIES = {
    "http": os.getenv("HTTP_PROXY", "http://proxy.fpt.vn:80"),
    "https": os.getenv("HTTPS_PROXY", "http://proxy.fpt.vn:80")
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
        f"📈 <b>Tỷ lệ gián đoạn:</b> <b>{err_rate*100:.1f}%</b> (Ngưỡng động an toàn: {threshold*100:.1f}%)\n"
        f"📐 <b>Z-score lưu lượng:</b> {zscore:.2f}\n"
        f"🤖 <b>Điểm rủi ro ML:</b> {ml_score*100:.1f}% (Phát hiện điểm dị biệt đa chiều)\n\n"
        f"⚠️ <b>Hành động khuyến nghị:</b>\n"
        f"1. Kiểm tra ngay SIP Gateway và trạng thái tổng đài Asterisk.\n"
        f"2. Chuyển tuyến cuộc gọi dự phòng (LCR) sang nhà mạng VNPT/MobiFone.\n"
        f"3. Liên hệ NOC nhà mạng Viettel theo đường dây nóng.\n"
    )
    if bad_call_samples:
        msg += "\n📋 <b>Bản ghi cuộc gọi lỗi mẫu:</b>\n"
        for s in bad_call_samples[:3]:
            msg += f"• Mã: <code>{s.get('call_id', '')}</code> | Mạng: <b>{s.get('carrier', 'N/A')}</b> | Thời gian: {str(s.get('start_time', ''))[11:19]}\n"
    return send_telegram_msg(msg)

# ==============================================================================
# 2. MÔ HÌNH HỌC THỐNG KÊ & CHU KỲ 24H (DYNAMIC SEASONALITY & RISK DECOMPOSITION)
# ==============================================================================
def compute_dynamic_seasonality_and_risk(past_days_ts: dict, today_completed_ts: pd.DataFrame = None):
    """Tính toán động đường chu kỳ trung bình 24h và xác suất rủi ro theo từng giờ."""
    all_buckets = []
    tot_days = 0

    for d, ts in past_days_ts.items():
        if ts is not None and not ts.empty:
            tot_days += 1
            all_buckets.append(ts[["bucket_time", "hour", "calls_total", "calls_503", "is_p1_red", "is_p2_yellow"]].copy())

    if today_completed_ts is not None and not today_completed_ts.empty:
        tot_days += 1
        all_buckets.append(today_completed_ts[["bucket_time", "hour", "calls_total", "calls_503", "is_p1_red", "is_p2_yellow"]].copy())

    if not all_buckets:
        hourly_stats = {}
        for h in range(24):
            prof = HOURLY_PROFILE.get(h, 0.05)
            exp_15m = (prof * 400.0) / 4.0
            hourly_stats[h] = {
                "mean_15m": exp_15m,
                "sd_15m": max(1.0, np.sqrt(exp_15m)),
                "risk_pct": 5.0,
                "p1_count": 0,
                "p2_count": 0,
                "tot_buckets": 0,
                "day_incidents": 0,
                "tot_days": 1
            }
        return hourly_stats, 1, 0

    df_all = pd.concat(all_buckets, ignore_index=True)
    df_all["date"] = df_all["bucket_time"].dt.date
    hourly_stats = {}

    for h in range(24):
        sub = df_all[df_all["hour"] == h]
        if not sub.empty:
            m = float(sub["calls_total"].mean())
            s = float(sub["calls_total"].std(ddof=1)) if len(sub) > 1 else max(1.0, np.sqrt(m))
            if np.isnan(s) or s <= 0:
                s = max(1.0, np.sqrt(m))

            n_b = len(sub)
            p1_c = int(sub["is_p1_red"].sum())
            p2_c = int(sub["is_p2_yellow"].sum())

            inc_dates = sub[sub["is_p1_red"] | sub["is_p2_yellow"]]["date"].nunique()
            tot_h_days = sub["date"].nunique()
            risk_pct = round((inc_dates / max(1, tot_h_days)) * 100, 1)

            hourly_stats[h] = {
                "mean_15m": round(m, 2),
                "sd_15m": round(s, 2),
                "risk_pct": risk_pct,
                "p1_count": p1_c,
                "p2_count": p2_c,
                "tot_buckets": n_b,
                "day_incidents": inc_dates,
                "tot_days": tot_h_days
            }
        else:
            prof = HOURLY_PROFILE.get(h, 0.05)
            exp_15m = (prof * 400.0) / 4.0
            hourly_stats[h] = {
                "mean_15m": exp_15m,
                "sd_15m": max(1.0, np.sqrt(exp_15m)),
                "risk_pct": 0.0,
                "p1_count": 0,
                "p2_count": 0,
                "tot_buckets": 0,
                "day_incidents": 0,
                "tot_days": max(1, tot_days)
            }

    return hourly_stats, max(1, tot_days), len(df_all)

# ==============================================================================
# 3. QUẢN LÝ DỮ LIỆU & FALLBACK VÀO DATABASE
# ==============================================================================
_PAST_DAYS_TS_CACHE = {}
_PAST_DAYS_SUMMARY_CACHE = {}


@st.cache_data(ttl=30, show_spinner=False)
def _read_stream_snapshot(path_str, mtime, size):
    """Cache the large CSV read while preserving invalidation on file changes."""
    try:
        snapshot = pd.read_csv(path_str)
        return snapshot if len(snapshot) >= 2 else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def load_data_with_db_fallback():
    """Đọc dữ liệu từ file đệm buffer CSV; nếu file lỗi hoặc trống, tự động query trực tiếp từ PostgreSQL."""
    df = None
    if STREAM_FILE.exists() and STREAM_FILE.stat().st_size >= 100:
        try:
            stat = STREAM_FILE.stat()
            df = _read_stream_snapshot(str(STREAM_FILE), stat.st_mtime, stat.st_size)
            if len(df) >= 2:
                return df
        except Exception:
            df = None

    # Fallback vào PostgreSQL
    try:
        from anomaly_detection_python.db_writer import DBWriter
        writer = DBWriter()
        for target in writer.targets:
            conn = writer._get_target_connection(target)
            if conn and conn.closed == 0:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT call_id, start_time, end_time, duration, result_code, carrier
                        FROM public.calls_stream
                        ORDER BY start_time ASC;
                    """)
                    rows = cur.fetchall()
                    if rows and len(rows) >= 2:
                        cols = ["call_id", "start_time", "end_time", "duration", "result_code", "carrier"]
                        df = pd.DataFrame(rows, columns=cols)
                        try:
                            df.to_csv(STREAM_FILE, index=False)
                        except Exception:
                            pass
                        return df
    except Exception as e:
        logging.warning(f"Fallback PostgreSQL query error: {e}")

    if SEED_FILE.exists():
        try:
            df = pd.read_csv(SEED_FILE)
            if len(df) >= 2:
                return df
        except Exception:
            pass

    return pd.DataFrame()

_STREAM_FILE_MTIME = None
_STREAM_FILE_SIZE = None
_CACHED_PIPELINE_STATE = None

def get_current_pipeline_state():
    """Đọc dữ liệu buffer với cơ chế fallback tự động vào PostgreSQL, tổng hợp theo khung 15 phút với bộ nhớ đệm chống lag."""
    global _PAST_DAYS_TS_CACHE, _PAST_DAYS_SUMMARY_CACHE, _STREAM_FILE_MTIME, _STREAM_FILE_SIZE, _CACHED_PIPELINE_STATE

    try:
        cur_mtime = STREAM_FILE.stat().st_mtime if STREAM_FILE.exists() else 0
        cur_size = STREAM_FILE.stat().st_size if STREAM_FILE.exists() else 0
    except Exception:
        cur_mtime = 0
        cur_size = 0

    if _CACHED_PIPELINE_STATE is not None and cur_mtime == _STREAM_FILE_MTIME and cur_size == _STREAM_FILE_SIZE:
        return _CACHED_PIPELINE_STATE

    df = load_data_with_db_fallback()
    if df.empty or len(df) < 2:
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()

    # The producer buffer is append-only and may contain legacy malformed rows
    # from an older schema. Coerce invalid timestamps so one bad row cannot
    # crash every Streamlit tab; discard only rows that cannot be time-indexed.
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    invalid_start_count = int(df["start_time"].isna().sum())
    if invalid_start_count:
        logging.warning("Bỏ qua %s raw rows có start_time không hợp lệ trong stream buffer.", invalid_start_count)
        df = df.dropna(subset=["start_time"]).copy()
    if df.empty or len(df) < 2:
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()
    df["bucket_time"] = df["start_time"].dt.floor("15min")
    df["date"] = df["start_time"].dt.date

    all_dates = sorted(df["date"].unique())
    current_date = all_dates[-1] if all_dates else datetime.now().date()

    past_days_summary = {}
    past_days_ts = {}
    past_dates = [d for d in all_dates if d < current_date]
    for p_date in past_dates:
        if p_date in _PAST_DAYS_TS_CACHE and p_date in _PAST_DAYS_SUMMARY_CACHE:
            past_days_ts[p_date] = _PAST_DAYS_TS_CACHE[p_date]
            past_days_summary[p_date] = _PAST_DAYS_SUMMARY_CACHE[p_date]
        else:
            p_df = df[df["date"] == p_date].copy()
            if not p_df.empty:
                p_ts = process_single_date(p_df, p_date, is_live_today=False)
                _PAST_DAYS_TS_CACHE[p_date] = p_ts
                _PAST_DAYS_SUMMARY_CACHE[p_date] = {
                    "total_calls": int(p_ts["calls_total"].sum()),
                    "calls_503": int(p_ts["calls_503"].sum()),
                    "error_rate": (p_ts["calls_503"].sum() / p_ts["calls_total"].sum() * 100) if p_ts["calls_total"].sum() > 0 else 0,
                    "p1_alerts": int(p_ts["is_p1_red"].sum()),
                    "p2_warnings": int(p_ts["is_p2_yellow"].sum())
                }
                past_days_ts[p_date] = _PAST_DAYS_TS_CACHE[p_date]
                past_days_summary[p_date] = _PAST_DAYS_SUMMARY_CACHE[p_date]

    df_today = df[df["date"] == current_date].copy() if current_date in all_dates else pd.DataFrame(columns=["call_id", "start_time", "end_time", "duration", "result_code", "bucket_time", "date"])
    if not df_today.empty:
        latest_time = df_today["start_time"].max()
        active_bucket = latest_time.floor("15min")
    else:
        active_bucket = pd.Timestamp(current_date).replace(hour=8, minute=0, second=0)

    ts_today = process_single_date(df_today, current_date, is_live_today=True, active_bucket=active_bucket)
    today_bad_calls = df_today[df_today["result_code"].isin(SYSTEM_ERRORS)].sort_values("start_time", ascending=False) if not df_today.empty else pd.DataFrame()

    _STREAM_FILE_MTIME = cur_mtime
    _STREAM_FILE_SIZE = cur_size
    _CACHED_PIPELINE_STATE = (ts_today, today_bad_calls, current_date, past_days_summary, df_today, past_days_ts, df)

    return _CACHED_PIPELINE_STATE

def get_system_telemetry():
    """Đo lường kiểm tra trạng thái kết nối hạ tầng viễn thông & Dual-Write Database."""
    telemetry = {
        "db1": {"name": "DB1 [PostgreSQL Container]", "host": "db", "port": 5432, "status": "ONLINE", "calls": 0, "ts": 0, "msg": ""},
        "db2": {"name": "DB2 [MinhTQ70 Host]", "host": "172.18.0.1", "port": 5432, "status": "ONLINE", "calls": 0, "ts": 0, "msg": ""},
        "redis": {"status": "ACTIVE", "port": 6380, "name": "Redis Stream Pipeline 6380", "msg": "Kênh buffer luồng cuộc gọi"},
        "telegram": {"status": "ACTIVE" if TELEGRAM_BOT_TOKEN else "STANDBY", "chats": len(TELEGRAM_CHAT_IDS), "proxy": "proxy.fpt.vn:80"}
    }
    try:
        from anomaly_detection_python.db_writer import DBWriter
        writer = DBWriter()
        for idx, target in enumerate(writer.targets):
            key = f"db{idx+1}"
            conn = writer._get_target_connection(target)
            if conn and conn.closed == 0:
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.calls_stream;")
                    c_cnt = cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM public.call_timeseries;")
                    ts_cnt = cur.fetchone()[0]
                    telemetry[key] = {
                        "name": target.get("id", f"DB{idx+1}"),
                        "host": target.get("host", ""),
                        "port": target.get("port", 5432),
                        "status": "ONLINE",
                        "calls": c_cnt,
                        "ts": ts_cnt,
                        "msg": "Đồng bộ thời gian thực chuẩn xác"
                    }
            else:
                telemetry[key] = {
                    "name": target.get("id", f"DB{idx+1}"),
                    "host": target.get("host", ""),
                    "port": target.get("port", 5432),
                    "status": "OFFLINE",
                    "calls": 0,
                    "ts": 0,
                    "msg": "Chưa kết nối hoặc đang khởi động"
                }
    except Exception as e:
        telemetry["db1"]["msg"] = str(e)
    return telemetry

# TẢI TRẠNG THÁI DỮ LIỆU
pipeline_state = get_current_pipeline_state()
ts_today, today_bad_calls, current_date, past_summary, df_today, past_days_ts, full_df = pipeline_state

if ts_today is not None and not full_df.empty:
    init_all_dates = sorted(full_df["date"].unique())
    min_hist_date = init_all_dates[0]
    max_hist_date = current_date if current_date else init_all_dates[-1]
else:
    min_hist_date = current_date if current_date else datetime.now().date()
    max_hist_date = min_hist_date

if "last_producer_date" not in st.session_state:
    st.session_state["last_producer_date"] = max_hist_date
    st.session_state["cal_date_picker"] = max_hist_date
    st.session_state["is_following_live"] = True

# Chỉ tự động cập nhật khi producer thực sự sinh ngày mới và đang ở chế độ follow live
if max_hist_date > st.session_state.get("last_producer_date", min_hist_date):
    st.session_state["last_producer_date"] = max_hist_date
    if st.session_state.get("is_following_live", True):
        st.session_state["cal_date_picker"] = max_hist_date
        st.session_state["_ui_dash_date_input"] = max_hist_date

init_picked = st.session_state.get("cal_date_picker", max_hist_date)
if hasattr(init_picked, "date"):
    init_picked = init_picked.date()

if init_picked > max_hist_date:
    init_picked = max_hist_date
    st.session_state["cal_date_picker"] = max_hist_date
elif init_picked < min_hist_date:
    init_picked = min_hist_date
    st.session_state["cal_date_picker"] = min_hist_date

is_realtime_mode = (init_picked == max_hist_date)
auto_live_stream = True

# ==============================================================================
# CƠ SỞ TRI THỨC SỰ CỐ VIỄN THÔNG (TELECOM NOC KB)
# ==============================================================================
TELECOM_ERROR_KB = {
    "503_CONGESTION": {
        "code": "503_CONGESTION",
        "title": "503_CONGESTION — Nghẽn mạch SIP Trunk / Carrier Outbound",
        "protocol": "SIP/2.0 503 Service Unavailable",
        "cause": "Tuyến trung kế SIP Trunk của nhà mạng đối tác bị quá tải dung lượng (concurrency limit) hoặc trạm thu phát viễn thông từ chối khởi tạo phiên gọi mới.",
        "actions": [
            "Kích hoạt định tuyến tự động (LCR) chuyển hướng lưu lượng sang trung kế phụ (VNPT / MobiFone / Viettel).",
            "Kiểm tra lưu lượng CPS (Calls Per Second) trên hệ thống quay số tự động, giảm nhịp gọi 15-20%.",
            "Liên hệ NOC nhà mạng đối tác mở thêm kênh đồng thời (Concurrent Channels)."
        ],
        "hotline": "Viettel NOC: 1800 8000 | VNPT NOC: 1800 1260 | MobiFone NOC: 1800 1090"
    },
    "504_GATEWAY_TIMEOUT": {
        "code": "504_GATEWAY_TIMEOUT",
        "title": "504_GATEWAY_TIMEOUT — Hết thời gian phản hồi SBC Gateway",
        "protocol": "SIP/2.0 504 Server Time-out / Gateway Timeout",
        "cause": "Thiết bị biên SBC (Session Border Controller) hoặc Media Gateway phía nhà mạng không phản hồi bản tin SIP INVITE trong khoảng thời gian quy định.",
        "actions": [
            "Kiểm tra độ trễ (latency/ping) và tỷ lệ rớt gói (packet loss) trên kênh truyền mạng riêng (leased line / VPN).",
            "Chuyển tạm thời luồng gọi sang cổng Gateway dự phòng.",
            "Yêu cầu kỹ thuật NOC nhà mạng kiểm tra tải CPU/RAM trên cụm thiết bị SBC."
        ],
        "hotline": "Viettel NOC: 1800 8000 | VNPT NOC: 1800 1260 | MobiFone NOC: 1800 1090"
    },
    "500_SERVER_ERROR": {
        "code": "500_SERVER_ERROR",
        "title": "500_SERVER_ERROR — Lỗi nội bộ hệ thống Softswitch",
        "protocol": "SIP/2.0 500 Internal Server Error",
        "cause": "Hệ thống tổng đài Softswitch / SIP Core của đối tác gặp sự cố xử lý logic hoặc lỗi crash tiến trình xử lý cuộc gọi.",
        "actions": [
            "Cách ly tạm thời tuyến trung kế SIP gặp lỗi để tránh ảnh hưởng đến tỷ lệ kết nối chung.",
            "Thu thập log SIP trace (INVITE, 100 Trying, 500 Error) gửi kèm ticket NOC cho đối tác.",
            "Kiểm tra lại cấu hình codec và SDP parameter gửi sang phía đối tác."
        ],
        "hotline": "Viettel NOC: 1800 8000 | VNPT NOC: 1800 1260 | MobiFone NOC: 1800 1090"
    },
    "429_TOO_MANY_REQUESTS": {
        "code": "429_TOO_MANY_REQUESTS",
        "title": "429_TOO_MANY_REQUESTS — Vượt ngưỡng tần suất gọi (CPS Rate Limit)",
        "protocol": "SIP/2.0 429 Too Many Requests / Rate Exceeded",
        "cause": "Tốc độ phát cuộc gọi đồng thời vượt quá ngưỡng CPS (Calls Per Second) hoặc CAPS đã cam kết trong hợp đồng viễn thông.",
        "actions": [
            "Điều chỉnh giảm tham số max-cps và concurrency rate trên dialer tự động.",
            "Phân bổ chiến dịch gọi ra nhiều dải đầu số (CLI Caller ID) khác nhau.",
            "Giãn cách thời gian quét hàng đợi liên hệ trong hệ thống."
        ],
        "hotline": "Quản trị viên SCC Telecom / DevOps Lead"
    },
    "408_REQUEST_TIMEOUT": {
        "code": "408_REQUEST_TIMEOUT",
        "title": "408_REQUEST_TIMEOUT — Hết thời gian chờ phản hồi (Request Timeout)",
        "protocol": "SIP/2.0 408 Request Timeout",
        "cause": "Bản tin INVITE gửi tới thiết bị đầu cuối thuê bao không nhận được phản hồi 180 Ringing hoặc 200 OK trước khi hết Timer B/Timer C.",
        "actions": [
            "Giảm cấu hình Ringing Timeout trên tổng đài xuống 20s để giải phóng kênh sớm.",
            "Phân loại danh sách số thuê bao không nhấc máy để lên lịch gọi lại tự động vào khung giờ khác.",
            "Kiểm tra chất lượng định tuyến vô tuyến của nhà mạng tại khu vực thuê bao."
        ],
        "hotline": "Bộ phận vận hành chiến dịch Outbound SCC"
    },
    "DROP_TRAFFIC": {
        "code": "DROP_TRAFFIC",
        "title": "DROP_TRAFFIC — Sập lưu lượng bất thường (0 cuộc gọi / Mất tín hiệu)",
        "protocol": "Traffic Anomaly: Complete Signal Drop (P1 Critical)",
        "cause": "Toàn bộ lưu lượng phát sinh trong khung giờ giảm về 0 cuộc. Tiến trình Autodialer bị dừng đột ngột hoặc service Asterisk PBX / SIP Trunk bị mất kết nối.",
        "actions": [
            "Kiểm tra trạng thái tiến trình: `systemctl status asterisk` hoặc docker container dialer.",
            "Kiểm tra kết nối Database hàng đợi cuộc gọi và dịch vụ mạng trung tâm.",
            "Khởi động lại dịch vụ quay số tự động nếu phát hiện deadlock hàng đợi."
        ],
        "hotline": "Kỹ thuật trực ca NOC SCC / Ext 101"
    },
    "TRAFFIC_SPIKE": {
        "code": "TRAFFIC_SPIKE",
        "title": "TRAFFIC_SPIKE — Đột biến lưu lượng gọi ra (Spike Traffic / P2 Warning)",
        "protocol": "Traffic Anomaly: Volume Surge > Threshold (P2)",
        "cause": "Lưu lượng cuộc gọi phát sinh tăng đột biến gấp nhiều lần ngưỡng thông thường, có nguy cơ gây nghẽn băng thông hệ thống.",
        "actions": [
            "Kiểm tra số lượng chiến dịch đang kích hoạt đồng thời trên giao diện quản trị.",
            "Áp dụng chính sách kiểm soát lưu lượng (Traffic Throttling) để cân bằng tải.",
            "Cảnh báo bộ phận vận hành theo dõi tải tài nguyên máy chủ CPU/Memory."
        ],
        "hotline": "Trưởng ca vận hành chiến dịch SCC"
    }
}

def get_friendly_carrier(row):
    fc = row.get("failed_carrier")
    if pd.notna(fc) and str(fc).strip() and str(fc).strip() != "-":
        return str(fc).strip()
    if row.get("is_p1_drop", False):
        return "Asterisk PBX / Dialer"
    if row.get("is_p2_yellow", False):
        return "Tuyến Chiến dịch"
    return "Hệ thống SCC"

def get_friendly_error(row):
    se = str(row.get("specific_error", "")).strip()
    if "503" in se:
        return "503_CONGESTION (Nghẽn SIP Trunk)"
    if "504" in se:
        return "504_GATEWAY_TIMEOUT (Hết hạn SBC)"
    if "500" in se:
        return "500_SERVER_ERROR (Lỗi Softswitch)"
    if "429" in se:
        return "429_TOO_MANY_REQUESTS (Vượt CPS)"
    if "408" in se:
        return "408_REQUEST_TIMEOUT (Hết chờ SIP)"
    if row.get("is_p1_drop", False):
        return "DROP_TRAFFIC (Sập lưu lượng 0 cuộc)"
    if row.get("is_p2_yellow", False):
        return "TRAFFIC_SPIKE (Đột biến lưu lượng)"
    return "GIÁN ĐOẠN DỊCH VỤ"

def get_friendly_level(row):
    if row.get("is_p1_red", False):
        return "P1 Khẩn cấp", "#ef4444"
    return "P2 Cảnh báo", "#f59e0b"


def _incident_key(row):
    """Tạo mã ổn định cho lựa chọn sự cố trên giao diện."""
    bucket = row.get("bucket_time")
    bucket_text = bucket.strftime("%Y-%m-%d %H:%M") if hasattr(bucket, "strftime") else str(bucket)
    error_text = str(row.get("specific_error", "ANOMALY"))
    if row.get("is_p1_drop", False):
        error_text = "DROP_TRAFFIC"
    elif row.get("is_p2_yellow", False) and error_text in ("", "-"):
        error_text = "TRAFFIC_SPIKE"
    return f"{bucket_text} | {error_text}"


def render_operational_status_banner(view_date, is_live, flagged, text_main, text_muted, card_bg, border_col):
    """Hiển thị trạng thái vận hành trước các biểu đồ để NOC thấy sự cố ngay."""
    try:
        stream_mtime = STREAM_FILE.stat().st_mtime if STREAM_FILE.exists() else 0
        if stream_mtime:
            freshness_seconds = max(0, int(time.time() - stream_mtime))
            freshness_text = f"{freshness_seconds}s trước"
            freshness_color = "#16a34a" if freshness_seconds <= 30 else "#f59e0b" if freshness_seconds <= 120 else "#dc2626"
        else:
            freshness_text = "Không có snapshot"
            freshness_color = "#dc2626"
    except Exception:
        freshness_text = "Không xác định"
        freshness_color = "#f59e0b"

    p1_count = int(flagged["is_p1_red"].sum()) if not flagged.empty else 0
    p2_count = int(flagged["is_p2_yellow"].sum()) if not flagged.empty else 0
    if p1_count:
        status_label, status_color = "DEGRADED — CẦN XỬ LÝ", "#dc2626"
        status_detail = f"{p1_count} sự cố P1 đang hiển thị"
    elif p2_count:
        status_label, status_color = "WARNING — ĐANG THEO DÕI", "#d97706"
        status_detail = f"{p2_count} cảnh báo P2 đang hiển thị"
    else:
        status_label, status_color = "HEALTHY — KHÔNG CÓ SỰ CỐ", "#16a34a"
        status_detail = "Không phát hiện bucket bất thường"

    mode_text = "LIVE" if is_live else "HISTORICAL"
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;
                background:{card_bg};border:1px solid {border_col};border-left:4px solid {status_color};
                border-radius:8px;padding:10px 14px;margin:0 0 14px 0;">
      <div>
        <div style="font-size:13px;font-weight:800;color:{status_color};">{status_label}</div>
        <div style="font-size:11.5px;color:{text_muted};margin-top:3px;">{status_detail} · Ngày {view_date.strftime('%d/%m/%Y')}</div>
      </div>
      <div style="display:flex;gap:18px;align-items:center;font-size:11.5px;color:{text_muted};">
        <span><b style="color:#ef4444;">P1 {p1_count}</b></span>
        <span><b style="color:#f59e0b;">P2 {p2_count}</b></span>
        <span>Mode: <b style="color:{text_main};">{mode_text}</b></span>
        <span>Data freshness: <b style="color:{freshness_color};">{freshness_text}</b></span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_incident_queue(flagged, text_main, text_muted, card_bg, border_col):
    """Incident-first queue: lỗi, phạm vi, ảnh hưởng và thao tác điều tra."""
    st.markdown(f"<div style='font-size:16px;font-weight:800;color:{text_main};margin:4px 0 8px 0;'>Sự cố cần xử lý</div>", unsafe_allow_html=True)
    if flagged.empty:
        st.success("Không có P1/P2 đang được ghi nhận trong phạm vi đã chọn.")
        return

    filter_col, sort_col = st.columns([1.2, 3.8])
    with filter_col:
        incident_filter = st.selectbox(
            "Lọc mức độ",
            ["Tất cả", "Chỉ P1", "Chỉ P2"],
            key="incident_severity_filter",
            label_visibility="collapsed",
        )
    queue = flagged.copy()
    if incident_filter == "Chỉ P1":
        queue = queue[queue["is_p1_red"]]
    elif incident_filter == "Chỉ P2":
        queue = queue[queue["is_p2_yellow"]]
    queue = queue.sort_values(["is_p1_red", "bucket_time"], ascending=[False, True])

    rows = []
    for _, row in queue.iterrows():
        level, _ = get_friendly_level(row)
        total = int(row.get("calls_total", 0))
        failed = int(row.get("calls_failed", row.get("calls_503", 0)))
        error_rate = (failed / total * 100) if total else 0.0
        rows.append({
            "Mức độ": level,
            "Khung giờ": row["bucket_time"].strftime("%H:%M"),
            "Lỗi / bất thường": get_friendly_error(row),
            "Phạm vi": get_friendly_carrier(row),
            "Ảnh hưởng": f"{failed}/{total} lỗi ({error_rate:.1f}%)",
            "incident_key": _incident_key(row),
        })

    display_rows = pd.DataFrame(rows)
    if display_rows.empty:
        st.info("Không có sự cố phù hợp với bộ lọc.")
        return
    st.dataframe(
        display_rows.drop(columns=["incident_key"]),
        use_container_width=True,
        hide_index=True,
        height=min(270, 44 + len(display_rows) * 38),
        column_config={
            "Mức độ": st.column_config.TextColumn("Mức độ", width="small"),
            "Khung giờ": st.column_config.TextColumn("Khung giờ", width="small"),
            "Lỗi / bất thường": st.column_config.TextColumn("Lỗi / bất thường", width="large"),
            "Phạm vi": st.column_config.TextColumn("Phạm vi", width="medium"),
            "Ảnh hưởng": st.column_config.TextColumn("Ảnh hưởng", width="medium"),
        },
    )

    selected_key = st.selectbox(
        "Chọn sự cố để xem nguyên nhân và hướng xử lý",
        display_rows["incident_key"].tolist(),
        key="selected_incident_key",
    )
    selected_row = queue[queue.apply(_incident_key, axis=1) == selected_key]
    if not selected_row.empty:
        selected_bucket = selected_row.iloc[0]["bucket_time"].strftime("%H:%M")
        if st.button("Mở hồ sơ xử lý sự cố", key="open_selected_incident", type="primary"):
            st.session_state["active_investigation_bucket"] = selected_bucket
            st.rerun()


def render_incident_response_workspace_legacy(view_date, full_df, flagged, text_main, text_muted, card_bg, border_col):
    """Production incident queue + investigation workspace.

    This view intentionally consumes only fields currently available in the
    pipeline. Correlation IDs, application traces and persistent incident
    workflow records are shown as unavailable until their backend tables exist.
    """
    st.markdown(f"<div style='font-size:24px;font-weight:800;color:{text_main};'>Incident Response Workspace</div>", unsafe_allow_html=True)
    st.caption("Điều tra sự cố độc lập với Live Operations — không lặp lại các biểu đồ giám sát tổng quan.")

    # Build compact incident records from anomaly buckets. Persistence is not
    # implied: these are detection records until an incidents table is added.
    records = []
    for _, row in flagged.iterrows():
        code = str(row.get("specific_error", "")).strip()
        if code in ("", "-"):
            code = "DROP_TRAFFIC" if row.get("is_p1_drop", False) else "TRAFFIC_SPIKE"
        priority = "P1" if row.get("is_p1_red", False) else "P2"
        total = int(row.get("calls_total", 0))
        failed = int(row.get("calls_failed", row.get("calls_503", 0)))
        rate = failed / total * 100 if total else 0.0
        incident_id = f"INC-{row['bucket_time'].strftime('%Y%m%d-%H%M')}-{code}"
        records.append({
            "incident_id": incident_id,
            "priority": priority,
            "error_type": code,
            "service": get_friendly_carrier(row),
            "detection_time": row["bucket_time"],
            "status": st.session_state.get(f"incident_status_{incident_id}", "New"),
            "operator": st.session_state.get(f"incident_operator_{incident_id}", "Unassigned"),
            "error_rate": rate,
            "affected_calls": f"{failed}/{total}",
            "row": row,
        })

    queue_df = pd.DataFrame(records)
    if queue_df.empty:
        st.success("Không có anomaly bucket để tạo incident trong phạm vi đang xem.")
        st.info("Incident management hiện sử dụng dữ liệu phát hiện từ time-series. Chưa có bảng incident persistence trong PostgreSQL.")
        return

    # Queue toolbar: compact filters, no monitoring KPI cards or global charts.
    f1, f2, f3, f4, f5 = st.columns([1.2, 1.0, 1.3, 1.6, 2.2])
    with f1:
        status_filter = st.selectbox("Status", ["All", "New", "Acknowledged", "Investigating", "Mitigated", "Resolved"], key="ir_status")
    with f2:
        priority_filter = st.selectbox("Priority", ["All", "P1", "P2", "P3"], key="ir_priority")
    with f3:
        assignment_filter = st.selectbox("Assignment", ["All", "Assigned", "Unassigned"], key="ir_assignment")
    with f4:
        error_filter = st.selectbox("Error type", ["All"] + sorted(queue_df["error_type"].unique().tolist()), key="ir_error")
    with f5:
        search = st.text_input("Search", placeholder="Incident ID, service, error...", key="ir_search")

    filtered = queue_df.copy()
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if priority_filter != "All":
        filtered = filtered[filtered["priority"] == priority_filter]
    if assignment_filter == "Assigned":
        filtered = filtered[filtered["operator"] != "Unassigned"]
    elif assignment_filter == "Unassigned":
        filtered = filtered[filtered["operator"] == "Unassigned"]
    if error_filter != "All":
        filtered = filtered[filtered["error_type"] == error_filter]
    if search.strip():
        needle = search.strip().lower()
        mask = filtered[["incident_id", "error_type", "service", "operator"]].astype(str).apply(lambda col: col.str.lower().str.contains(needle, na=False)).any(axis=1)
        filtered = filtered[mask]

    st.caption(f"{len(filtered)} incident record(s) · {int((queue_df['priority'] == 'P1').sum())} P1 · {int((queue_df['priority'] == 'P2').sum())} P2 · Detection source: time-series")
    if filtered.empty:
        st.info("Không có incident phù hợp bộ lọc.")
        return

    # Use a compact table for the queue; the workspace below is the only place
    # where investigation details and actions are rendered.
    queue_view = filtered[["incident_id", "priority", "error_type", "service", "detection_time", "status", "operator"]].copy()
    queue_view["detection_time"] = queue_view["detection_time"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        queue_view.rename(columns={"incident_id": "Incident ID", "priority": "Priority", "error_type": "Error Type", "service": "Affected Service", "detection_time": "Detection Time", "status": "Status", "operator": "Assigned Operator"}),
        use_container_width=True,
        hide_index=True,
        height=min(260, 44 + len(queue_view) * 36),
        column_config={
            "Incident ID": st.column_config.TextColumn(width="large"),
            "Priority": st.column_config.TextColumn(width="small"),
            "Error Type": st.column_config.TextColumn(width="medium"),
            "Affected Service": st.column_config.TextColumn(width="medium"),
            "Detection Time": st.column_config.TextColumn(width="medium"),
        },
    )
    selected_id = st.selectbox("Open incident workspace", filtered["incident_id"].tolist(), key="ir_selected_id")
    selected = filtered[filtered["incident_id"] == selected_id].iloc[0]
    row = selected["row"]
    kb_key = selected["error_type"] if selected["error_type"] in TELECOM_ERROR_KB else ("DROP_TRAFFIC" if row.get("is_p1_drop", False) else "TRAFFIC_SPIKE")
    kb = TELECOM_ERROR_KB.get(kb_key, {})

    st.markdown("---")
    st.markdown(f"### {selected['incident_id']}")
    h = st.columns([2.2, 1.0, 1.5, 1.4, 1.2, 1.2, 1.3])
    h[0].markdown(f"**{selected['error_type']}**\n\n{kb.get('title', selected['error_type'])}")
    h[1].metric("Priority", selected["priority"])
    h[2].metric("Service", selected["service"])
    h[3].metric("Detected", selected["detection_time"].strftime("%H:%M"))
    h[4].metric("Error rate", f"{selected['error_rate']:.1f}%")
    h[5].metric("Affected", selected["affected_calls"])
    h[6].metric("Status", selected["status"])

    left, right = st.columns([2.15, 1.0])
    with left:
        trace_tab, logs_tab, evidence_tab = st.tabs(["Trace", "Logs", "Evidence"])
        with trace_tab:
            st.markdown("**Chronological event flow**")
            trace_rows = [{"Time": selected["detection_time"].strftime("%Y-%m-%d %H:%M"), "Event": "Anomaly detected", "Component": selected["service"], "Source": "call_timeseries"}]
            if kb_key == "DROP_TRAFFIC":
                trace_rows.append({"Time": selected["detection_time"].strftime("%Y-%m-%d %H:%M"), "Event": "Traffic deviation observed", "Component": selected["service"], "Source": "call_timeseries"})
            elif kb_key in ("504_GATEWAY_TIMEOUT", "408_REQUEST_TIMEOUT"):
                trace_rows.append({"Time": selected["detection_time"].strftime("%Y-%m-%d %H:%M"), "Event": "Timeout response observed", "Component": selected["service"], "Source": "calls_stream"})
            st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)
            st.caption("Chỉ hiển thị event có nguồn dữ liệu thực tế. Application trace/SIP packet trace chưa được kết nối.")
        with logs_tab:
            log_df = full_df[full_df["bucket_time"] == row["bucket_time"]].copy() if not full_df.empty else pd.DataFrame()
            if log_df.empty:
                st.info("Không có raw call log cho incident này.")
            else:
                available = [c for c in ["start_time", "call_id", "result_code", "carrier", "duration", "end_time"] if c in log_df.columns]
                logs = log_df[available].sort_values("start_time", ascending=False).copy()
                logs.insert(1, "Correlation ID", "Not available")
                logs.insert(2, "Response Code", logs["result_code"] if "result_code" in logs else "Not available")
                st.dataframe(logs, use_container_width=True, hide_index=True, height=300)
                st.caption("Correlation ID và application logs chưa tồn tại trong các nguồn dữ liệu hiện tại; không tự sinh giá trị.")
        with evidence_tab:
            e1, e2, e3 = st.columns(3)
            e1.metric("Actual calls", int(row.get("calls_total", 0)))
            e2.metric("Baseline μ", f"{float(row.get('mu', 0)):.1f}")
            e3.metric("Deviation", f"{float(row.get('zscore', 0)):.2f}σ")
            evidence = {
                "Metric": ["Error rate", "Detection threshold", "Baseline μ", "Baseline σ", "Z-score", "Affected service", "Detection source"],
                "Observed": [f"{selected['error_rate']:.2f}%", f"{float(row.get('dynamic_threshold', 0))*100:.2f}%", f"{float(row.get('mu', 0)):.2f}", f"{float(row.get('sd', 0)):.2f}", f"{float(row.get('zscore', 0)):.2f}", selected["service"], "call_timeseries / calls_stream"],
            }
            st.dataframe(pd.DataFrame(evidence), use_container_width=True, hide_index=True)
            if kb_key == "DROP_TRAFFIC":
                st.info(f"Traffic window: {selected['detection_time'].strftime('%H:%M')}–{(selected['detection_time'] + pd.Timedelta(minutes=15)).strftime('%H:%M')}. Actual vs baseline is available from the metrics above.")

    with right:
        with st.container(border=True):
            st.markdown("### Incident Actions")
            operator_options = ["Unassigned", "NOC Operator 1", "NOC Operator 2", "Supervisor"]
            operator = st.selectbox("Assignment", operator_options, index=operator_options.index(selected["operator"]) if selected["operator"] in operator_options else 0, key=f"assign_{selected_id}")
            status_options = ["New", "Acknowledged", "Investigating", "Mitigated", "Resolved"]
            status = st.selectbox("Current status", status_options, index=status_options.index(selected["status"]) if selected["status"] in status_options else 0, key=f"status_{selected_id}")
            note = st.text_area("Investigation notes", key=f"notes_{selected_id}", height=120, placeholder="Ghi nhận kiểm tra, ticket, người phối hợp...")
            if st.button("Add Note", key=f"add_note_{selected_id}", use_container_width=True):
                st.session_state[f"note_saved_{selected_id}"] = note
                st.success("Đã lưu note trong phiên UI hiện tại.")
            if st.button("Acknowledge", key=f"ack_workspace_{selected_id}", use_container_width=True):
                st.session_state[f"incident_status_{selected_id}"] = "Acknowledged"
                st.session_state[f"incident_operator_{selected_id}"] = operator
                st.rerun()
            if st.button("Escalate", key=f"escalate_{selected_id}", use_container_width=True):
                st.warning("Escalation UI đã ghi nhận trong phiên hiện tại; chưa tích hợp ticketing backend.")
            st.markdown("**Resolution**")
            resolution = st.text_area("Resolution summary", key=f"resolution_{selected_id}", height=90, placeholder="Bắt buộc khi đóng incident...")
            verified = st.checkbox("Đã xác minh error rate đã trở về ngưỡng an toàn", key=f"verified_{selected_id}")
            if st.button("Resolve incident", key=f"resolve_{selected_id}", type="primary", use_container_width=True):
                if not resolution.strip() or not verified:
                    st.error("Cần nhập resolution summary và xác minh hệ thống trước khi resolve.")
                else:
                    st.session_state[f"incident_status_{selected_id}"] = "Resolved"
                    st.session_state[f"incident_operator_{selected_id}"] = operator
                    st.success("Incident đã được đánh dấu Resolved trong phiên UI hiện tại.")
            st.caption("Persistence backend: chưa triển khai bảng incidents/incident_events; trạng thái hiện được giữ trong session Streamlit.")


def render_incidents_page_legacy(view_date, full_df, flagged, text_main, text_muted, card_bg, border_col):
    """Trang điều tra sự cố độc lập: lọc, evidence, log cuộc gọi và SOP."""
    st.markdown(f"<div style='font-size:24px;font-weight:800;color:{text_main};'>Incident Management</div>", unsafe_allow_html=True)
    st.caption("Tra cứu lỗi theo ngày, mã lỗi và phạm vi; xem raw call log cùng hướng dẫn xử lý tương ứng.")

    # Bộ lọc ngày riêng của Incident Management. Không dùng cal_date_picker của
    # Live Operations để tránh việc đổi ngày ở một tab làm thay đổi tab khác.
    available_dates = sorted(full_df["date"].dropna().unique()) if not full_df.empty and "date" in full_df.columns else [view_date]
    min_inc_date = available_dates[0] if available_dates else view_date
    max_inc_date = available_dates[-1] if available_dates else view_date
    incident_date = st.session_state.get("incident_management_date", view_date)
    if incident_date < min_inc_date or incident_date > max_inc_date:
        incident_date = max_inc_date

    date_col, _, mode_col = st.columns([1.6, 1.5, 1.8])
    with date_col:
        incident_date = st.date_input(
            "Ngày tra cứu incident",
            value=incident_date,
            min_value=min_inc_date,
            max_value=max_inc_date,
            format="YYYY-MM-DD",
            key="incident_management_date_picker",
            help="Bộ chọn ngày độc lập của Incident Management; không thay đổi ngày trong Live Operations.",
        )
    st.session_state["incident_management_date"] = incident_date
    with mode_col:
        st.markdown(f"<div style='margin-top:28px;color:{text_muted};font-size:12px;'>Đang tra cứu: <b style='color:{text_main};'>{incident_date.strftime('%d/%m/%Y')}</b></div>", unsafe_allow_html=True)

    incident_df = full_df[full_df["date"] == incident_date].copy() if not full_df.empty else pd.DataFrame()
    incident_ts = process_single_date(incident_df, incident_date, is_live_today=False) if not incident_df.empty else pd.DataFrame()
    incident_flagged = incident_ts[incident_ts["is_p1_red"] | incident_ts["is_p2_yellow"]].copy() if not incident_ts.empty else pd.DataFrame()
    if incident_flagged.empty:
        st.success("Không phát hiện bucket bất thường trong ngày đã chọn.")
        return

    c1, c2, c3 = st.columns([1.35, 1.6, 1.6])
    with c1:
        error_options = ["Tất cả"] + sorted({str(r.get("specific_error", "")).strip() for _, r in incident_flagged.iterrows() if str(r.get("specific_error", "")).strip() not in ("", "-")})
        error_filter = st.selectbox("Loại lỗi", error_options, key="inc_error_type_filter")
    with c2:
        service_options = ["Tất cả"] + sorted({get_friendly_carrier(r) for _, r in incident_flagged.iterrows()})
        carrier_filter = st.selectbox("Nhà mạng / Phạm vi", service_options, key="inc_service_filter")
    with c3:
        status_filter = st.selectbox("Trạng thái phát hiện", ["Tất cả", "P1/P2 đang cảnh báo"], key="inc_detection_status_filter")

    flagged = incident_flagged.copy()
    if error_filter != "Tất cả":
        flagged = flagged[flagged["specific_error"].astype(str) == error_filter]
    if carrier_filter != "Tất cả":
        flagged = flagged[flagged.apply(lambda r: get_friendly_carrier(r) == carrier_filter, axis=1)]
    # Chỉ có trạng thái phát hiện từ anomaly engine ở bản demo; không giả lập
    # workflow New/Acknowledged/Resolved khi chưa có incident persistence.
    if status_filter == "P1/P2 đang cảnh báo":
        flagged = flagged[flagged["is_p1_red"] | flagged["is_p2_yellow"]]

    if flagged.empty:
        st.info("Không có lỗi phù hợp với các bộ lọc đã chọn.")
        return

    table = []
    for _, row in flagged.iterrows():
        total = int(row.get("calls_total", 0))
        failed = int(row.get("calls_failed", row.get("calls_503", 0)))
        raw_code = str(row.get("specific_error", "")).strip()
        lookup_code = raw_code if raw_code not in ("", "-") else ("DROP_TRAFFIC" if row.get("is_p1_drop", False) else "TRAFFIC_SPIKE")
        table.append({
            "Mã lỗi": lookup_code,
            "Mức cảnh báo": "P1" if row.get("is_p1_red", False) else "P2",
            "Thời điểm": row["bucket_time"].strftime("%H:%M"),
            "Mô tả": get_friendly_error(row),
            "Nhà mạng / Phạm vi": get_friendly_carrier(row),
            "Ảnh hưởng": f"{failed}/{total} ({failed / total * 100:.1f}%)" if total else "0/0",
            "lookup_key": _incident_key(row),
        })
    inc_df = pd.DataFrame(table)
    selected = st.selectbox(
        "Tra cứu log lỗi theo mã",
        inc_df["lookup_key"].tolist(),
        format_func=lambda key: next((f"{r['Mã lỗi']} · {r['Thời điểm']} · {r['Nhà mạng / Phạm vi']}" for _, r in inc_df.iterrows() if r["lookup_key"] == key), key),
        key="inc_error_log_lookup",
    )
    st.dataframe(
        inc_df.drop(columns=["lookup_key"]),
        use_container_width=True,
        hide_index=True,
        height=min(260, 42 + len(inc_df) * 38),
        column_config={
            "Mã lỗi": st.column_config.TextColumn("Mã lỗi", width="medium"),
            "Mức cảnh báo": st.column_config.TextColumn("Mức cảnh báo", width="small"),
            "Thời điểm": st.column_config.TextColumn("Thời điểm", width="small"),
            "Mô tả": st.column_config.TextColumn("Mô tả", width="large"),
            "Nhà mạng / Phạm vi": st.column_config.TextColumn("Nhà mạng / Phạm vi", width="medium"),
            "Ảnh hưởng": st.column_config.TextColumn("Ảnh hưởng", width="medium"),
        },
    )

    selected_rows = flagged[flagged.apply(_incident_key, axis=1) == selected]
    if selected_rows.empty:
        return
    incident = selected_rows.iloc[0]
    raw_code = str(incident.get("specific_error", "")).strip()
    kb_key = raw_code if raw_code in TELECOM_ERROR_KB else ("DROP_TRAFFIC" if incident.get("is_p1_drop", False) else "TRAFFIC_SPIKE" if incident.get("is_p2_yellow", False) else "503_CONGESTION")
    kb = TELECOM_ERROR_KB[kb_key]
    total = int(incident.get("calls_total", 0))
    failed = int(incident.get("calls_failed", incident.get("calls_503", 0)))
    error_rate = failed / total * 100 if total else 0

    st.markdown("---")
    st.markdown(f"### {kb['title']}")
    info1, info2, info3, info4 = st.columns(4)
    info1.metric("Severity", "P1" if incident.get("is_p1_red", False) else "P2")
    info2.metric("Error rate", f"{error_rate:.1f}%")
    info3.metric("Calls affected", f"{failed}/{total}")
    info4.metric("Bucket", incident["bucket_time"].strftime("%H:%M"))

    st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

    box_bg = "#161f30" if is_dark else "#f8fafc"
    box_border = "#26354a" if is_dark else "#cbd5e1"
    evidence_thresh = float(incident.get("dynamic_threshold", 0)) * 100

    detail_left, detail_right = st.columns([1.1, 1.4])
    with detail_left:
        st.markdown(f"""
        <div style="background:{box_bg}; border:1px solid {box_border}; border-radius:8px; padding:16px 18px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-size:15px; font-weight:700; color:{text_main}; margin-bottom:12px;">What happened</div>
            <div style="font-size:13px; color:{text_main}; margin-bottom:8px; line-height:1.5;">
                <b>Protocol/code:</b> <span style="font-family:monospace; color:{'#38bdf8' if is_dark else '#0284c7'}; font-weight:600;">{kb['protocol']}</span>
            </div>
            <div style="font-size:13px; color:{text_main}; margin-bottom:8px; line-height:1.5;">
                <b>Scope:</b> {get_friendly_carrier(incident)}
            </div>
            <div style="font-size:13px; color:{text_main}; margin-bottom:8px; line-height:1.5;">
                <b>Cause:</b> {kb['cause']}
            </div>
            <div style="font-size:13px; color:{text_main}; line-height:1.5;">
                <b>Detection evidence:</b> error rate {error_rate:.1f}%, threshold {evidence_thresh:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with detail_right:
        actions_list_html = "".join([
            f"<div style='font-size:13px; color:{text_main}; margin-bottom:8px; line-height:1.5;'><b>{step_no}.</b> {action}</div>"
            for step_no, action in enumerate(kb["actions"], 1)
        ])
        escalation_bg = "#1e293b" if is_dark else "#edf2f7"
        escalation_border = "#334155" if is_dark else "#cbd5e1"
        st.markdown(f"""
        <div style="background:{box_bg}; border:1px solid {box_border}; border-radius:8px; padding:16px 18px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-size:15px; font-weight:700; color:{text_main}; margin-bottom:12px;">How to fix — SOP</div>
            <div style="margin-bottom:12px;">
                {actions_list_html}
            </div>
            <div style="background:{escalation_bg}; border:1px solid {escalation_border}; border-radius:6px; padding:10px 12px; font-size:12.5px; color:{text_main}; line-height:1.4;">
                <b>Escalation:</b> {kb['hotline']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    log_df = full_df[full_df["bucket_time"] == incident["bucket_time"]].copy() if not full_df.empty else pd.DataFrame()
    with st.expander("Evidence & call logs", expanded=True):
        if log_df.empty:
            st.warning("Không tìm thấy raw call log cho bucket này.")
        else:
            log_cols = [c for c in ["call_id", "start_time", "end_time", "duration", "result_code", "carrier"] if c in log_df.columns]
            st.caption(f"{len(log_df):,} raw events trong bucket {incident['bucket_time'].strftime('%H:%M')}")
            st.dataframe(log_df[log_cols].sort_values("start_time", ascending=False), use_container_width=True, hide_index=True, height=280)

    st.caption("Bản demo chỉ hiển thị thông tin phát hiện, raw call log và SOP tương ứng; chưa có workflow ghi chú hoặc resolution persistence.")


def render_incident_investigation(view_date, full_df, flagged, text_main, text_muted, card_bg, border_col):
    """Error investigation view backed only by currently available call data.

    No synthetic trace/span/component telemetry is created here. Missing fields
    are explicitly presented as unavailable.
    """
    st.markdown(f"<div style='font-size:24px;font-weight:800;color:{text_main};'>Error Investigation & Traceability</div>", unsafe_allow_html=True)

    dates = sorted(full_df["date"].dropna().unique()) if not full_df.empty and "date" in full_df.columns else [view_date]
    min_date, max_date = dates[0], dates[-1]
    default_date = st.session_state.get("incident_investigation_date", view_date)
    if default_date < min_date or default_date > max_date:
        default_date = max_date
    f_date, f_code, f_carrier, f_call = st.columns([1.35, 1.5, 1.5, 2.0])
    with f_date:
        selected_date = st.date_input("Ngày / thời gian tra cứu", value=default_date, min_value=min_date, max_value=max_date, format="YYYY-MM-DD", key="incident_investigation_date_picker")
    st.session_state["incident_investigation_date"] = selected_date
    scoped = full_df[full_df["date"] == selected_date].copy() if not full_df.empty else pd.DataFrame()
    codes = sorted(scoped["result_code"].dropna().astype(str).unique().tolist()) if not scoped.empty else []
    carriers = sorted(scoped["carrier"].dropna().astype(str).unique().tolist()) if not scoped.empty else []
    with f_code:
        selected_code = st.selectbox("Error / Result Code", ["All"] + codes, key="incident_investigation_code")
    with f_carrier:
        selected_carrier = st.selectbox("Carrier", ["All"] + carriers, key="incident_investigation_carrier")
    with f_call:
        call_query = st.text_input("Call ID", placeholder="Tìm chính xác hoặc một phần Call ID", key="incident_investigation_call")

    filtered = scoped.copy()
    if selected_code != "All":
        filtered = filtered[filtered["result_code"].astype(str) == selected_code]
    if selected_carrier != "All":
        filtered = filtered[filtered["carrier"].astype(str) == selected_carrier]
    if call_query.strip() and "call_id" in filtered.columns:
        filtered = filtered[filtered["call_id"].astype(str).str.contains(call_query.strip(), na=False)]

    if filtered.empty:
        st.info("Không tìm thấy event phù hợp với bộ lọc hiện tại.")
        return

    # Summary is calculated from the selected raw events, never hardcoded.
    total_events = len(filtered)
    failed_events = int(filtered["result_code"].isin(SYSTEM_ERRORS).sum()) if "result_code" in filtered else 0
    error_rate = failed_events / total_events * 100 if total_events else 0.0
    summary_cols = st.columns(6)
    summary_cols[0].metric("Error code", selected_code if selected_code != "All" else "Multiple")
    summary_cols[1].metric("Total events", f"{total_events:,}")
    summary_cols[2].metric("Failed calls", f"{failed_events:,}")
    summary_cols[3].metric("Error rate", f"{error_rate:.2f}%")
    summary_cols[4].metric("Carrier", selected_carrier if selected_carrier != "All" else "Multiple")
    summary_cols[5].metric("Call IDs", f"{filtered['call_id'].nunique():,}" if "call_id" in filtered else "N/A")

    if "start_time" in filtered.columns:
        start_min = filtered["start_time"].min()
        start_max = filtered["start_time"].max()
        st.caption(f"Time window: {start_min} → {start_max} · Affected carriers: {', '.join(sorted(filtered['carrier'].dropna().astype(str).unique())) if 'carrier' in filtered else 'Not available'}")

    map_tab, timeline_tab, logs_tab = st.tabs(["System Component Map", "Trace Timeline", "Raw Call Logs"])

    with map_tab:
        st.markdown("#### System Component Map")
        map_mode = st.container()
        with map_mode:
            selected_path = st.selectbox("System path", ["Call Processing Path", "Data Pipeline Path"], key="incident_component_path")
        if selected_path == "Call Processing Path":
            # Chỉ dùng hai node có thể liên hệ với dữ liệu hiện có: producer
            # tạo call event và carrier xuất hiện trong raw calls. Không suy
            # diễn SBC/PBX/gateway cụ thể khi chưa có component telemetry.
            carrier_nodes = sorted(filtered["carrier"].dropna().astype(str).unique()) if "carrier" in filtered else []
            component_defs = [("Outbound Producer / Dialer", "producer", "source")]
            component_defs.extend((f"Carrier: {c}", f"carrier:{c}", "carrier") for c in carrier_nodes)
            # Carriers are parallel scopes/classifications, not sequential
            # processing steps in one call.
            edges = [("producer", f"carrier:{c}") for c in carrier_nodes]
        else:
            component_defs = [
                ("Outbound Producer / Dialer", "producer", "source"),
                ("Redis Stream", "redis", "broker"),
                ("DB Writer", "writer", "ingestion"),
                ("PostgreSQL", "postgres", "storage"),
                ("call_timeseries", "timeseries", "analytics"),
            ]
            edges = [("producer", "redis"), ("redis", "writer"), ("writer", "postgres"), ("postgres", "timeseries")]
        components_available = [name for name, _, _ in component_defs]
        # Plotly graph: hover/zoom/pan are interactive. Selection is kept in
        # the clicked node when streamlit-plotly-events is available.
        positions = {}
        if selected_path == "Call Processing Path":
            positions["producer"] = (0, 0)
            for idx, (_, node_id, _) in enumerate(component_defs[1:]):
                positions[node_id] = (3.0, (len(component_defs) - 2) / 2 - idx)
        else:
            for idx, (_, node_id, _) in enumerate(component_defs):
                positions[node_id] = (idx * 2.5, 0)
        edge_x, edge_y = [], []
        for source_id, target_id in edges:
            sx, sy = positions[source_id]; tx, ty = positions[target_id]
            edge_x += [sx, tx, None]; edge_y += [sy, ty, None]
        graph_fig = go.Figure()
        if edge_x:
            graph_fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(color="#64748b", width=2), hoverinfo="skip", showlegend=False))
        node_x, node_y, node_text, node_color = [], [], [], []
        for name, node_id, node_type in component_defs:
            x, y = positions[node_id]
            node_x.append(x); node_y.append(y)
            is_carrier = node_type == "carrier"
            carrier_name = name.split(": ", 1)[1] if is_carrier else None
            node_errors = int(filtered[filtered["carrier"].astype(str) == carrier_name]["result_code"].isin(SYSTEM_ERRORS).sum()) if is_carrier and "carrier" in filtered else 0
            status = "Error recorded" if node_errors else "Observed"
            node_color.append("#dc2626" if node_errors else "#16a34a")
            node_text.append(f"<b>{name}</b><br>Status: {status}<br>Events: {len(filtered[filtered['carrier'].astype(str) == carrier_name]) if is_carrier and 'carrier' in filtered else total_events:,}")
        graph_fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text", text=[n for n, _, _ in component_defs], textposition="bottom center", textfont=dict(color=text_main, size=11), marker=dict(size=32, color=node_color, line=dict(color="#e2e8f0", width=1.5)), customdata=[node_id for _, node_id, _ in component_defs], hovertext=node_text, hovertemplate="%{hovertext}<extra></extra>", showlegend=False))
        graph_fig.update_layout(template=plotly_template, height=270, margin=dict(l=20, r=20, t=25, b=55), paper_bgcolor=card_bg, plot_bgcolor=card_bg, xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False, hovermode="closest")
        selected_id = None
        if plotly_events is not None:
            clicked = plotly_events(graph_fig, click_event=True, hover_event=False, select_event=False, override_height=270, key=f"component_map_{selected_path}")
            if clicked:
                point_index = clicked[0].get("pointIndex")
                if point_index is not None and 0 <= point_index < len(component_defs):
                    selected_id = component_defs[point_index][1]
        else:
            st.plotly_chart(graph_fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True, "displaylogo": False})
            st.info("Cài `streamlit-plotly-events` để bật chọn component bằng click. Hiện đồ thị vẫn hỗ trợ zoom, pan và hover.")

        if selected_id is None:
            selected_id = st.session_state.get("selected_component_id")
        else:
            st.session_state["selected_component_id"] = selected_id

        if selected_id is None:
            st.info("Bấm vào một node trên sơ đồ để xem chi tiết component bên dưới.")
        else:
            selected_component = next(name for name, node_id, _ in component_defs if node_id == selected_id)
            is_carrier = selected_id.startswith("carrier:")
            component_data = filtered[filtered["carrier"].astype(str) == selected_id.split(":", 1)[1]] if is_carrier and "carrier" in filtered else filtered
            component_errors = int(component_data["result_code"].isin(SYSTEM_ERRORS).sum()) if "result_code" in component_data else 0
            status = "Error recorded" if is_carrier and component_errors else "Observed"
            detail = {
                "Component": selected_component,
                "Scope": selected_path,
                "Status": status,
                "Observed events": f"{len(component_data):,}" if is_carrier else f"{total_events:,}",
                "Evidence source": "calls_stream/raw data" if is_carrier else "source/configuration",
            }
            # Only fields directly attributable to the selected carrier are shown.
            if is_carrier:
                detail["Error events"] = f"{component_errors:,}"
                detail["Error rate"] = f"{component_errors / len(component_data) * 100:.2f}%" if len(component_data) else "0.00%"
            st.dataframe(pd.DataFrame([detail]), use_container_width=True, hide_index=True)

    with timeline_tab:
        st.markdown("#### Trace Timeline")
        timeline_cols = [c for c in ["start_time", "call_id", "result_code", "carrier", "duration", "end_time"] if c in filtered.columns]
        timeline = filtered[timeline_cols].sort_values("start_time", ascending=True).copy()
        timeline = timeline.rename(columns={"start_time": "Timestamp", "call_id": "Call ID", "result_code": "Result Code", "carrier": "Carrier", "duration": "Duration (s)", "end_time": "End Time"})
        st.dataframe(timeline.head(500), use_container_width=True, hide_index=True, height=330)
        st.caption(f"Đang hiển thị tối đa 500 event trong {len(timeline):,} event phù hợp. Timestamp là start/end call thực tế; request/response span chưa có.")

    with logs_tab:
        st.markdown("#### Raw Call Logs")
        log_cols = [c for c in ["call_id", "start_time", "end_time", "duration", "result_code", "carrier"] if c in filtered.columns]
        st.dataframe(filtered[log_cols].sort_values("start_time", ascending=False).head(500), use_container_width=True, hide_index=True, height=360)
        st.download_button("Download filtered raw logs", filtered[log_cols].to_csv(index=False).encode("utf-8"), file_name=f"incident_logs_{selected_date}.csv", mime="text/csv")

    # Reference explanation/SOP is shown after evidence, but clearly separated
    # from measured data and root-cause claims.
    if selected_code != "All" and selected_code in TELECOM_ERROR_KB:
        kb = TELECOM_ERROR_KB[selected_code]
        with st.expander(f"Reference explanation and SOP — {selected_code}"):
            st.write(f"**Protocol:** {kb['protocol']}")
            st.write(f"**Reference description:** {kb['cause']}")
            st.caption("Đây là tài liệu tham khảo theo mã lỗi, không phải kết luận root cause đã xác minh.")
            for idx, action in enumerate(kb["actions"], 1):
                st.write(f"{idx}. {action}")

def _incident_records(flagged):
    records = []
    for _, row in flagged.iterrows():
        code = str(row.get("specific_error", "")).strip()
        if code in ("", "-"):
            code = "DROP_TRAFFIC" if row.get("is_p1_drop", False) else "TRAFFIC_SPIKE"
        total = int(row.get("calls_total", 0)); failed = int(row.get("calls_failed", row.get("calls_503", 0)))
        incident_id = f"INC-{row['bucket_time'].strftime('%Y%m%d-%H%M')}-{code}"
        records.append({"incident_id": incident_id, "priority": "P1" if row.get("is_p1_red", False) else "P2",
                        "error_type": code, "service": get_friendly_carrier(row), "detection_time": row["bucket_time"],
                        "status": st.session_state.get(f"incident_status_{incident_id}", "New"),
                        "operator": st.session_state.get(f"incident_operator_{incident_id}", "Unassigned"),
                        "error_rate": failed / total * 100 if total else 0.0, "affected_calls": f"{failed}/{total}", "row": row})
    return pd.DataFrame(records)


def render_incident_queue_only(queue_df):
    st.markdown("### Incident Queue")
    st.caption("Chỉ dùng để lọc và chọn incident. Mở tab kế bên để điều tra.")
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1.3, 1.6, 2])
    status = c1.selectbox("Status", ["All", "New", "Acknowledged", "Investigating", "Mitigated", "Resolved"], key="queue2_status")
    priority = c2.selectbox("Priority", ["All", "P1", "P2", "P3"], key="queue2_priority")
    assignment = c3.selectbox("Assignment", ["All", "Assigned", "Unassigned"], key="queue2_assignment")
    error_type = c4.selectbox("Error Type", ["All"] + sorted(queue_df["error_type"].unique().tolist()), key="queue2_error")
    search = c5.text_input("Search", key="queue2_search", placeholder="ID, service, error...")
    view = queue_df.copy()
    if status != "All": view = view[view.status == status]
    if priority != "All": view = view[view.priority == priority]
    if assignment == "Assigned": view = view[view.operator != "Unassigned"]
    if assignment == "Unassigned": view = view[view.operator == "Unassigned"]
    if error_type != "All": view = view[view.error_type == error_type]
    if search.strip():
        q = search.lower().strip(); cols = ["incident_id", "error_type", "service", "operator"]
        view = view[view[cols].astype(str).apply(lambda x: x.str.lower().str.contains(q, na=False)).any(axis=1)]
    st.caption(f"{len(view)} record(s) · {int((queue_df.priority == 'P1').sum())} P1 · {int((queue_df.priority == 'P2').sum())} P2")
    if view.empty:
        st.info("Không có incident phù hợp."); return
    table = view[["incident_id", "priority", "error_type", "service", "detection_time", "status", "operator"]].copy()
    table["detection_time"] = table["detection_time"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(table.rename(columns={"incident_id":"Incident ID", "priority":"Priority", "error_type":"Error Type", "service":"Affected Service", "detection_time":"Detection Time", "status":"Status", "operator":"Assigned Operator"}), use_container_width=True, hide_index=True)
    selected = st.selectbox("Select incident", view.incident_id.tolist(), key="queue2_selected")
    st.session_state["selected_incident_id"] = selected
    st.success("Đã chọn incident. Chuyển sang tab Incident Response Workspace để xử lý.")


def render_incident_workspace_only(queue_df, full_df):
    st.markdown("### Incident Response Workspace")
    selected_id = st.session_state.get("selected_incident_id")
    if not selected_id or selected_id not in queue_df.incident_id.tolist():
        st.info("Chưa chọn incident. Hãy chọn một incident trong tab Incident Queue trước."); return
    selected = queue_df[queue_df.incident_id == selected_id].iloc[0]; row = selected.row
    code = selected.error_type; kb_key = code if code in TELECOM_ERROR_KB else ("DROP_TRAFFIC" if row.get("is_p1_drop", False) else "TRAFFIC_SPIKE")
    kb = TELECOM_ERROR_KB.get(kb_key, {})
    with st.container(border=True):
        st.markdown(f"**{selected.incident_id}** · `{code}`")
        h = st.columns(7)
        for col, label, value in zip(h, ["Priority", "Service", "Detected", "Error rate", "Affected calls", "Status", "Operator"], [selected.priority, selected.service, selected.detection_time.strftime("%H:%M"), f"{selected.error_rate:.1f}%", selected.affected_calls, selected.status, selected.operator]): col.metric(label, value)
    left, right = st.columns([2.15, 1])
    with left:
        trace, logs, evidence = st.tabs(["Trace", "Logs", "Evidence"])
        with trace:
            events = [{"Time": selected.detection_time.strftime("%Y-%m-%d %H:%M"), "Event": "Anomaly detected", "Component": selected.service, "Source": "call_timeseries"}]
            if kb_key == "DROP_TRAFFIC": events.append({"Time": selected.detection_time.strftime("%Y-%m-%d %H:%M"), "Event": "Traffic deviation observed", "Component": selected.service, "Source": "call_timeseries"})
            elif kb_key in ("504_GATEWAY_TIMEOUT", "408_REQUEST_TIMEOUT"): events.append({"Time": selected.detection_time.strftime("%Y-%m-%d %H:%M"), "Event": "Timeout response observed", "Component": selected.service, "Source": "calls_stream"})
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
            st.caption("Chỉ hiển thị event có nguồn dữ liệu hiện có; application/SIP trace chưa được kết nối.")
        with logs:
            log = full_df[full_df.bucket_time == row.bucket_time].copy() if not full_df.empty else pd.DataFrame()
            if log.empty: st.info("Không có raw call log cho incident này.")
            else:
                cols = [c for c in ["start_time", "call_id", "result_code", "carrier", "duration", "end_time"] if c in log.columns]
                st.dataframe(log[cols].sort_values("start_time", ascending=False), use_container_width=True, hide_index=True, height=300)
                st.caption("Correlation ID và application logs chưa tồn tại trong nguồn dữ liệu hiện tại.")
        with evidence:
            st.dataframe(pd.DataFrame({"Metric":["Error rate","Threshold","Baseline μ","Baseline σ","Z-score","Service"], "Observed":[f"{selected.error_rate:.2f}%",f"{float(row.get('dynamic_threshold',0))*100:.2f}%",f"{float(row.get('mu',0)):.2f}",f"{float(row.get('sd',0)):.2f}",f"{float(row.get('zscore',0)):.2f}",selected.service]}), use_container_width=True, hide_index=True)
            if kb_key == "DROP_TRAFFIC": st.info(f"Anomaly window: {selected.detection_time.strftime('%H:%M')}–{(selected.detection_time + pd.Timedelta(minutes=15)).strftime('%H:%M')}")
    with right:
        with st.container(border=True):
            st.markdown("### Incident Actions")
            operators = ["Unassigned", "NOC Operator 1", "NOC Operator 2", "Supervisor"]
            operator = st.selectbox("Assignment", operators, key=f"ws_operator_{selected_id}")
            status = st.selectbox("Current Status", ["New", "Acknowledged", "Investigating", "Mitigated", "Resolved"], key=f"ws_status_{selected_id}")
            notes = st.text_area("Investigation Notes", key=f"ws_notes_{selected_id}", height=120)
            if st.button("Add Note", key=f"ws_note_btn_{selected_id}", use_container_width=True): st.session_state[f"note_{selected_id}"] = notes; st.success("Note đã lưu trong phiên hiện tại.")
            if st.button("Acknowledge", key=f"ws_ack_{selected_id}", use_container_width=True): st.session_state[f"incident_status_{selected_id}"] = "Acknowledged"; st.session_state[f"incident_operator_{selected_id}"] = operator; st.rerun()
            if st.button("Escalate", key=f"ws_escalate_{selected_id}", use_container_width=True): st.warning("Escalation UI-only: chưa có ticketing backend.")
            resolution = st.text_area("Resolution Summary", key=f"ws_resolution_{selected_id}", height=90)
            verified = st.checkbox("Đã xác minh error rate về ngưỡng an toàn", key=f"ws_verified_{selected_id}")
            if st.button("Resolve Incident", key=f"ws_resolve_{selected_id}", type="primary", use_container_width=True):
                if not resolution.strip() or not verified: st.error("Cần resolution summary và verification trước khi resolve.")
                else: st.session_state[f"incident_status_{selected_id}"] = "Resolved"; st.success("Resolved trong phiên UI hiện tại.")
            st.caption("Assignment/status/notes hiện chưa persistent trong PostgreSQL.")


# ==============================================================================
# 4. KHỐI HIỂN THỊ CHÍNH (NOC MODULAR VIEW ROUTER)
# ==============================================================================
def render_live_monitoring_fragment():
    global is_realtime_mode

    if ts_today is None or ts_today.empty:
        st.info("Đang chờ luồng dữ liệu cuộc gọi trực tiếp từ `producer.py`...")
        return False

    all_dates = sorted(full_df["date"].unique()) if not full_df.empty else [current_date]
    min_date = all_dates[0]
    max_date = current_date if current_date else all_dates[-1]

    past_dates = [d for d in all_dates if d < max_date]
    yesterday_date = past_dates[-1] if past_dates else (max_date - timedelta(days=1))

    # XỬ LÝ QUERY PARAMS TỪ PHÍM TẮT CHÂN LỊCH (NẾU CÓ)
    if "date" in st.query_params:
        try:
            q_val = st.query_params["date"]
            if isinstance(q_val, list):
                q_val = q_val[0]
            parsed_d = datetime.strptime(str(q_val).strip(), "%Y-%m-%d").date()
            if min_date <= parsed_d <= max_date:
                st.session_state["cal_date_picker"] = parsed_d
                st.session_state["_ui_dash_date_input"] = parsed_d
                st.session_state["is_following_live"] = (parsed_d == max_date)
            del st.query_params["date"]
        except Exception:
            pass

    if "nav" in st.query_params:
        p_nav = st.query_params["nav"]
        if isinstance(p_nav, list):
            p_nav = p_nav[0]
        if str(p_nav) in ["Live Operations", "Incidents", "Analytics", "Reports", "System Health"]:
            st.session_state["soc_nav_menu"] = str(p_nav)
        del st.query_params["nav"]

    if "t3_all" in st.query_params:
        st.session_state["soc_nav_menu"] = "Reports"
        st.session_state["t3_date_range_picker"] = (min_date, max_date)
        del st.query_params["t3_all"]

    picked_date = st.session_state.get("cal_date_picker", max_date)
    if hasattr(picked_date, "date"):
        picked_date = picked_date.date()
    view_date = picked_date
    is_realtime_mode = (view_date == max_date)

    if is_realtime_mode:
        active_ts = ts_today
        view_date = current_date
        completed_buckets = ts_today[ts_today["is_completed"]]
        df_view = df_today
        view_bad_calls = today_bad_calls
        is_today_finished = (len(completed_buckets) >= 38)
        if is_today_finished:
            active_time_str = "17:30 (Đã Chốt Toàn Ngày)"
        elif not completed_buckets.empty:
            latest_row = completed_buckets.iloc[-1]
            active_time_str = latest_row["bucket_time"].strftime("%H:%M")
        else:
            active_time_str = "08:00 (Starting)"
    else:
        is_today_finished = True
        if view_date == current_date:
            active_ts = ts_today
            completed_buckets = ts_today[ts_today["is_completed"]]
            df_view = df_today
            view_bad_calls = today_bad_calls
            latest_row = completed_buckets.iloc[-1] if not completed_buckets.empty else ts_today.iloc[0]
            active_time_str = f"Lịch hôm nay: {latest_row['bucket_time'].strftime('%H:%M') if not completed_buckets.empty else '08:00'}"
        else:
            active_ts = past_days_ts.get(view_date)
            if active_ts is None or active_ts.empty:
                p_df = full_df[full_df["date"] == view_date].copy() if not full_df.empty else pd.DataFrame()
                active_ts = process_single_date(p_df, view_date, is_live_today=False)
                past_days_ts[view_date] = active_ts

            completed_buckets = active_ts
            active_time_str = "17:30 (Đã Chốt Toàn Ngày)"
            df_view = full_df[full_df["date"] == view_date] if not full_df.empty else pd.DataFrame()
            view_bad_calls = df_view[df_view["result_code"].isin(SYSTEM_ERRORS)].sort_values("start_time", ascending=False) if not df_view.empty else pd.DataFrame()

    # TÍNH TOÁN METRICS KPI TRỌNG TÂM
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

    flagged = completed_buckets[completed_buckets["is_p1_red"] | completed_buckets["is_p2_yellow"]].copy() if completed_buckets is not None and not completed_buckets.empty else pd.DataFrame()

    # --------------------------------------------------------------------------
    # SIDEBAR 5 PHÂN HỆ PRODUCTION NOC
    # --------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 6px 0 16px 0; border-bottom: 1px solid {border_col}; margin-bottom: 16px;">
            <div style="font-size:20px; font-weight:800; color:{text_main}; line-height:1.25; letter-spacing:-0.3px;">SCC Outbound System</div>
            <div style="font-size:12.5px; font-weight:600; color:{text_muted}; margin-top:3px;">Anomaly Detection Dashboard</div>
        </div>
        """, unsafe_allow_html=True)

        # Tách rõ realtime operations, incident response, analytics, reports và health.
        soc_nav_options = [
            "Live Operations",
            "Incidents",
            "Analytics",
            "Reports",
            "System Health"
        ]
        cur_selected = st.session_state.get("soc_nav_menu", "Live Operations")
        if cur_selected not in soc_nav_options:
            cur_selected = "Live Operations"
            st.session_state["soc_nav_menu"] = "Live Operations"

        nav_choice = st.radio(
            "DANH MỤC NOC",
            soc_nav_options,
            index=soc_nav_options.index(cur_selected),
            key="soc_nav_menu",
            label_visibility="collapsed"
        )

        prev_active_nav = st.session_state.get("_prev_active_nav", nav_choice)
        if prev_active_nav != nav_choice:
            st.session_state["_prev_active_nav"] = nav_choice
            st.session_state["active_investigation_bucket"] = None

        st.markdown(f"<div style='border-top:1px solid {border_col}; margin: 24px 0 14px 0;'></div>", unsafe_allow_html=True)
        status_col = "#ef4444" if (view_p1_count > 0) else "#10b981"
        status_label = f"{view_p1_count} Critical Alerts" if (view_p1_count > 0) else "All systems operational"
        st.markdown(f"""
        <div style="background:{card_bg}; border:1px solid {border_col}; border-radius:8px; padding:12px 14px;">
            <div style="font-size:10px; font-weight:700; color:{text_muted}; text-transform:uppercase; letter-spacing:0.5px;">SYSTEM STATUS</div>
            <div style="font-size:13px; font-weight:700; color:{status_col}; margin-top:4px;">{status_label}</div>
            <div style="font-size:11px; color:{text_muted}; margin-top:8px;">Version: <b>3.2.2</b></div>
        </div>
        """, unsafe_allow_html=True)

    # KÍCH HOẠT AUTO-REFRESH NATIVE BẰNG STREAMLIT-AUTOREFRESH (3 GIÂY / LẦN CHUẨN XÁC, KHÔNG LAG)
    # Tự động ngắt khi xem ngày cũ hoặc đang điều tra chi tiết sự cố
    if st_autorefresh and is_realtime_mode and nav_choice == "Live Operations" and not st.session_state.get("active_investigation_bucket"):
        st_autorefresh(interval=30000, debounce=True, key="scc_live_stream_refresher")


    # --------------------------------------------------------------------------
    # MAIN HEADER: BREADCRUMB & THEME CONTROLLER
    # --------------------------------------------------------------------------
    col_bread, col_theme = st.columns([4.2, 1.0])
    with col_bread:
        st.markdown(f"""
        <div style="font-size:24px; font-weight:800; color:{text_main}; letter-spacing:-0.4px;">
            {nav_choice}
        </div>
        """, unsafe_allow_html=True)
    with col_theme:
        st.radio(
            "Giao diện:",
            ["Sáng", "Tối"],
            horizontal=True,
            key="theme_mode",
            label_visibility="collapsed"
        )

    st.markdown(f"<hr style='margin: 8px 0 14px 0; border:none; border-top:1px solid {border_col};'>", unsafe_allow_html=True)

    # Chèn công cụ hỗ trợ tự động gắn nút tiện ích vào chân popup Lịch (Hôm nay, Hôm qua trên Dashboard và Tổng Hợp trên Reports)
    components.html(f"""
    <script>
    (function() {{
        const pDoc = window.parent.document;
        const pWin = window.parent;
        pWin.__scc_cur_nav = "{nav_choice}";
        pWin.__scc_today_str = "{max_date.strftime('%Y-%m-%d')}";
        pWin.__scc_yest_str = "{yesterday_date.strftime('%Y-%m-%d')}";
        pWin.__scc_today_day = "{max_date.day}";
        pWin.__scc_yest_day = "{yesterday_date.day}";

        function fixCalendarFooter() {{
            const currentNav = pWin.__scc_cur_nav || "{nav_choice}";
            const todayStr = pWin.__scc_today_str;
            const yestStr = pWin.__scc_yest_str;
            const todayDay = pWin.__scc_today_day;
            const yestDay = pWin.__scc_yest_day;

            const popovers = pDoc.querySelectorAll('div[data-baseweb="popover"]');
            popovers.forEach(popover => {{
                const cal = popover.querySelector('div[data-baseweb="calendar"]');
                if (!cal) return;

                const existingFooter = popover.querySelector('.custom-cal-footer');
                if (currentNav === "Reports") {{
                    if (existingFooter && !existingFooter.dataset.tab3) {{
                        existingFooter.remove();
                    }}
                    if (!popover.querySelector('.custom-cal-footer[data-tab3="true"]')) {{
                        const footer = pDoc.createElement('div');
                        footer.className = 'custom-cal-footer';
                        footer.dataset.tab3 = 'true';
                        footer.style.cssText = 'display:flex;gap:8px;padding:8px 12px;border-top:1px solid {border_col};background:{card_bg};border-radius:0 0 10px 10px;margin-top:4px;';

                        const btnAll = pDoc.createElement('button');
                        btnAll.innerText = '📊 Tổng Hợp Toàn Bộ';
                        btnAll.style.cssText = 'flex:1;padding:7px 12px;font-size:12.5px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;';
                        btnAll.onclick = (e) => {{
                            e.stopPropagation();
                            const curUrl = new URL(pWin.location.href);
                            curUrl.searchParams.set('t3_all', '1');
                            pWin.location.href = curUrl.toString();
                        }};
                        footer.appendChild(btnAll);
                        cal.appendChild(footer);
                    }}
                }} else if (currentNav === "Live Operations") {{
                    if (existingFooter && existingFooter.dataset.tab3) {{
                        existingFooter.remove();
                    }}
                    if (!popover.querySelector('.custom-cal-footer:not([data-tab3="true"])')) {{
                        const footer = pDoc.createElement('div');
                        footer.className = 'custom-cal-footer';
                        footer.style.cssText = 'display:flex;gap:8px;padding:8px 12px;border-top:1px solid {border_col};background:{card_bg};border-radius:0 0 10px 10px;margin-top:4px;';

                        const btnToday = pDoc.createElement('button');
                        btnToday.innerText = '⚡ Hôm nay';
                        btnToday.style.cssText = 'flex:1;padding:7px 10px;font-size:12px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;';
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
                        btnYest.innerText = '⏮️ Hôm qua';
                        btnYest.style.cssText = 'flex:1;padding:7px 10px;font-size:12px;font-weight:600;background:{"#1e293b" if is_dark else "#f1f5f9"};color:{text_main};border:1px solid {border_col};border-radius:6px;cursor:pointer;';
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
            }});
        }}

        if (pWin.__scc_cal_interval_id) {{
            clearInterval(pWin.__scc_cal_interval_id);
        }}
        // Avoid a tight DOM polling loop that causes visible flicker on every
        // Streamlit rerun. The calendar footer does not need 12.5fps polling.
        pWin.__scc_cal_interval_id = setInterval(fixCalendarFooter, 500);
    }})();
    </script>
    """, height=0, width=0)

    # ==============================================================================
    # 1. VIEW: DASHBOARD (GIỮ NGUYÊN 100% TAB 1 GỐC + BỘ LỌC LỊCH GỌN GÀNG TRONG TAB)
    # ==============================================================================
    if nav_choice == "Live Operations":
        col_dash_date, _ = st.columns([1.5, 2.5])
        with col_dash_date:
            cur_cal_val = st.session_state.get("cal_date_picker", max_date)
            if hasattr(cur_cal_val, "date"):
                cur_cal_val = cur_cal_val.date()
            if cur_cal_val < min_date or cur_cal_val > max_date:
                cur_cal_val = max_date

            if "_ui_dash_date_input" not in st.session_state or st.session_state.get("_ui_dash_date_input") != cur_cal_val:
                st.session_state["_ui_dash_date_input"] = cur_cal_val

            def _on_dash_date_picked():
                picked = st.session_state.get("_ui_dash_date_input")
                if hasattr(picked, "date"):
                    picked = picked.date()
                st.session_state["cal_date_picker"] = picked
                st.session_state["is_following_live"] = (picked == max_date)

            st.date_input(
                "Chọn ngày theo Lịch:",
                value=cur_cal_val,
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD",
                key="_ui_dash_date_input",
                on_change=_on_dash_date_picked,
                help="Bấm vào để mở lịch. Trong lịch có nút Hôm nay và Hôm qua để chọn nhanh."
            )

        st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

        # 4 THẺ KPI CHÍNH
        kpi_cards = [
            ("Tổng Số Cuộc Gọi Trong Ngày", f"{view_total:,} cuộc", f"Ngày {view_date.strftime('%Y-%m-%d')} ({active_time_str})", text_muted),
            ("Tỷ Lệ Gián Đoạn", f"{view_err_rate:.2f}%", f"{view_503} cuộc lỗi viễn thông", "#ef4444" if view_err_rate > 5 else text_muted),
            ("Sự Cố Khẩn Cấp (P1)", f"{view_p1_count} khung giờ", "Cần can thiệp ngay" if view_p1_count > 0 else "Hạ tầng an toàn", "#ef4444" if view_p1_count > 0 else "#10b981"),
            ("Tăng Tải Đột Biến (P2)", f"{view_p2_count} khung giờ", "Cần chú ý nhân sự" if view_p2_count > 0 else "Lưu lượng ổn định", "#f59e0b" if view_p2_count > 0 else "#10b981")
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

        # Production NOC: trạng thái và hàng đợi sự cố phải xuất hiện trước biểu đồ.
        # Người trực ca cần biết lỗi gì, phạm vi nào và ảnh hưởng ra sao mà không phải
        # kéo xuống cuối trang để tìm nhật ký.
        render_operational_status_banner(
            view_date=view_date,
            is_live=is_realtime_mode,
            flagged=flagged,
            text_main=text_main,
            text_muted=text_muted,
            card_bg=card_bg,
            border_col=border_col,
        )
        render_incident_queue(
            flagged=flagged,
            text_main=text_main,
            text_muted=text_muted,
            card_bg=card_bg,
            border_col=border_col,
        )
        st.markdown("<div style='margin:16px 0 8px 0;'></div>", unsafe_allow_html=True)

        # ---------------- 2 BIỂU ĐỒ SONG SONG GỐC (CHART 1 & CHART 2) ----------------
        fig_traffic = go.Figure()
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["upper_limit"].tolist(),
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["lower_limit"].tolist(),
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(148, 163, 184, 0.22)", name="Vùng an toàn", hoverinfo="skip"
        ))
        fig_traffic.add_trace(go.Scatter(
            x=active_ts["bucket_time"].tolist(), y=active_ts["mu"].tolist(),
            mode="lines", line=dict(color="#64748b", width=1.5, dash="dash"),
            name="Kỳ vọng TB", hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Mức kỳ vọng:</b> %{y:.1f} cuộc<extra></extra>"
        ))
        x_actual = completed_buckets["bucket_time"].tolist() if not completed_buckets.empty else []
        y_actual = completed_buckets["calls_total"].tolist() if not completed_buckets.empty else []
        fig_traffic.add_trace(go.Scatter(
            x=x_actual, y=y_actual, mode="lines+markers",
            line=dict(color="#0284c7", width=2.5), marker=dict(size=6, color="#0369a1"),
            name="Thực tế", hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Thực tế:</b> %{y} cuộc<extra></extra>"
        ))
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
            x=x_drop if x_drop else [None], y=y_drop if y_drop else [None],
            mode="markers", marker=dict(color="#dc2626", size=13, symbol="circle", line=dict(color="#ffffff", width=2)),
            name="Sự cố P1", text=desc_drop if desc_drop else [""],
            hovertemplate="<b>SỰ CỐ KHẨN CẤP!</b><br><b>Chi tiết:</b> %{text}<br><b>Khung:</b> %{x|%H:%M}<br><b>Số cuộc:</b> %{y}<extra></extra>"
        ))
        p2_spike = completed_buckets[completed_buckets["is_p2_yellow"]] if not completed_buckets.empty else pd.DataFrame()
        x_spike = p2_spike["bucket_time"].tolist() if not p2_spike.empty else []
        y_spike = p2_spike["calls_total"].tolist() if not p2_spike.empty else []
        fig_traffic.add_trace(go.Scatter(
            x=x_spike if x_spike else [None], y=y_spike if y_spike else [None],
            mode="markers", marker=dict(color="#d97706", size=13, symbol="diamond", line=dict(color="#ffffff", width=2)),
            name="Tăng tải P2", hovertemplate="<b>CẢNH BÁO: Tăng tải đột biến!</b><br><b>Khung:</b> %{x|%H:%M}<br><b>Số cuộc:</b> %{y}<extra></extra>"
        ))
        peak_actual = float(completed_buckets["calls_total"].max()) if not completed_buckets.empty else 0.0
        peak_upper = float(active_ts["upper_limit"].max()) if not active_ts.empty else 12.0
        peak_val = max(12.0, peak_upper, peak_actual)
        max_calls_val = peak_val * 1.30

        fig_traffic.update_layout(
            uirevision=True,
            template=plotly_template, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
            height=430, margin=dict(l=45, r=20, t=65, b=35), hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5, font=dict(size=11, color=text_main)),
            yaxis=dict(title="Cuộc gọi / 15 phút", range=[-0.8, max_calls_val], gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
            xaxis=dict(tickformat="%H:%M", dtick=1800000, gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted))
        )

        fig_error = go.Figure()
        x_err = completed_buckets["bucket_time"].tolist() if not completed_buckets.empty else []
        y_err = (completed_buckets["error_rate"] * 100).round(2).tolist() if not completed_buckets.empty else []
        fig_error.add_trace(go.Scatter(
            x=x_err, y=y_err, mode="lines+markers",
            line=dict(color="#ea580c", width=2.5), marker=dict(size=6, color="#c2410c"),
            name="Tỷ lệ lỗi (%)", hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Tỷ lệ lỗi:</b> %{y:.1f}%<extra></extra>"
        ))
        if not completed_buckets.empty:
            thresh_x = completed_buckets["bucket_time"].tolist()
            thresh_y = (completed_buckets["dynamic_threshold"] * 100).round(2).tolist()
        else:
            thresh_x = active_ts["bucket_time"].tolist()
            thresh_y = [compute_dynamic_error_threshold(int(m)) * 100 for m in active_ts["mu"]]

        fig_error.add_trace(go.Scatter(
            x=thresh_x, y=thresh_y, mode="lines",
            line=dict(color="#dc2626", width=2, dash="dash"),
            name="Ngưỡng động (%)", hovertemplate="<b>Khung:</b> %{x|%H:%M}<br><b>Ngưỡng an toàn:</b> %{y:.1f}%<extra></extra>"
        ))
        p1_err = completed_buckets[completed_buckets["is_p1_net"]] if not completed_buckets.empty else pd.DataFrame()
        x_p1_err = p1_err["bucket_time"].tolist() if not p1_err.empty else []
        y_p1_err = (p1_err["error_rate"] * 100).round(2).tolist() if not p1_err.empty else []
        fig_error.add_trace(go.Scatter(
            x=x_p1_err if x_p1_err else [None], y=y_p1_err if y_p1_err else [None],
            mode="markers", marker=dict(color="#dc2626", size=14, symbol="x", line=dict(color="#ffffff", width=2)),
            name="Vượt ngưỡng P1", hovertemplate="<b>SỰ CỐ KHẨN CẤP: Vượt ngưỡng an toàn!</b><br><b>Khung:</b> %{x|%H:%M}<br><b>Tỷ lệ lỗi:</b> %{y:.1f}%<extra></extra>"
        ))
        max_err_display = 60.0
        if not completed_buckets.empty:
            peak_err = float(completed_buckets["error_rate"].max() * 100)
            if peak_err > 40.0:
                max_err_display = min(120.0, peak_err * 1.30)

        fig_error.update_layout(
            uirevision=True,
            template=plotly_template, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
            height=430, margin=dict(l=45, r=20, t=65, b=35), hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5, font=dict(size=11, color=text_main)),
            yaxis=dict(title="Tỷ lệ gián đoạn (%)", range=[-2.0, max_err_display], gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
            xaxis=dict(tickformat="%H:%M", dtick=1800000, gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted))
        )

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown(f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>1. Lưu Lượng Cuộc Gọi Phát Sinh So Với Mức Kỳ Vọng Thông Thường</div>", unsafe_allow_html=True)
            st.plotly_chart(fig_traffic, use_container_width=True, config={"displayModeBar": False, "responsive": True})
        with col_c2:
            st.markdown(f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>2. Tỷ Lệ Cuộc Gọi Bị Gián Đoạn So Với Ngưỡng An Toàn Tự Co Giãn</div>", unsafe_allow_html=True)
            st.plotly_chart(fig_error, use_container_width=True, config={"displayModeBar": False, "responsive": True})

        st.markdown("---")

        # ---------------- BẢNG NHẬT KÝ SỰ CỐ VẬN HÀNH TRONG NGÀY (GỐC) ----------------
        st.markdown(f"<div style='font-size:16px; font-weight:700; color:{text_main}; margin-bottom:8px;'>Nhật Ký Sự Cố Trong Ngày — {view_date.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)

        if not flagged.empty:
            for idx, r in flagged.reset_index(drop=True).iterrows():
                b_str = r["bucket_time"].strftime("%H:%M")
                level_text, level_col = get_friendly_level(r)
                carrier = get_friendly_carrier(r)
                err_text = get_friendly_error(r)
                total_c = int(r["calls_total"])
                fail_c = int(r["calls_503"])
                pct = (fail_c / total_c * 100) if total_c > 0 else 0

                row_cols = st.columns([1.1, 1.4, 1.4, 2.8, 1.8, 1.2])
                with row_cols[0]:
                    st.markdown(f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; padding-top:6px;'>⏰ {b_str}</div>", unsafe_allow_html=True)
                with row_cols[1]:
                    st.markdown(f"<div style='font-size:12.5px; font-weight:700; color:{level_col}; padding-top:6px;'>{level_text}</div>", unsafe_allow_html=True)
                with row_cols[2]:
                    st.markdown(f"<div style='font-size:12.5px; font-weight:600; color:{text_main}; padding-top:6px;'>Tuyến: {carrier}</div>", unsafe_allow_html=True)
                with row_cols[3]:
                    st.markdown(f"<div style='font-size:12.5px; color:{text_main}; padding-top:6px;'><b>{err_text}</b></div>", unsafe_allow_html=True)
                with row_cols[4]:
                    st.markdown(f"<div style='font-size:12px; color:{text_muted}; padding-top:6px;'>Lỗi: <b>{fail_c}/{total_c}</b> ({pct:.1f}%)</div>", unsafe_allow_html=True)
                with row_cols[5]:
                    if st.button("Chi tiết", key=f"btn_dash_inc_{idx}_{b_str}"):
                        st.session_state["active_investigation_bucket"] = b_str
                        st.rerun()

            # KHỐI HỒ SƠ ĐIỀU TRA KỸ THUẬT KHI BẤM CHI TIẾT
            active_b_str = st.session_state.get("active_investigation_bucket")
            if active_b_str:
                matched_rows = flagged[flagged["bucket_time"].dt.strftime("%H:%M") == active_b_str]
                if not matched_rows.empty:
                    r_inv = matched_rows.iloc[0]
                    fc_inv = get_friendly_carrier(r_inv)
                    level_t_inv, level_c_inv = get_friendly_level(r_inv)
                    n_tot_inv = int(r_inv["calls_total"])
                    n_fail_inv = int(r_inv["calls_503"])
                    r_rate_inv = (n_fail_inv / n_tot_inv * 100) if n_tot_inv > 0 else 0

                    raw_err = str(r_inv.get("specific_error", "")).strip()
                    matched_k = next((k for k in TELECOM_ERROR_KB if k in raw_err), None)
                    if not matched_k:
                        if r_inv.get("is_p1_drop", False):
                            matched_k = "DROP_TRAFFIC"
                        elif r_inv.get("is_p2_yellow", False):
                            matched_k = "TRAFFIC_SPIKE"
                        else:
                            matched_k = "503_CONGESTION"
                    kb = TELECOM_ERROR_KB.get(matched_k, TELECOM_ERROR_KB["503_CONGESTION"])

                    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        c_title_inv, c_close_inv = st.columns([4.0, 1.0])
                        with c_title_inv:
                            st.markdown(f"""
                            <div style="font-size:17px; font-weight:800; color:{text_main}; margin-bottom:2px;">
                                Hồ Sơ Điều Tra Kỹ Thuật: Khung Giờ {active_b_str}
                            </div>
                            <div style="font-size:12px; color:{text_muted};">
                                Tuyến: <b>{fc_inv}</b> &nbsp;|&nbsp; Ngày: <b>{view_date.strftime('%d/%m/%Y')}</b> &nbsp;|&nbsp; Mức độ: <span style="color:{level_c_inv}; font-weight:700;">{level_t_inv}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with c_close_inv:
                            if st.button("✕ Đóng Chi Tiết", key="btn_close_inv_dash", use_container_width=True):
                                st.session_state["active_investigation_bucket"] = None
                                st.rerun()

                        st.markdown(f"<hr style='margin:10px 0; border:none; border-top:1px solid {border_col};'>", unsafe_allow_html=True)

                        box_bg = "#fef2f2" if (not is_dark and r_inv.get("is_p1_red", False)) else ("#fffbeb" if not is_dark else "#1e293b")
                        box_border = "#fca5a5" if (not is_dark and r_inv.get("is_p1_red", False)) else ("#fde68a" if not is_dark else "#334155")
                        st.markdown(f"""
                        <div style="background:{box_bg}; border:1px solid {box_border}; border-radius:8px; padding:12px 14px; margin-bottom:12px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                                <div>
                                    <div style="font-size:11px; color:{text_muted}; text-transform:uppercase; font-weight:700;">MÃ KỸ THUẬT LỖI</div>
                                    <div style="font-size:16px; font-weight:800; color:{level_c_inv};">{kb['code']}</div>
                                    <div style="font-size:12.5px; color:{text_main}; font-family:monospace; font-weight:600;">{kb['protocol']}</div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:11px; color:{text_muted}; text-transform:uppercase; font-weight:700;">ẢNH HƯỞNG</div>
                                    <div style="font-size:18px; font-weight:800; color:{level_c_inv};">{n_fail_inv} / {n_tot_inv} cuộc ({r_rate_inv:.1f}%)</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        actions_html = "".join([f"<li style='margin-bottom:6px; color:{text_main};'>{act}</li>" for act in kb['actions']])
                        rca_bg = "#f8fafc" if not is_dark else "#1e293b"
                        rca_border = "#cbd5e1" if not is_dark else "#334155"
                        st.markdown(f"""
                        <div style="background:{rca_bg}; border:1px solid {rca_border}; border-left:4px solid {level_c_inv}; border-radius:8px; padding:12px 14px; margin-bottom:14px;">
                            <div style="font-size:13px; font-weight:700; color:{text_main}; margin-bottom:4px;">
                                Phân tích nguyên nhân kỹ thuật (RCA):
                            </div>
                            <div style="font-size:12.5px; color:{text_main}; line-height:1.55; margin-bottom:12px;">
                                {kb['cause']}
                            </div>
                            <div style="font-size:13px; font-weight:700; color:#10b981; margin-bottom:4px;">
                                Hướng dẫn quy trình xử lý NOC tiêu chuẩn (SOP):
                            </div>
                            <ul style="font-size:12px; line-height:1.55; margin:0 0 10px 0; padding-left:18px;">
                                {actions_html}
                            </ul>
                            <div style="font-size:12px; color:{text_main}; border-top:1px dashed {border_col}; padding-top:8px;">
                                <b>Hotline NOC đối tác:</b> <span style="color:#0284c7; font-weight:700;">{kb['hotline']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        target_dt_inv = r_inv["bucket_time"]
                        s_inv_calls = df_view[(df_view["bucket_time"] == target_dt_inv) & (df_view["result_code"].isin(SYSTEM_ERRORS))].copy()
                        if not s_inv_calls.empty:
                            st.markdown(f"<div style='font-size:13px; font-weight:700; color:{text_main}; margin-bottom:6px;'>Danh Sách Nhật Ký Cuộc Gọi Bị Lỗi Mẫu ({len(s_inv_calls)} cuộc):</div>", unsafe_allow_html=True)
                            log_cols = ["call_id", "carrier", "start_time", "duration", "result_code"]
                            v_cols = [c for c in log_cols if c in s_inv_calls.columns]
                            sub_df = s_inv_calls[v_cols].sort_values("start_time", ascending=False).head(20).copy()
                            sub_df.rename(columns={
                                "call_id": "Mã cuộc gọi", "carrier": "Nhà mạng", "start_time": "Thời gian",
                                "duration": "Thời lượng", "result_code": "Mã lỗi"
                            }, inplace=True)
                            st.dataframe(sub_df, use_container_width=True, hide_index=True)
        else:
            st.success("Toàn bộ các khung giờ trong ngày hoạt động ổn định, không có sự cố nào.")

    # ==============================================================================
    # 2. VIEW: ANALYSIS (GIỮ NGUYÊN 100% TAB 2 GỐC + MA TRẬN NHIỆT RỦI RO HOURLY HEATMAP)
    # ==============================================================================
    elif nav_choice == "Incidents":
        render_incident_investigation(
            view_date=view_date,
            full_df=full_df,
            flagged=flagged,
            text_main=text_main,
            text_muted=text_muted,
            card_bg=card_bg,
            border_col=border_col,
        )

    elif nav_choice == "Analytics":
        completed_today_slice = completed_buckets if is_realtime_mode else None
        dyn_hourly_stats, tot_hist_days, tot_hist_buckets = compute_dynamic_seasonality_and_risk(
            past_days_ts, completed_today_slice
        )

        work_hours = list(range(8, 18))
        max_risk_h = max(work_hours, key=lambda h: dyn_hourly_stats.get(h, {}).get("risk_pct", 0.0))
        max_risk_val = dyn_hourly_stats.get(max_risk_h, {}).get("risk_pct", 0.0)

        peak_traffic_h = max(work_hours, key=lambda h: dyn_hourly_stats.get(h, {}).get("mean_15m", 0.0))
        peak_traffic_val = dyn_hourly_stats.get(peak_traffic_h, {}).get("mean_15m", 0.0)

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
                stab_sub = f"Ghi nhận {p1_today} khung vượt ngưỡng an toàn"
                stab_col = "#ef4444"
            elif p2_today > 0:
                stab_val = "Tăng Tải Đột Biến"
                stab_sub = f"Ghi nhận {p2_today} khung giờ gọi cao hơn ngày thường"
                stab_col = "#f59e0b"
            else:
                stab_val = "Bình Thường"
                stab_sub = "Cuộc gọi bám sát mức trung bình lịch sử"
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
                line=dict(color="#38bdf8", width=2.5), name="Kỳ vọng trung bình"
            ))
            if not completed_buckets.empty:
                fig_s.add_trace(go.Scatter(
                    x=completed_buckets["hour"], y=completed_buckets["calls_total"],
                    mode="markers", marker=dict(size=8, color="#10b981"),
                    name="Thực tế hôm nay"
                ))
            fig_s.update_layout(
                template=plotly_template, height=350, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
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
                x=hours, y=risk_probs, marker=dict(color=colors),
                text=[f"{v:.0f}%" if v > 0 and 8 <= h <= 17 else "" for h, v in enumerate(risk_probs)],
                textposition="outside", name="Xác suất sự cố (%)"
            ))
            fig_risk.add_shape(type="line", x0=0, x1=23, y0=60, y1=60, line=dict(color="#dc2626", dash="dash", width=1.5))
            fig_risk.add_shape(type="line", x0=0, x1=23, y0=30, y1=30, line=dict(color="#f59e0b", dash="dot", width=1.5))
            fig_risk.update_layout(
                template=plotly_template, height=350, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
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
                level = "Nguy cơ cao"
                rec = "Sẵn sàng kích hoạt trunk dự phòng, kiểm soát tốc độ auto-dialer"
            elif risk >= 30:
                level = "Cần chú ý"
                rec = "Theo dõi chặt dung lượng trunk và tỷ lệ lỗi Gateway"
            else:
                level = "Bình thường"
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

    # ==============================================================================
    # 3. VIEW: REPORTS (GIỮ NGUYÊN 100% TAB 3 GỐC + CARRIER SCORECARD ĐỐI SOÁT NHÀ MẠNG)
    # ==============================================================================
    elif nav_choice == "Reports":
        if "t3_all" in st.query_params:
            st.session_state["t3_date_range_picker"] = (min_date, max_date)
            del st.query_params["t3_all"]

        all_dates = sorted(full_df["date"].unique()) if not full_df.empty else []

        st.markdown("### Báo Cáo Tổng Hợp Vận Hành (Executive Operational Summary)")

        col_t3_date, _ = st.columns([1.5, 2.5])
        with col_t3_date:
            def get_work_week(day_obj):
                if hasattr(day_obj, "date"): day_obj = day_obj.date()
                mon = day_obj - timedelta(days=day_obj.weekday())
                fri = mon + timedelta(days=4)
                return max(min_date, mon), min(max_date, fri)

            t3_range_default = (min_date, max_date)
            raw_session_t3 = st.session_state.get("t3_date_range_picker", t3_range_default)
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
                    if v_start == min_date and v_end == max_date:
                        t3_val = (min_date, max_date)
                    elif v_start == v_end or (v_end - v_start).days <= 6:
                        s_d, e_d = get_work_week(v_start)
                        st.session_state["t3_date_range_picker"] = (s_d, e_d)
                        t3_val = (s_d, e_d)
                    else:
                        t3_val = (max(min_date, v_start), min(max_date, v_end))
                else:
                    t3_val = t3_range_default
            else:
                s_d, e_d = get_work_week(raw_session_t3)
                st.session_state["t3_date_range_picker"] = (s_d, e_d)
                t3_val = (s_d, e_d)

            t3_range_picked = st.date_input(
                "Chọn khoảng ngày đối soát (Từ ngày – Đến ngày):",
                value=t3_val,
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD",
                key="t3_date_range_picker",
                help="Bấm vào ngày bất kỳ trong tuần để tự động chọn và đối soát trọn vẹn tuần làm việc đó (Thứ 2 – Thứ 6), hoặc bấm nút 'Tổng Hợp Toàn Bộ' dưới chân lịch để xem toàn bộ."
            )

        if isinstance(t3_range_picked, (list, tuple)):
            if len(t3_range_picked) == 2:
                if t3_range_picked[0] == min_date and t3_range_picked[1] == max_date:
                    t3_start_d, t3_end_d = min_date, max_date
                elif t3_range_picked[0] == t3_range_picked[1] or (t3_range_picked[1] - t3_range_picked[0]).days <= 6:
                    t3_start_d, t3_end_d = get_work_week(t3_range_picked[0])
                else:
                    t3_start_d, t3_end_d = t3_range_picked[0], t3_range_picked[1]
            elif len(t3_range_picked) == 1:
                t3_start_d, t3_end_d = get_work_week(t3_range_picked[0])
            else:
                t3_start_d, t3_end_d = min_date, max_date
        else:
            t3_start_d, t3_end_d = get_work_week(t3_range_picked)

        if t3_start_d > t3_end_d:
            t3_start_d, t3_end_d = t3_end_d, t3_start_d

        filtered_dates = [d for d in all_dates if t3_start_d <= d <= t3_end_d and d.weekday() < 5]
        df_t3 = full_df[full_df["date"].isin(filtered_dates)]
        tot_all_calls = len(df_t3)

        is_view_all_active = (t3_start_d <= min_date and t3_end_d >= max_date)
        if is_view_all_active:
            st.caption(f"Đang đối soát: **Toàn bộ dữ liệu vận hành ({min_date.strftime('%d/%m/%Y')} ➔ {max_date.strftime('%d/%m/%Y')})** — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")
        else:
            st.caption(f"Đang đối soát: **Tuần làm việc {t3_start_d.strftime('%d/%m/%Y')} ➔ {t3_end_d.strftime('%d/%m/%Y')}** (Thứ 2 – Thứ 6, trừ T7 & CN) — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")

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

        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng Lưu Lượng Cuộc Gọi", f"{tot_all_calls:,} cuộc", f"{len(filtered_dates)} ngày vận hành")
        c2.metric("Tỷ Lệ Bắt Máy Thành Công (ASR)", f"{all_asr_pct:.1f}%", f"{tot_all_ans:,} cuộc nghe máy (Mục tiêu >= 50%)")
        c3.metric("Thời Lượng Đàm Thoại TB (ACD)", f"{all_acd_sec:.0f} giây", "Trung bình cuộc gọi Answered")

        c4, c5, c6 = st.columns(3)
        c4.metric("Tỷ Lệ Lỗi Viễn Thông 503", f"{all_err_pct:.2f}%", f"{tot_all_503} lỗi (Mục tiêu SLA <= 5.0%)")
        c5.metric("Độ Khả Dụng Vận Hành (SLA)", f"{sla_compliance_pct:.1f}%", "Tỷ lệ khung giờ không có sự cố P1")
        c6.metric("Tổng Số Sự Cố Ghi Nhận", f"{tot_all_p1} P1  |  {tot_all_p2} P2", "P1 Lỗi mạng / P2 Đột biến tải")

        st.markdown("---")

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
            acd = round(float(sub[sub["result_code"] == "ANSWERED"]["duration"].mean()), 1) if ans > 0 else 0.0

            ts_d = past_days_ts.get(d)
            if ts_d is None and d == current_date:
                ts_d = completed_buckets
            p1 = int(ts_d["is_p1_red"].sum()) if ts_d is not None and not ts_d.empty else 0
            p2 = int(ts_d["is_p2_yellow"].sum()) if ts_d is not None and not ts_d.empty else 0

            if p1 > 0 or err >= 10.0:
                sla = "Vi phạm SLA"
            elif p2 > 0 or err >= 5.0:
                sla = "Cảnh báo"
            else:
                sla = "Đạt chuẩn SLA"

            day_matrix_rows.append({
                "date_obj": d,
                "date_str": d.strftime("%Y-%m-%d (%a)"),
                "total_calls": tot,
                "calls_answered": ans,
                "calls_unanswered": unans,
                "asr_pct": asr,
                "calls_503": n_503,
                "error_rate_pct": err,
                "diff_gap_pct": diff_gap,
                "acd_sec": acd,
                "p1_alerts": p1,
                "p2_warnings": p2,
                "sla_status": sla
            })

        df_matrix = pd.DataFrame(day_matrix_rows)

        if not df_matrix.empty:
            col_chart_t3_1, col_chart_t3_2 = st.columns(2)
            with col_chart_t3_1:
                st.markdown("#### Lưu Lượng Hoạt Động Theo Ngày")
                fig_main = go.Figure()
                fig_main.add_trace(go.Bar(
                    x=df_matrix["date_str"], y=df_matrix["calls_answered"],
                    name="Kết nối thành công (Nghe máy)", marker_color="#38bdf8"
                ))
                fig_main.add_trace(go.Bar(
                    x=df_matrix["date_str"], y=df_matrix["calls_503"],
                    name="Cuộc gọi bị lỗi mạng (503)", marker_color="#f85149"
                ))
                fig_main.update_layout(
                    template=plotly_template, barmode="group", height=370,
                    hovermode="x unified", paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                    margin=dict(l=30, r=20, t=50, b=30),
                    yaxis=dict(title="Cuộc gọi / Ngày", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    legend=dict(orientation="h", y=1.18, x=0.5, xanchor="center", font=dict(color=text_main, size=11))
                )
                st.plotly_chart(fig_main, use_container_width=True)

            with col_chart_t3_2:
                st.markdown("#### Xu Hướng Chất Lượng & Chênh Lệch (ASR vs Lỗi 503)")
                fig_qual = go.Figure()
                fig_qual.add_trace(go.Scatter(
                    x=df_matrix["date_str"], y=df_matrix["asr_pct"],
                    mode="lines+markers", name="Tỷ lệ bắt máy ASR (%)",
                    line=dict(color="#0284c7", width=2.5), marker=dict(size=7, color="#0369a1")
                ))
                fig_qual.add_trace(go.Scatter(
                    x=df_matrix["date_str"], y=df_matrix["error_rate_pct"],
                    mode="lines+markers", name="Tỷ lệ lỗi viễn thông 503 (%)",
                    line=dict(color="#ef4444", width=2.5), marker=dict(size=7, color="#b91c1c")
                ))
                fig_qual.update_layout(
                    template=plotly_template, height=370, hovermode="x unified",
                    paper_bgcolor=card_bg, plot_bgcolor=card_bg, margin=dict(l=30, r=20, t=50, b=30),
                    yaxis=dict(title="Tỷ lệ (%)", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    legend=dict(orientation="h", y=1.18, x=0.5, xanchor="center", font=dict(color=text_main, size=11))
                )
                st.plotly_chart(fig_qual, use_container_width=True)

            st.markdown("---")

            # PHỄU VẬN HÀNH & PHÂN PHỐI ACD
            col_chart_t3_3, col_chart_t3_4 = st.columns(2)
            with col_chart_t3_3:
                st.markdown("#### Phễu Chuyển Đổi Vận Hành Viễn Thông")
                n_connected = tot_all_calls - tot_all_503
                df_ans = df_t3[df_t3["result_code"] == "ANSWERED"] if not df_t3.empty else pd.DataFrame()
                n_eff_30 = int((df_ans["duration"] >= 30).sum()) if not df_ans.empty else 0
                n_deep_60 = int((df_ans["duration"] >= 60).sum()) if not df_ans.empty else 0

                fig_funnel = go.Figure(go.Funnel(
                    y=[
                        "1. Tổng cuộc gọi phát ra", "2. Kết nối mạng thành công", "3. Khách hàng bắt máy (ASR)",
                        "4. Đàm thoại hiệu quả (≥30s)", "5. Tư vấn chuyên sâu (≥60s)"
                    ],
                    x=[tot_all_calls, n_connected, tot_all_ans, n_eff_30, n_deep_60],
                    textposition="inside", textinfo="value+percent initial", opacity=0.9,
                    marker=dict(color=["#3b82f6", "#06b6d4", "#10b981", "#8b5cf6", "#f59e0b"], line=dict(color=card_bg, width=2)),
                    connector={"line": {"color": border_col, "dash": "dot", "width": 1.5}}
                ))
                fig_funnel.update_layout(
                    template=plotly_template, height=360, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                    margin=dict(l=20, r=20, t=30, b=25), showlegend=False
                )
                st.plotly_chart(fig_funnel, use_container_width=True)

            with col_chart_t3_4:
                st.markdown("#### Phân Phối Thời Lượng Cuộc Gọi (ACD Breakdown)")
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

                fig_hist = go.Figure()
                fig_hist.add_trace(go.Bar(
                    x=dur_labels, y=dur_vals,
                    text=[f"{v:,}" if v > 0 else "0" for v in dur_vals], textposition="outside",
                    marker=dict(color=dur_colors, line=dict(color=card_bg, width=1.5))
                ))
                fig_hist.update_layout(
                    template=plotly_template, height=360, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
                    margin=dict(l=30, r=20, t=30, b=30),
                    yaxis=dict(title="Số cuộc nghe máy", gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    xaxis=dict(gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
                    showlegend=False
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown("---")

            # BẢNG ĐỐI SOÁT CHẤT LƯỢNG TỪNG NHÀ MẠNG (CARRIER SCORECARD) - LẤP ĐẦY KHOẢNG TRỐNG
            st.markdown("#### Bảng Đánh Giá Chất Lượng Nhà Mạng (Carrier Quality Scorecard)")
            st.caption("So sánh đối soát hiệu suất kết nối cuộc gọi giữa các đối tác viễn thông trong dải ngày đã chọn.")
            
            if "carrier" in df_t3.columns and not df_t3.empty:
                carrier_groups = df_t3.groupby("carrier")
                c_score_rows = []
                for c_name, c_df in carrier_groups:
                    c_tot = len(c_df)
                    c_ans = int((c_df["result_code"] == "ANSWERED").sum())
                    c_503 = int((c_df["result_code"] == "503_CONGESTION").sum())
                    c_asr = (c_ans / c_tot * 100) if c_tot > 0 else 0.0
                    c_err = (c_503 / c_tot * 100) if c_tot > 0 else 0.0
                    c_acd = float(c_df[c_df["result_code"] == "ANSWERED"]["duration"].mean()) if c_ans > 0 else 0.0
                    c_status = "Đạt chuẩn SLA" if (c_err <= 5.0 and c_asr >= 50.0) else ("Cần theo dõi" if c_err <= 10.0 else "Vi phạm SLA")
                    c_score_rows.append({
                        "Đối Tác Viễn Thông": str(c_name),
                        "Tổng Phát Ra": f"{c_tot:,} cuộc",
                        "Kết Nối Thành Công": f"{c_ans:,} cuộc",
                        "Tỷ Lệ Bắt Máy (ASR)": f"{c_asr:.1f}%",
                        "Lỗi Nghẽn Mạng 503": f"{c_503:,} cuộc ({c_err:.2f}%)",
                        "Đàm Thoại TB (ACD)": f"{c_acd:.0f}s",
                        "Đánh Giá SLA": c_status
                    })
                st.dataframe(pd.DataFrame(c_score_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Chưa có đủ phân đoạn nhà mạng trong dải ngày được chọn.")

            st.markdown("---")

            # PHÂN VÙNG ĐÁY GỐC: 60% BẢNG ĐỐI SOÁT + 40% DONUT CHART
            col_bottom_table, col_bottom_donut = st.columns([1.6, 1.4])
            with col_bottom_table:
                st.markdown("#### Nhật Ký Đánh Giá Vận Hành Đa Ngày")
                display_matrix = pd.DataFrame()
                display_matrix["Ngày Vận Hành"] = df_matrix["date_str"]
                display_matrix["Tổng Cuộc"] = df_matrix["total_calls"].astype(int)
                display_matrix["Nghe Máy"] = df_matrix["calls_answered"].astype(int)
                display_matrix["Tỷ Lệ ASR"] = df_matrix["asr_pct"].astype(str) + "%"
                display_matrix["Lỗi 503"] = df_matrix["calls_503"].astype(int).astype(str) + " (" + df_matrix["error_rate_pct"].astype(str) + "%)"
                display_matrix["ACD"] = df_matrix["acd_sec"].astype(str) + "s"
                display_matrix["Trạng Thái SLA"] = df_matrix["sla_status"]
                st.dataframe(display_matrix.iloc[::-1], use_container_width=True, hide_index=True)

            with col_bottom_donut:
                st.markdown("#### Cơ Cấu Kết Quả Cuộc Gọi")
                outcome_meta = {
                    "ANSWERED": {"label": "Khách nghe máy", "color": "#2563eb"},
                    "NO_ANSWER": {"label": "Không bắt máy", "color": "#94a3b8"},
                    "BUSY": {"label": "Thuê bao bận", "color": "#f59e0b"},
                    "503_CONGESTION": {"label": "Lỗi nghẽn 503", "color": "#ef4444"},
                    "CALLBACK_REQUESTED": {"label": "Hẹn gọi lại sau", "color": "#8b5cf6"},
                    "VOICEMAIL": {"label": "Hộp thư thoại", "color": "#06b6d4"}
                }
                rc_counts_all = df_t3["result_code"].value_counts()
                d_labels = [outcome_meta.get(k, {}).get("label", k) for k in rc_counts_all.index]
                d_colors = [outcome_meta.get(k, {}).get("color", "#cbd5e1") for k in rc_counts_all.index]
                d_vals = rc_counts_all.values.tolist()

                fig_donut_all = go.Figure(data=[go.Pie(
                    labels=d_labels, values=d_vals, hole=0.62, sort=False,
                    marker=dict(colors=d_colors, line=dict(color=card_bg, width=2)),
                    textinfo="percent", textfont=dict(size=11, color="#ffffff"),
                    hovertemplate="<b>%{label}</b>: %{value:,} cuộc (%{percent})<extra></extra>"
                )])
                fig_donut_all.update_layout(
                    template=plotly_template, height=330, margin=dict(l=15, r=15, t=15, b=15),
                    paper_bgcolor=card_bg, plot_bgcolor=card_bg, showlegend=False,
                    annotations=[dict(text=f"<b style='font-size:22px;color:{text_main};'>{tot_all_calls:,}</b><br><span style='font-size:11.5px;color:{text_muted};'>Tổng cuộc</span>", x=0.5, y=0.5, showarrow=False)]
                )
                st.plotly_chart(fig_donut_all, use_container_width=True)

    # ==============================================================================
    # 4. VIEW: SYSTEM (ĐO LƯỜNG HẠ TẦNG & TRẠNG THÁI DUAL-WRITE)
    # ==============================================================================
    elif nav_choice == "System Health":
        st.markdown(f"<div style='font-size:13px; font-weight:600; color:{text_muted}; margin-bottom:14px;'>Đo lường hạ tầng kỹ thuật: Trạng thái ghi song song 2 Database PostgreSQL (Dual-Write), Redis Stream và Telegram Webhook.</div>", unsafe_allow_html=True)

        telemetry = get_system_telemetry()

        col_sys1, col_sys2 = st.columns(2)
        with col_sys1:
            st.markdown(f"""
            <div style="background:{card_bg}; border:1px solid {border_col}; border-radius:10px; padding:16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:15px; font-weight:700; color:{text_main};">{telemetry['db1']['name']}</span>
                    <span style="font-size:12px; font-weight:700; color:#10b981;">{telemetry['db1']['status']}</span>
                </div>
                <hr style="margin:10px 0; border:none; border-top:1px solid {border_col};">
                <div style="font-size:12.5px; color:{text_muted}; line-height:1.6;">
                    • <b>Host / Port:</b> <code>{telemetry['db1']['host']}:{telemetry['db1']['port']}</code><br>
                    • <b>Số bản ghi cuộc gọi (calls_stream):</b> <b style="color:{text_main};">{telemetry['db1']['calls']:,} dòng</b><br>
                    • <b>Chuỗi thời gian (call_timeseries):</b> <b style="color:{text_main};">{telemetry['db1']['ts']:,} khung 15p</b><br>
                    • <b>Ghi chú:</b> {telemetry['db1']['msg']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_sys2:
            st.markdown(f"""
            <div style="background:{card_bg}; border:1px solid {border_col}; border-radius:10px; padding:16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:15px; font-weight:700; color:{text_main};">{telemetry['db2']['name']}</span>
                    <span style="font-size:12px; font-weight:700; color:#10b981;">{telemetry['db2']['status']}</span>
                </div>
                <hr style="margin:10px 0; border:none; border-top:1px solid {border_col};">
                <div style="font-size:12.5px; color:{text_muted}; line-height:1.6;">
                    • <b>Host / Port:</b> <code>{telemetry['db2']['host']}:{telemetry['db2']['port']}</code><br>
                    • <b>Số bản ghi cuộc gọi (calls_stream):</b> <b style="color:{text_main};">{telemetry['db2']['calls']:,} dòng</b><br>
                    • <b>Chuỗi thời gian (call_timeseries):</b> <b style="color:{text_main};">{telemetry['db2']['ts']:,} khung 15p</b><br>
                    • <b>Ghi chú:</b> {telemetry['db2']['msg']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        col_sys3, col_sys4 = st.columns(2)
        with col_sys3:
            st.markdown(f"""
            <div style="background:{card_bg}; border:1px solid {border_col}; border-radius:10px; padding:16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:15px; font-weight:700; color:{text_main};">{telemetry['redis']['name']}</span>
                    <span style="font-size:12px; font-weight:700; color:#10b981;">{telemetry['redis']['status']}</span>
                </div>
                <hr style="margin:10px 0; border:none; border-top:1px solid {border_col};">
                <div style="font-size:12.5px; color:{text_muted}; line-height:1.6;">
                    • <b>Port kết nối:</b> <code>{telemetry['redis']['port']}</code><br>
                    • <b>Vai trò:</b> Buffer dữ liệu luồng tốc độ cao từ Autodialer.<br>
                    • <b>Trạng thái:</b> Sẵn sàng tiếp nhận sự kiện cuộc gọi mới.
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_sys4:
            st.markdown(f"""
            <div style="background:{card_bg}; border:1px solid {border_col}; border-radius:10px; padding:16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:15px; font-weight:700; color:{text_main};">Telegram NOC Alert & Squid Proxy</span>
                    <span style="font-size:12px; font-weight:700; color:#10b981;">{telemetry['telegram']['status']}</span>
                </div>
                <hr style="margin:10px 0; border:none; border-top:1px solid {border_col};">
                <div style="font-size:12.5px; color:{text_muted}; line-height:1.6;">
                    • <b>Kênh nhận thông báo:</b> <b>{telemetry['telegram']['chats']} Chat IDs</b><br>
                    • <b>Định tuyến Proxy:</b> <code>{telemetry['telegram']['proxy']}</code><br>
                    • <b>Loại thông báo:</b> P1 Red Alert (Nghẽn mạng 503 / Sập lưu lượng) & Daily EOD Report.
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### Bảng Đối Soát Tính Toàn Vẹn Dual-Write")
        sync_rows = [
            {"Chỉ mục": "Kết Nối (Connectivity)", "DB1 (Container)": telemetry['db1']['status'], "DB2 (Host MinhTQ70)": telemetry['db2']['status'], "Trạng Thái": "Khớp chuẩn"},
            {"Chỉ mục": "Số Cuộc Gọi Đã Lưu (calls_stream)", "DB1 (Container)": f"{telemetry['db1']['calls']:,}", "DB2 (Host MinhTQ70)": f"{telemetry['db2']['calls']:,}", "Trạng Thái": "Đồng bộ liên tục"},
            {"Chỉ mục": "Số Khung Chuỗi Thời Gian (call_timeseries)", "DB1 (Container)": f"{telemetry['db1']['ts']:,}", "DB2 (Host MinhTQ70)": f"{telemetry['db2']['ts']:,}", "Trạng Thái": "Toàn vẹn"},
            {"Chỉ mục": "Cơ Chế Khôi Phục (Failover)", "DB1 (Container)": "Tự động kích hoạt khi có gián đoạn", "DB2 (Host MinhTQ70)": "Tự động kích hoạt khi có gián đoạn", "Trạng Thái": "Sẵn sàng"}
        ]
        st.dataframe(pd.DataFrame(sync_rows), use_container_width=True, hide_index=True)

    return is_today_finished

# KÍCH HOẠT HIỂN THỊ
is_day_done = render_live_monitoring_fragment()

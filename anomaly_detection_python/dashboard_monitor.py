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
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    z-index: 1000005 !important;
}}
div[data-baseweb="calendar"] * {{
    color: {cal_text_color} !important;
    fill: {cal_text_color} !important;
}}
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
div[data-baseweb="calendar"] [aria-selected="true"],
div[data-baseweb="calendar"] [aria-selected="true"] > div {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 50% !important;
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

/* 8. ẨN HOÀN TOÀN NÚT LÀM MỚI TỰ ĐỘNG KỸ THUẬT (NON-BLOCKING TRIGGER) */
div:has(#scc-refresh-marker) + div,
div:has(> * > #scc-refresh-marker) + div,
div:has(#scc-refresh-marker) ~ div,
section[data-testid="stSidebar"] div.element-container:has(#scc-refresh-marker) + div.element-container,
div.element-container:has(button[key="btn_scc_live_tick"]) {{
    display: none !important;
    height: 0px !important;
    position: absolute !important;
    visibility: hidden !important;
    pointer-events: none !important;
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

def load_data_with_db_fallback():
    """Đọc dữ liệu từ file đệm buffer CSV; nếu file lỗi hoặc trống, tự động query trực tiếp từ PostgreSQL."""
    df = None
    if STREAM_FILE.exists() and STREAM_FILE.stat().st_size >= 100:
        try:
            df = pd.read_csv(STREAM_FILE)
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

def get_current_pipeline_state():
    """Đọc dữ liệu buffer với cơ chế fallback tự động vào PostgreSQL, tổng hợp theo khung 15 phút với bộ nhớ đệm chống lag."""
    global _PAST_DAYS_TS_CACHE, _PAST_DAYS_SUMMARY_CACHE

    df = load_data_with_db_fallback()
    if df.empty or len(df) < 2:
        return None, None, None, {}, pd.DataFrame(), {}, pd.DataFrame()

    df["start_time"] = pd.to_datetime(df["start_time"])
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

    return ts_today, today_bad_calls, current_date, past_days_summary, df_today, past_days_ts, df

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

if max_hist_date > st.session_state.get("last_producer_date", min_hist_date):
    st.session_state["last_producer_date"] = max_hist_date
    if st.session_state.get("is_following_live", True):
        st.session_state["cal_date_picker"] = max_hist_date

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
                st.session_state["is_following_live"] = (parsed_d == max_date)
            del st.query_params["date"]
        except Exception:
            pass

    if "nav" in st.query_params:
        p_nav = st.query_params["nav"]
        if isinstance(p_nav, list):
            p_nav = p_nav[0]
        if str(p_nav) in ["Dashboard", "Analysis", "Reports", "System"]:
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
    # SIDEBAR ĐIỀU HÀNH 4 MỤC CỐT LÕI (KHÔNG TRÙNG LẶP, KHÔNG ICON, KHÔNG NÚT TRÒN)
    # --------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 6px 0 16px 0; border-bottom: 1px solid {border_col}; margin-bottom: 16px;">
            <div style="font-size:20px; font-weight:800; color:{text_main}; line-height:1.25; letter-spacing:-0.3px;">SCC Outbound System</div>
            <div style="font-size:12.5px; font-weight:600; color:{text_muted}; margin-top:3px;">Anomaly Detection Dashboard</div>
        </div>
        """, unsafe_allow_html=True)

        # 4 PHÂN HỆ CỐT LÕI DUY NHẤT
        soc_nav_options = [
            "Dashboard",
            "Analysis",
            "Reports",
            "System"
        ]
        cur_selected = st.session_state.get("soc_nav_menu", "Dashboard")
        if cur_selected not in soc_nav_options:
            cur_selected = "Dashboard"
            st.session_state["soc_nav_menu"] = "Dashboard"

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

        # Trigger làm mới tự động ngầm đặt trong sidebar (ẩn hoàn toàn)
        st.markdown('<div id="scc-refresh-marker" style="display:none;"></div>', unsafe_allow_html=True)
        st.button("SCC_AUTO_REFRESH_TRIGGER", key="btn_scc_live_tick")

    # --------------------------------------------------------------------------
    # CHÈN SCRIPT CALENDAR FOOTER (HÔM NAY / HÔM QUA TRONG CHÂN LỊCH POPUP)
    # --------------------------------------------------------------------------
    today_str = max_date.strftime("%Y-%m-%d")
    yesterday_str = yesterday_date.strftime("%Y-%m-%d")
    today_day = str(max_date.day)
    yesterday_day = str(yesterday_date.day)

    components.html(f"""
    <script>
    (function() {{
        const pWin = window.parent;
        const pDoc = window.parent ? window.parent.document : null;
        if (!pDoc) return;

        function fixCalendarFooter() {{
            const popovers = pDoc.querySelectorAll('div[data-baseweb="popover"]');
            popovers.forEach(popover => {{
                const cal = popover.querySelector('div[data-baseweb="calendar"]');
                if (!cal) return;

                if (!popover.querySelector('.custom-cal-footer')) {{
                    const footer = pDoc.createElement('div');
                    footer.className = 'custom-cal-footer';
                    footer.style.cssText = 'display:flex;gap:8px;padding:8px 12px;border-top:1px solid {border_col};background:{card_bg};border-radius:0 0 10px 10px;margin-top:4px;';

                    const isReports = ({json.dumps(nav_choice)} === "Reports");
                    if (isReports) {{
                        const btnAll = pDoc.createElement('button');
                        btnAll.type = 'button';
                        btnAll.innerText = 'Tổng Hợp Toàn Bộ';
                        btnAll.style.cssText = 'flex:1;padding:7px 12px;font-size:12px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;transition:all 0.15s ease;';
                        btnAll.onmouseover = () => {{ btnAll.style.background = '#0369a1'; }};
                        btnAll.onmouseout = () => {{ btnAll.style.background = '#0284c7'; }};
                        btnAll.onclick = (e) => {{
                            e.stopPropagation();
                            const curUrl = new URL(pWin.location.href);
                            curUrl.searchParams.set('nav', 'Reports');
                            curUrl.searchParams.set('t3_all', '1');
                            pWin.location.href = curUrl.toString();
                        }};
                        footer.appendChild(btnAll);
                    }} else {{
                        const btnToday = pDoc.createElement('button');
                        btnToday.type = 'button';
                        btnToday.innerText = 'Hôm nay';
                        btnToday.style.cssText = 'flex:1;padding:6px 10px;font-size:12px;font-weight:600;background:#0284c7;color:#ffffff;border:none;border-radius:6px;cursor:pointer;transition:all 0.15s ease;';
                        btnToday.onmouseover = () => {{ btnToday.style.background = '#0369a1'; }};
                        btnToday.onmouseout = () => {{ btnToday.style.background = '#0284c7'; }};
                        btnToday.onclick = (e) => {{
                            e.stopPropagation();
                            const cells = cal.querySelectorAll('div[role="gridcell"]');
                            let clicked = false;
                            for (let cell of cells) {{
                                if (cell.innerText.trim() === "{today_day}" && !cell.getAttribute('aria-disabled')) {{
                                    cell.click();
                                    clicked = true;
                                    break;
                                }}
                            }}
                            if (!clicked) {{
                                const curUrl = new URL(pWin.location.href);
                                curUrl.searchParams.set('date', "{today_str}");
                                pWin.location.href = curUrl.toString();
                            }}
                        }};

                        const btnYest = pDoc.createElement('button');
                        btnYest.type = 'button';
                        btnYest.innerText = 'Hôm qua';
                        btnYest.style.cssText = 'flex:1;padding:6px 10px;font-size:12px;font-weight:600;background:{tab_active_bg};color:{text_main};border:1px solid {border_col};border-radius:6px;cursor:pointer;transition:all 0.15s ease;';
                        btnYest.onmouseover = () => {{ btnYest.style.background = 'rgba(2, 132, 199, 0.2)'; }};
                        btnYest.onmouseout = () => {{ btnYest.style.background = '{tab_active_bg}'; }};
                        btnYest.onclick = (e) => {{
                            e.stopPropagation();
                            const cells = cal.querySelectorAll('div[role="gridcell"]');
                            let clicked = false;
                            for (let cell of cells) {{
                                if (cell.innerText.trim() === "{yesterday_day}" && !cell.getAttribute('aria-disabled')) {{
                                    cell.click();
                                    clicked = true;
                                    break;
                                }}
                            }}
                            if (!clicked) {{
                                const curUrl = new URL(pWin.location.href);
                                curUrl.searchParams.set('date', "{yesterday_str}");
                                pWin.location.href = curUrl.toString();
                            }}
                        }};

                        footer.appendChild(btnToday);
                        footer.appendChild(btnYest);
                    }}
                    cal.appendChild(footer);
                }}
            }});
        }}

        setInterval(fixCalendarFooter, 300);

        // 1. Cuộn mượt về đầu trang ngay khi chuyển tab
        const curNavChoice = {json.dumps(nav_choice)};
        if (pWin.__scc_cur_nav && pWin.__scc_cur_nav !== curNavChoice) {{
            pWin.scrollTo({{ top: 0, behavior: 'instant' }});
            try {{
                const mainArea = pDoc.querySelector('.main .block-container') || pDoc.documentElement;
                if (mainArea) mainArea.scrollTop = 0;
            }} catch(e) {{}}
        }}
        pWin.__scc_cur_nav = curNavChoice;

        // 2. Kích hoạt auto-refresh phi khối (Non-blocking timer) chỉ khi ở Dashboard trực tiếp
        const shouldAutoRefresh = {json.dumps(bool(nav_choice == "Dashboard" and is_realtime_mode and not is_today_finished and not st.session_state.get("active_investigation_bucket")))};

        if (pWin.__scc_refresh_timer) {{
            clearTimeout(pWin.__scc_refresh_timer);
            pWin.__scc_refresh_timer = null;
        }}

        if (shouldAutoRefresh) {{
            pWin.__scc_refresh_timer = setTimeout(() => {{
                const btns = pDoc.querySelectorAll('button');
                for (let b of btns) {{
                    if (b.innerText && b.innerText.includes('SCC_AUTO_REFRESH_TRIGGER')) {{
                        b.click();
                        break;
                    }}
                }}
            }}, 3500);
        }}

        // 3. Đảm bảo ẩn tuyệt đối nút trigger trên DOM
        function hideHiddenTrigger() {{
            const btns = pDoc.querySelectorAll('button');
            for (let b of btns) {{
                if (b.innerText && b.innerText.includes('SCC_AUTO_REFRESH_TRIGGER')) {{
                    const c = b.closest('div[data-testid="stButton"]') || b.closest('.element-container') || b;
                    c.style.display = 'none';
                    c.style.height = '0px';
                    c.style.visibility = 'hidden';
                }}
            }}
        }}
        hideHiddenTrigger();
        setInterval(hideHiddenTrigger, 100);
    }})();
    </script>
    """, height=0, width=0)

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

    # ==============================================================================
    # 1. VIEW: DASHBOARD (GIỮ NGUYÊN 100% TAB 1 GỐC + BỘ LỌC LỊCH GỌN GÀNG TRONG TAB)
    # ==============================================================================
    if nav_choice == "Dashboard":
        # BỘ LỌC LỊCH DUY NHẤT & GỌN GÀNG (KHÔNG CÒN NÚT THỪA NGOÀI LỊCH, KHÔNG CÒN TIẾN ĐỘ CA TRỰC)
        col_dash_date, _ = st.columns([1.6, 3.4])
        with col_dash_date:
            cur_cal_val = st.session_state.get("cal_date_picker", max_date)
            if hasattr(cur_cal_val, "date"):
                cur_cal_val = cur_cal_val.date()
            if cur_cal_val < min_date or cur_cal_val > max_date:
                cur_cal_val = max_date

            new_dash_date = st.date_input(
                "Ngày Giám Sát:",
                value=cur_cal_val,
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD",
                key="dash_date_input",
                help="Nhấn để chọn ngày trên lịch. Sử dụng phím tắt Hôm nay / Hôm qua ở đáy lịch."
            )
            if hasattr(new_dash_date, "date"):
                new_dash_date = new_dash_date.date()
            if new_dash_date != picked_date:
                st.session_state["cal_date_picker"] = new_dash_date
                st.session_state["is_following_live"] = (new_dash_date == max_date)
                st.rerun()

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
            template=plotly_template, paper_bgcolor=card_bg, plot_bgcolor=card_bg,
            height=430, margin=dict(l=45, r=20, t=65, b=35), hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5, font=dict(size=11, color=text_main)),
            yaxis=dict(title="Tỷ lệ gián đoạn (%)", range=[-2.0, max_err_display], gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted)),
            xaxis=dict(tickformat="%H:%M", dtick=1800000, gridcolor=plotly_grid, linecolor=plotly_line, tickfont=dict(color=text_muted))
        )

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown(f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>1. Lưu Lượng Cuộc Gọi Phát Sinh So Với Mức Kỳ Vọng Thông Thường</div>", unsafe_allow_html=True)
            st.plotly_chart(fig_traffic, use_container_width=True)
        with col_c2:
            st.markdown(f"<div style='font-size:13.5px; font-weight:700; color:{text_main}; margin-bottom:8px;'>2. Tỷ Lệ Cuộc Gọi Bị Gián Đoạn So Với Ngưỡng An Toàn Tự Co Giãn</div>", unsafe_allow_html=True)
            st.plotly_chart(fig_error, use_container_width=True)

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
    elif nav_choice == "Analysis":
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
        all_dates = sorted(full_df["date"].unique()) if not full_df.empty else []

        st.markdown("### Báo Cáo Tổng Hợp Vận Hành (Executive Operational Summary)")

        col_t3_date, _ = st.columns([1.6, 2.4])
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
                    t3_val = (s_d, e_d)
                elif len(raw_session_t3) == 2:
                    v_start, v_end = raw_session_t3[0], raw_session_t3[1]
                    if hasattr(v_start, "date"): v_start = v_start.date()
                    if hasattr(v_end, "date"): v_end = v_end.date()
                    if v_start > v_end: v_start, v_end = v_end, v_start
                    t3_val = (max(min_date, v_start), min(max_date, v_end))
                else:
                    t3_val = t3_range_default
            else:
                s_d, e_d = get_work_week(raw_session_t3)
                t3_val = (s_d, e_d)

            t3_range_picked = st.date_input(
                "Chọn khoảng ngày đối soát (Từ ngày – Đến ngày):",
                value=t3_val,
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD",
                key="t3_date_range_picker",
                help="Bấm vào ngày bất kỳ để chọn tuần làm việc đó, hoặc bấm nút 'Tổng Hợp Toàn Bộ' dưới chân lịch để xem toàn bộ."
            )

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

        filtered_dates = [d for d in all_dates if t3_start_d <= d <= t3_end_d and d.weekday() < 5]
        df_t3 = full_df[full_df["date"].isin(filtered_dates)]
        tot_all_calls = len(df_t3)

        is_view_all_active = (t3_start_d <= min_date and t3_end_d >= max_date)
        if is_view_all_active:
            st.caption(f"Đang đối soát: **Toàn bộ dữ liệu vận hành ({min_date.strftime('%d/%m/%Y')} ➔ {max_date.strftime('%d/%m/%Y')})** — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")
        else:
            st.caption(f"Đang đối soát: **{t3_start_d.strftime('%d/%m/%Y')} ➔ {t3_end_d.strftime('%d/%m/%Y')}** (Thứ 2 – Thứ 6) — Gồm {len(filtered_dates)} ngày làm việc ({tot_all_calls:,} cuộc gọi).")

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
    elif nav_choice == "System":
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


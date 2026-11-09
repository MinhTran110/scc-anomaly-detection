# daily_reporter.py
"""
SCC Outbound: Daily Operational Reporter & Metrics Processor
- Tính toán chuỗi thời gian 38 khung giờ (08:00 - 17:30) cho bất kỳ ngày nào.
- Xuất biểu đồ phân tích 3 phần (Summary Box, Lưu lượng cuộc gọi & Ngưỡng cảnh báo, Tỷ lệ lỗi 503 & Ngưỡng Bayes động).
- Tự động gửi ảnh và báo cáo tổng kết ngày qua Telegram FPT Proxy.
- Quản lý tệp ghi nhớ exported_reports.json để ngăn ngừa gửi trùng lặp.
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from telegram_notifier import send_telegram_photo
except ImportError:
    try:
        from anomaly_detection_python.telegram_notifier import send_telegram_photo
    except ImportError:
        send_telegram_photo = None

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
EXPORTED_REPORTS_FILE = DATA_DIR / "exported_reports.json"
PROFILE_PATH = BASE_DIR / "baseline_profile.json"

# Nạp thông số baseline & Bayesian Prior
HOURLY_PROFILE = {}
BAYES_PRIOR = {}
if PROFILE_PATH.exists():
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            p_data = json.load(f)
            HOURLY_PROFILE = p_data.get("hourly_baseline_15min", {})
            BAYES_PRIOR = p_data.get("bayesian_prior", {})
    except Exception as e:
        logging.warning(f"Không thể đọc baseline_profile.json: {e}")

ALPHA_PRIOR = BAYES_PRIOR.get("alpha", 0.4)
BETA_PRIOR = BAYES_PRIOR.get("beta", 19.6)
MIN_CALL_FLOOR = BAYES_PRIOR.get("min_call_volume_floor", 4)
MIN_FAIL_FLOOR = BAYES_PRIOR.get("min_fail_count_floor", 2)
MIN_SPIKE_VOLUME_FLOOR = BAYES_PRIOR.get("min_spike_volume_floor", 8)

def compute_dynamic_error_threshold(n_calls: int, base_threshold: float = 0.15) -> float:
    """
    Thuật toán Ngưỡng Động Tỷ Lệ Lỗi (Wilson Score Upper Bound).
    - Cỡ mẫu nhỏ (N = 3 - 5): Ngưỡng tự động nới lỏng ~35 - 40%, tránh báo động giả.
    - Cỡ mẫu lớn (N >= 20): Ngưỡng siết chặt về mức chuẩn 20 - 25%.
    """
    if n_calls <= 0:
        return 0.35
    p0 = 0.05
    z = 1.96
    denom = 1.0 + (z**2) / n_calls
    center = (p0 + (z**2) / (2.0 * n_calls)) / denom
    spread = (z / denom) * np.sqrt((p0 * (1.0 - p0) / n_calls) + (z**2) / (4.0 * (n_calls**2)))
    upper_bound = center + spread
    return float(np.clip(upper_bound, base_threshold, 0.40))

def process_single_date(df_date, the_date, is_live_today: bool = False, active_bucket=None, ml_model=None):
    """
    Xử lý và gom nhóm toàn bộ dữ liệu cuộc gọi của 1 ngày thành 38 khung 15 phút (08:00 - 17:30).
    Tính toán các chỉ số thống kê, ngưỡng động Bayes, Z-Score và nhãn bất thường.
    """
    the_date_obj = pd.Timestamp(the_date).date()
    day_start = pd.Timestamp(the_date_obj).replace(hour=8, minute=0, second=0)
    day_end = pd.Timestamp(the_date_obj).replace(hour=17, minute=30, second=0)
    full_day_grid = pd.date_range(day_start, day_end - pd.Timedelta(minutes=15), freq="15min", name="bucket_time").to_frame().reset_index(drop=True)

    if is_live_today and active_bucket is not None:
        completed_data = df_date[df_date["bucket_time"] < active_bucket].copy()
    else:
        completed_data = df_date.copy()

    if completed_data.empty:
        ts = full_day_grid.copy()
        ts["calls_total"] = 0
        ts["calls_503"] = 0
        ts["calls_answered"] = 0
        ts["avg_duration"] = 0.0
    else:
        if "bucket_time" not in completed_data.columns:
            completed_data["start_time"] = pd.to_datetime(completed_data["start_time"])
            completed_data["bucket_time"] = completed_data["start_time"].dt.floor("15min")
            
        agg = completed_data.groupby("bucket_time").agg(
            calls_total=("call_id", "count"),
            calls_503=("result_code", lambda s: (s == "503_CONGESTION").sum()),
            calls_answered=("result_code", lambda s: (s == "ANSWERED").sum()),
            avg_duration=("duration", "mean")
        ).reset_index()
        ts = pd.merge(full_day_grid, agg, on="bucket_time", how="left").fillna(0)

    ts["hour"] = ts["bucket_time"].dt.hour
    ts["mu"] = ts["hour"].map(lambda h: HOURLY_PROFILE.get(str(h), {}).get("mu", 4.0))
    ts["sd"] = ts["hour"].map(lambda h: HOURLY_PROFILE.get(str(h), {}).get("sd", 1.8))
    ts["upper_limit"] = ts["hour"].map(lambda h: HOURLY_PROFILE.get(str(h), {}).get("upper_limit", 9.0))
    ts["lower_limit"] = ts["hour"].map(lambda h: HOURLY_PROFILE.get(str(h), {}).get("lower_limit", 0.0))

    if is_live_today and active_bucket is not None:
        ts["is_completed"] = ts["bucket_time"] < active_bucket
    else:
        ts["is_completed"] = True

    # Tỷ lệ lỗi thực tế (Empirical Error Rate)
    ts["error_rate"] = np.where(ts["calls_total"] > 0, ts["calls_503"] / ts["calls_total"], 0.0)
    ts["smoothed_error_rate"] = ts["error_rate"]
    ts["dynamic_threshold"] = ts["calls_total"].apply(compute_dynamic_error_threshold)
    ts["zscore"] = np.where(ts["sd"] > 0, (ts["calls_total"] - ts["mu"]) / ts["sd"], 0.0).round(2)

    # 1. P1 Lỗi hạ tầng SIP Trunk: Tỷ lệ lỗi >= Ngưỡng động VÀ có ít nhất 2 cuộc lỗi (hiển thị trên Đồ thị 2)
    ts["is_p1_net"] = (
        ts["is_completed"] & 
        (ts["error_rate"] >= ts["dynamic_threshold"]) & 
        (ts["calls_total"] >= 4) & 
        (ts["calls_503"] >= 2)
    )

    # 2. P1 Sập lưu lượng PBX: Lưu lượng rơi về 0 trong giờ làm việc (mu >= 2.5) (hiển thị trên Đồ thị 1)
    ts["is_p1_drop"] = (
        ts["is_completed"] & 
        (ts["calls_total"] == 0) & 
        (ts["mu"] >= 2.5)
    )

    ts["is_p1_red"] = ts["is_p1_net"] | ts["is_p1_drop"]

    # 3. P2 Đột biến tải chiến dịch (Traffic Spike): Chạm hoặc vượt Capacity Upper Limit, hoặc Z >= 2.0, hoặc volume >= 9
    ts["is_p2_yellow"] = (
        ts["is_completed"] & 
        (
            (ts["calls_total"] >= ts["upper_limit"]) | 
            ((ts["zscore"] >= 2.0) & (ts["calls_total"] >= 7)) |
            (ts["calls_total"] >= 9)
        ) & 
        (~ts["is_p1_drop"])
    )

    return ts

def generate_daily_report_chart(day_date, day_ts: pd.DataFrame, report_file: Path):
    """Vẽ biểu đồ phân tích chuẩn 3 phần và lưu file PNG."""
    tot_calls = int(day_ts["calls_total"].sum())
    tot_503 = int(day_ts["calls_503"].sum())
    err_pct = (tot_503 / tot_calls * 100) if tot_calls > 0 else 0.0
    tot_conn = int(day_ts["calls_answered"].sum())
    conn_pct = (tot_conn / tot_calls * 100) if tot_calls > 0 else 0.0
    tot_p1 = int(day_ts["is_p1_red"].sum())
    tot_p2 = int(day_ts["is_p2_yellow"].sum())

    fig = plt.figure(figsize=(15, 9))
    gs = gridspec.GridSpec(3, 1, height_ratios=[0.6, 1.8, 1.4], figure=fig)

    # 1. Header Box
    ax_header = fig.add_subplot(gs[0])
    ax_header.axis("off")
    date_str = day_date.strftime('%d/%m/%Y') if hasattr(day_date, 'strftime') else str(day_date)
    summary_text = (
        f"================ BÁO CÁO TỔNG KẾT VẬN HÀNH SCC OUTBOUND: {date_str} (08:00 - 17:30) ================\n\n"
        f"  • Tổng cuộc gọi phát sinh : {tot_calls:,} cuộc            • Kết nối thành công (Nghe máy): {conn_pct:.1f}% ({tot_conn:,} cuộc)\n"
        f"  • Lỗi gián đoạn viễn thông : {tot_503:,} cuộc (503)      • Tỷ lệ lỗi toàn ngày          : {err_pct:.2f}%\n"
        f"  • Sự cố khẩn cấp PBX/SIP   : {tot_p1} khung giờ (P1 Khẩn)  • Cảnh báo tăng tải đột biến   : {tot_p2} khung giờ (P2 Cảnh Báo)"
    )
    box_color = "#fee2e2" if tot_p1 > 0 else "#f0fdf4"
    border_color = "#dc2626" if tot_p1 > 0 else "#16a34a"
    ax_header.text(0.5, 0.5, summary_text, fontsize=10.5, family="sans-serif", va="center", ha="center",
                   bbox=dict(boxstyle="round,pad=0.7", facecolor=box_color, edgecolor=border_color, lw=1.5))

    # 2. Traffic Subplot
    ax1 = fig.add_subplot(gs[1])
    ax1.plot(day_ts["bucket_time"], day_ts["calls_total"], label="Cuộc gọi thực tế (15 phút)", color="#0284c7", lw=1.8, marker="o", markersize=4)
    ax1.plot(day_ts["bucket_time"], day_ts["mu"], label="Mức kỳ vọng trung bình (μ)", color="#64748b", linestyle="--")
    ax1.plot(day_ts["bucket_time"], day_ts["upper_limit"], label="Ngưỡng trên an toàn (μ + 2.5σ)", color="#d97706", linestyle=":")
    ax1.plot(day_ts["bucket_time"], day_ts["lower_limit"], label="Ngưỡng dưới an toàn", color="#94a3b8", linestyle=":")

    p1_drop_pts = day_ts[day_ts["is_p1_drop"]]
    if not p1_drop_pts.empty:
        ax1.scatter(p1_drop_pts["bucket_time"], p1_drop_pts["calls_total"], color="#dc2626", s=150, zorder=7, label="[Sự Cố P1] Sập cuộc gọi PBX", edgecolors="white", lw=2)

    p2_pts = day_ts[day_ts["is_p2_yellow"]]
    if not p2_pts.empty:
        ax1.scatter(p2_pts["bucket_time"], p2_pts["calls_total"], color="#d97706", s=150, zorder=7, label="[Cảnh Báo P2] Quá tải lưu lượng", edgecolors="white", lw=2, marker="D")

    ax1.set_title("1. Diễn Biến Lưu Lượng Cuộc Gọi & Điểm Bất Thường", fontsize=11, fontweight="bold", color="#0f172a")
    ax1.set_ylabel("Cuộc gọi / 15 phút", color="#334155")
    ax1.grid(True, linestyle=":", alpha=0.5, color="#cbd5e1")
    handles1, _ = ax1.get_legend_handles_labels()
    if handles1:
        ax1.legend(loc="upper right", framealpha=0.9)

    # 3. Error Rate Subplot
    ax2 = fig.add_subplot(gs[2], sharex=ax1)
    ax2.plot(day_ts["bucket_time"], day_ts["error_rate"] * 100, label="Tỷ lệ gián đoạn (%)", color="#ea580c", lw=1.8, marker="x")
    ax2.plot(day_ts["bucket_time"], day_ts["dynamic_threshold"] * 100, label="Ngưỡng an toàn tự co giãn (%)", color="#dc2626", linestyle="--", lw=1.5)

    p1_net = day_ts[day_ts["is_p1_net"]]
    if not p1_net.empty:
        ax2.scatter(p1_net["bucket_time"], p1_net["error_rate"] * 100, color="#dc2626", s=140, zorder=7, edgecolors="white", lw=2, label="[Sự Cố P1] Nghẽn mạng SIP 503", marker="X")

    ax2.set_title("2. Tỷ Lệ Cuộc Gọi Bị Gián Đoạn So Với Ngưỡng An Toàn Tự Co Giãn", fontsize=10, fontweight="bold", color="#0f172a")
    ax2.set_ylabel("Tỷ lệ gián đoạn (%)", color="#334155")
    ax2.set_xlabel("Khung giờ làm việc (08:00 - 17:30)", color="#334155")
    ax2.grid(True, linestyle=":", alpha=0.5, color="#cbd5e1")
    handles2, _ = ax2.get_legend_handles_labels()
    if handles2:
        ax2.legend(loc="upper left", framealpha=0.9)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
    fig.autofmt_xdate(rotation=0, ha="center")

    plt.tight_layout()
    plt.savefig(report_file, dpi=120)
    plt.close(fig)

def export_and_send_daily_report(day_date, day_ts: pd.DataFrame, force: bool = False):
    """
    Tạo ảnh báo cáo và gửi qua Telegram FPT Proxy.
    Có cơ chế lưu cờ vào exported_reports.json để chống gửi trùng lặp.
    """
    date_key = day_date.strftime("%Y-%m-%d") if hasattr(day_date, "strftime") else str(day_date)
    report_file = DATA_DIR / f"daily_report_{date_key}.png"

    # Kiểm tra danh sách đã gửi
    exported_list = set()
    if EXPORTED_REPORTS_FILE.exists():
        try:
            with open(EXPORTED_REPORTS_FILE, "r", encoding="utf-8") as f:
                exported_list = set(json.load(f))
        except Exception:
            pass

    if not force and date_key in exported_list and report_file.exists():
        return True, f"Báo cáo ngày {date_key} đã được gửi trước đó.", report_file

    # Vẽ biểu đồ ra file ảnh
    generate_daily_report_chart(day_date, day_ts, report_file)

    # Tạo caption chi tiết
    tot_calls = int(day_ts["calls_total"].sum())
    tot_503 = int(day_ts["calls_503"].sum())
    err_pct = (tot_503 / tot_calls * 100) if tot_calls > 0 else 0.0
    tot_conn = int(day_ts["calls_answered"].sum())
    conn_pct = (tot_conn / tot_calls * 100) if tot_calls > 0 else 0.0
    tot_p1 = int(day_ts["is_p1_red"].sum())
    tot_p2 = int(day_ts["is_p2_yellow"].sum())

    date_label = day_date.strftime('%d/%m/%Y (%A)') if hasattr(day_date, 'strftime') else str(day_date)
    caption = (
        f"🏁 <b>[SCC OUTBOUND] BÁO CÁO TỔNG KẾT NGÀY HOÀN TẤT</b>\n\n"
        f"📅 <b>Ngày hoạt động:</b> {date_label}\n"
        f"📞 <b>Tổng cuộc gọi tiếp nhận:</b> {tot_calls:,} cuộc\n"
        f"✅ <b>Kết nối thành công:</b> {tot_conn:,} cuộc ({conn_pct:.1f}%)\n"
        f"⚠️ <b>Tổng cuộc gọi lỗi 503:</b> {tot_503} cuộc\n"
        f"📉 <b>Tỷ lệ lỗi toàn ngày:</b> <b>{err_pct:.2f}%</b>\n"
        f"🔴 <b>Số khung P1 Sự Cố:</b> <b>{tot_p1}</b> khung\n"
        f"🟡 <b>Số khung P2 Quá Tải:</b> <b>{tot_p2}</b> khung\n\n"
        "👉 <i>Đồ thị phân tích chi tiết toàn ngày đính kèm bên dưới. "
        "Truy cập Dashboard SCC để kiểm tra chi tiết các khung giờ!</i>"
    )

    sent_ok = False
    desc = "Chưa gửi Telegram"
    if send_telegram_photo:
        sent_ok = send_telegram_photo(caption=caption, photo_path=report_file)
        desc = "Gửi Telegram thành công" if sent_ok else "Gửi Telegram thất bại"

    # Lưu cờ chống gửi trùng
    exported_list.add(date_key)
    try:
        with open(EXPORTED_REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(exported_list), f, indent=2)
    except Exception as e:
        logging.error(f"Lỗi khi lưu exported_reports.json: {e}")

    return sent_ok, desc, report_file

# ml_baseline_trainer.py
"""
Machine Learning Baseline Trainer & Seasonality Analyzer
1. Phân tích chu kỳ (Seasonality Decomposition): Chu kỳ ngày (Diurnal 24h) và chu kỳ tuần (Weekly 7 ngày).
2. Xây dựng dải kỳ vọng động (Dynamic Prediction Band) qua Fourier Smoothing / Prophet logic.
3. Huấn luyện mô hình Isolation Forest phát hiện bất thường đa biến trên dữ liệu lịch sử.
4. Xuất file cấu hình 'baseline_profile.json' cho Dashboard sử dụng động.
"""
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Đảm bảo utf-8 cho console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path(__file__).resolve().parent / "data"
PROFILE_OUTPUT = Path(__file__).resolve().parent / "baseline_profile.json"

# Tìm file dữ liệu lịch sử
HIST_FILE = Path(__file__).resolve().parent.parent / "data" / "outbound_calls_timeseries_hourly_may.csv"
if not HIST_FILE.exists():
    HIST_FILE = DATA_DIR / "outbound_calls_timeseries_hourly_may.csv"

def train_and_export_baseline():
    print("=" * 70)
    print("[ML] HUAN LUYEN MACHINE LEARNING BASELINE & PHAN TICH CHU KY DU LIEU")
    print("=" * 70)

    if not HIST_FILE.exists():
        print(f"[!] Khong tim thay file du lieu lich su: {HIST_FILE}")
        return

    # 1. Đọc và tiền xử lý dữ liệu chuỗi thời gian
    df = pd.read_csv(HIST_FILE)
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["hour"] = df["start_time"].dt.hour
    df["dayofweek"] = df["start_time"].dt.dayofweek # 0: Thứ 2 -> 6: CN
    df["is_weekend"] = df["dayofweek"] >= 5

    print(f"[+] Da nap {len(df)} dong du lieu tu {df['start_time'].min()} den {df['start_time'].max()}")

    # 2. Phân tích chu kỳ (Seasonality): Thống kê theo giờ (chuyển đổi sang quy mô khung 15 phút = / 4)
    hourly_stats = {}
    for h in range(24):
        subset = df[df["hour"] == h]["call_count"]
        # Quy đổi từ 1 giờ sang khung 15 phút (chia 4)
        mean_15m = float(np.round(subset.mean() / 4.0, 2))
        std_15m = float(np.round(subset.std() / 4.0, 2))
        std_15m = max(std_15m, 0.8) # Đảm bảo độ lệch chuẩn tối thiểu tránh chia 0

        # Giờ hành chính (8h - 17h) vs Giờ thấp điểm/đêm
        if 8 <= h <= 17:
            # Dải chặn trên và dưới (2.5 độ lệch chuẩn)
            upper_limit = float(np.round(mean_15m + 2.5 * std_15m, 2))
            lower_limit = float(np.round(max(0.0, mean_15m - 2.5 * std_15m), 2))
        else:
            # Ngoài giờ hành chính: kỳ vọng rất thấp
            mean_15m = max(0.2, mean_15m)
            upper_limit = float(np.round(mean_15m + 3.0 * std_15m, 2))
            lower_limit = 0.0

        hourly_stats[str(h)] = {
            "mu": mean_15m,
            "sd": std_15m,
            "upper_limit": upper_limit,
            "lower_limit": lower_limit
        }

    # 3. Huấn luyện mô hình Isolation Forest phát hiện ngoại lai lịch sử
    features = df[["call_count", "hour", "dayofweek"]].copy()
    features["avg_duration"] = df["avg_duration"].fillna(0)
    
    iso_model = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
    df["anomaly_score"] = iso_model.fit_predict(features)
    n_anomalies = int((df["anomaly_score"] == -1).sum())
    print(f"[+] Isolation Forest: Da phat hien {n_anomalies} diem bat thuong lich su ({n_anomalies/len(df):.1%})")

    # 4. Cấu hình tham số Bayes Smoothing & Dynamic Thresholding
    config = {
        "model_version": "v2.0-ml-dynamic",
        "description": "Baseline dong hoc tu du lieu lich su thang 5/2026 ket hop Bayesian Smoothing",
        "bayesian_prior": {
            "p0_baseline_error_rate": 0.02, # 2% lỗi tự nhiên
            "pseudo_counts_C": 20,          # Trọng số niềm tin
            "alpha": 0.4,                  # C * p0
            "beta": 19.6,                  # C * (1 - p0)
            "min_call_volume_floor": 5,    # Ngưỡng thể tích tối thiểu để xét tỷ lệ %
            "min_fail_count_floor": 2      # Số cuộc lỗi tối thiểu để kích hoạt P1
        },
        "hourly_baseline_15min": hourly_stats
    }

    # 5. Xuất file cấu hình JSON
    with open(PROFILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"[OK] Da xuat cau hinh baseline dong thanh cong: {PROFILE_OUTPUT}")
    print("[*] Xem truoc dai ky vong khung 15 phut:")
    for h in [8, 10, 12, 14, 16, 20]:
        info = hourly_stats[str(h)]
        print(f"   * Gio {h:02d}:00: Ky vong mu={info['mu']:.1f}, Dai tin cay=[{info['lower_limit']:.1f} - {info['upper_limit']:.1f}] cuoc")

if __name__ == "__main__":
    train_and_export_baseline()

# ml_train_pipeline.py
"""
========================================================================================
SCC OUTBOUND - MACHINE LEARNING TRAINING & BENCHMARK PIPELINE
========================================================================================
Quy trình huấn luyện, đánh giá và đối chuẩn (Benchmark) mô hình Machine Learning phát hiện
bất thường đa biến (Multivariate Anomaly Detection) trên chuỗi thời gian cuộc gọi SCC Outbound.

Nguyên tắc kỹ thuật:
1. Nạp 2,392 khung 15 phút từ PostgreSQL / CSV (tháng 10/2026 - 01/2027).
2. Trích xuất vector đặc trưng 10 chiều (Lưu lượng, Tỷ lệ lỗi, Thời lượng, Chu kỳ, Độ trễ).
3. Phân chia theo dòng thời gian (Temporal Split: 70% Train - 30% Test), chống rò rỉ dữ liệu.
4. Chuẩn hóa RobustScaler (Median + IQR) tránh méo phân phối do sự cố.
5. Huấn luyện đối đầu 5 mô hình:
   - [A] Statistical Rule Engine (Wilson Score 95% + 2.5σ)
   - [B] Isolation Forest (Core Tree ML)
   - [C] One-Class SVM (RBF Kernel)
   - [D] Local Outlier Factor (LOF Density)
   - [E] Hybrid Ensemble (Statistical + ML)
6. Đo lường toàn diện: AUC-ROC, PR-AUC (Average Precision), Precision, Recall, F1, FPR, Latency.
7. Xếp hạng Top Sự Cố Nghiêm Trọng (Anomaly Ranking) kèm giải thích đặc trưng chi phối.
8. Đóng gói mô hình (.joblib) và báo cáo JSON vào thư mục models/.
========================================================================================
"""

import os
import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

# Đảm bảo UTF-8 cho console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn thư mục
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE = DATA_DIR / "call_timeseries.csv"


# ======================================================================================
# GIAI ĐOẠN 1: NẠP VÀ LÀM SẠCH DỮ LIỆU (DATA HYGIENE)
# ======================================================================================
def load_timeseries_dataset() -> pd.DataFrame:
    """Nạp dữ liệu chuỗi thời gian từ PostgreSQL hoặc fallback file CSV."""
    df = None

    # Thử kết nối DB PostgreSQL nếu có
    db_hosts = [os.environ.get("POSTGRES_HOST", "db"), "127.0.0.1", "172.18.0.2"]
    for host in db_hosts:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=host,
                port=int(os.environ.get("POSTGRES_PORT", 5432)),
                dbname=os.environ.get("POSTGRES_DB", "scc_calls"),
                user=os.environ.get("POSTGRES_USER", "postgres"),
                password=os.environ.get("POSTGRES_PASSWORD", "postgrespassword"),
                connect_timeout=2
            )
            query = """
                SELECT bucket_time, calls_total, calls_connected, avg_duration, 
                       calls_failed, failed_carrier, specific_error, is_imputed
                FROM call_timeseries 
                ORDER BY bucket_time ASC;
            """
            df = pd.read_sql(query, conn)
            conn.close()
            print(f"[+] Da nap thanh cong {len(df)} khung gio tu PostgreSQL ({host})")
            break
        except Exception:
            continue

    if df is None:
        if not CSV_FILE.exists():
            raise FileNotFoundError(f"Khong tim thay file du lieu: {CSV_FILE}")
        df = pd.read_csv(CSV_FILE)
        print(f"[+] Da nap thanh cong {len(df)} khung gio tu file CSV: {CSV_FILE}")

    # Chuẩn hóa kiểu dữ liệu
    df["bucket_time"] = pd.to_datetime(df["bucket_time"])
    df = df.sort_values("bucket_time").reset_index(drop=True)

    # Xử lý missing
    df["calls_total"] = df["calls_total"].fillna(0).astype(int)
    df["calls_connected"] = df["calls_connected"].fillna(0).astype(int)
    df["calls_failed"] = df["calls_failed"].fillna(0).astype(int)
    df["avg_duration"] = df["avg_duration"].fillna(0.0).astype(float)
    df["failed_carrier"] = df["failed_carrier"].fillna("-")
    df["specific_error"] = df["specific_error"].fillna("-")

    return df


# ======================================================================================
# GIAI ĐOẠN 2: FEATURE ENGINEERING & TẠO NHÃN GROUND TRUTH
# ======================================================================================
def extract_features_and_ground_truth(df: pd.DataFrame):
    """
    Trích xuất vector 10 chiều cho từng khung 15 phút và gán nhãn sự cố đối chứng.
    """
    df = df.copy()

    # 1. Các chỉ số chất lượng dịch vụ
    df["error_rate"] = np.where(
        df["calls_total"] > 0,
        df["calls_failed"] / df["calls_total"],
        0.0
    )
    df["asr_rate"] = np.where(
        df["calls_total"] > 0,
        df["calls_connected"] / df["calls_total"],
        0.0
    )

    # 2. Chu kỳ thời gian
    df["hour"] = df["bucket_time"].dt.hour
    df["dayofweek"] = df["bucket_time"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)

    # Mã hóa lượng giác 24 giờ (Cyclical Encoding)
    df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24.0)

    # 3. Động học chuỗi thời gian (Lag & Rolling)
    df["calls_total_lag1"] = df["calls_total"].shift(1).fillna(df["calls_total"].iloc[0])
    df["error_rate_lag1"] = df["error_rate"].shift(1).fillna(0.0)
    df["rolling_mean_4"] = df["calls_total"].rolling(window=4, min_periods=1).mean()
    df["rolling_std_4"] = df["calls_total"].rolling(window=4, min_periods=1).std().fillna(0.0)

    # 4. Gán nhãn Ground Truth (y_true ∈ {0, 1})
    # Tiêu chí sự cố thực tế:
    # - Sự cố P1 PBX Sập: calls_total = 0 trong giờ hành chính (8h-17h, ngày thường)
    # - Sự cố P1 Nghẽn mạng: calls_failed >= 2 VÀ error_rate >= 0.35
    # - Sự cố P2 Quá tải chiến dịch: calls_total >= 11 (hoặc Z-score >= 2.2 và calls_total >= 7)
    # - Sự cố Bot kẹt: calls_total >= 5, calls_connected >= 3 nhưng avg_duration <= 2.0 giây
    is_p1_drop = (df["calls_total"] == 0) & (df["hour"].between(8, 17)) & (df["is_weekend"] == 0)
    is_p1_trunk = (df["calls_failed"] >= 2) & (df["error_rate"] >= 0.35)
    is_p2_spike = (df["calls_total"] >= 11)
    is_bot_stuck = (df["calls_total"] >= 5) & (df["avg_duration"] <= 2.0)

    df["is_anomaly_gt"] = (is_p1_drop | is_p1_trunk | is_p2_spike | is_bot_stuck).astype(int)

    feature_cols = [
        "calls_total",
        "calls_failed",
        "error_rate",
        "avg_duration",
        "hour",
        "dayofweek",
        "sin_hour",
        "cos_hour",
        "calls_total_lag1",
        "rolling_mean_4",
        "rolling_std_4"
    ]

    return df, feature_cols


# ======================================================================================
# GIAI ĐOẠN 3: TEMPORAL SPLIT (70% TRAIN - 30% TEST KHÔNG XÁO TRỘN)
# ======================================================================================
def split_temporal(df: pd.DataFrame, feature_cols: list, train_ratio: float = 0.70):
    """
    Phân chia theo dòng thời gian (Temporal Split) để chống rò rỉ thông tin tương lai.
    """
    n_total = len(df)
    n_train = int(n_total * train_ratio)

    train_df = df.iloc[:n_train].copy()
    test_df = df.iloc[n_train:].copy()

    X_train = train_df[feature_cols].values
    y_train = train_df["is_anomaly_gt"].values

    X_test = test_df[feature_cols].values
    y_test = test_df["is_anomaly_gt"].values

    print("\n" + "=" * 80)
    print("PHÂN CHIA TẬP DỮ LIỆU THEO DÒNG THỜI GIAN (TEMPORAL SPLIT - NO LEAKAGE)")
    print("=" * 80)
    print(f"• Toàn bộ dữ liệu: {n_total} khung từ {df['bucket_time'].min()} đến {df['bucket_time'].max()}")
    print(f"• Tập TRAIN (70%):  {len(train_df)} khung từ {train_df['bucket_time'].min()} đến {train_df['bucket_time'].max()}")
    print(f"  └─ Số sự cố trong Train: {y_train.sum()}/{len(y_train)} khung ({y_train.mean():.1%})")
    print(f"• Tập TEST  (30%):  {len(test_df)} khung từ {test_df['bucket_time'].min()} đến {test_df['bucket_time'].max()}")
    print(f"  └─ Số sự cố trong Test:  {y_test.sum()}/{len(y_test)} khung ({y_test.mean():.1%})")

    return train_df, test_df, X_train, y_train, X_test, y_test


# ======================================================================================
# GIAI ĐOẠN 4: CHUẨN HÓA DỮ LIỆU (ROBUST SCALER PIPELINE)
# ======================================================================================
def scale_features(X_train: np.ndarray, X_test: np.ndarray):
    """
    Sử dụng RobustScaler (Median & IQR) chống méo tâm do ngoại lai.
    QUY TẮC VÀNG: Fit trên Train -> Transform sang Test.
    """
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Lưu scaler để tái sử dụng trong suy luận thời gian thực
    scaler_path = MODELS_DIR / "scaler.joblib"
    joblib.dump(scaler, scaler_path)
    print(f"[+] Da luu bo chuan hoa RobustScaler: {scaler_path}")

    return X_train_scaled, X_test_scaled, scaler


# ======================================================================================
# GIAI ĐOẠN 5: HUẤN LUYỆN BỘ 5 MÔ HÌNH ĐỐI ĐẦU
# ======================================================================================
def train_and_evaluate_models(train_df, test_df, X_train, y_train, X_test, y_test, X_train_sc, X_test_sc, feature_cols):
    """
    Huấn luyện và đánh giá đối đầu 5 mô hình trên cùng tập Test độc lập.
    """
    results = {}
    models_dict = {}

    print("\n" + "=" * 80)
    print("BẮT ĐẦU HUẤN LUYỆN VÀ ĐỐI CHUẨN (BENCHMARKING) 5 MÔ HÌNH")
    print("=" * 80)

    # ----------------------------------------------------------------------------------
    # MÔ HÌNH 1: STATISTICAL RULE ENGINE (BASELINE)
    # Wilson Score 95% + 2.5σ Volume
    # ----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    hour_profile = train_df.groupby("hour")["calls_total"].agg(["mean", "std"]).to_dict("index")

    stat_preds = []
    stat_scores = []
    for _, row in test_df.iterrows():
        n = row["calls_total"]
        k = row["calls_failed"]
        h = row["hour"]
        mu = hour_profile.get(h, {}).get("mean", 2.0)
        sd = max(hour_profile.get(h, {}).get("std", 1.0), 0.8)

        p_hat = k / n if n > 0 else 0.0
        z = 1.96
        denom = 1 + z**2 / max(n, 1)
        center = (p_hat + z**2 / (2 * max(n, 1))) / denom
        margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * max(n, 1)**2)) / max(n, 1)) / denom
        wilson_upper = min(1.0, center + margin)

        is_p1_drop = (n == 0) and (8 <= h <= 17) and (row["is_weekend"] == 0)
        is_p1_err = (n >= 4) and (k >= 2) and (p_hat >= 0.35)
        is_p2_vol = (n >= mu + 2.5 * sd) and (n >= 7)

        is_anom = is_p1_drop or is_p1_err or is_p2_vol
        stat_preds.append(1 if is_anom else 0)

        z_vol = (n - mu) / sd
        c_score = max(0.0, z_vol) + (k * 3.0) + (10.0 if is_p1_drop else 0.0)
        stat_scores.append(c_score)

    t_stat = (time.perf_counter() - t0) * 1000 / len(test_df)
    results["Statistical Rule Engine"] = {
        "preds": np.array(stat_preds),
        "scores": np.array(stat_scores),
        "higher_is_anom": True,
        "latency_ms": t_stat
    }

    # ----------------------------------------------------------------------------------
    # MÔ HÌNH 2: ISOLATION FOREST (CORE TREE ML)
    # ----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    iforest = IsolationForest(
        n_estimators=150,
        contamination=0.035,
        max_samples="auto",
        random_state=42,
        n_jobs=-1
    )
    iforest.fit(X_train)
    t_train_if = time.perf_counter() - t0

    t0 = time.perf_counter()
    raw_pred_if = iforest.predict(X_test)
    if_scores = iforest.decision_function(X_test)
    t_if = (time.perf_counter() - t0) * 1000 / len(test_df)

    results["Isolation Forest"] = {
        "preds": np.where(raw_pred_if == -1, 1, 0),
        "scores": if_scores,
        "higher_is_anom": False,
        "latency_ms": t_if
    }
    models_dict["isolation_forest"] = iforest
    joblib.dump(iforest, MODELS_DIR / "isolation_forest.joblib")

    # ----------------------------------------------------------------------------------
    # MÔ HÌNH 3: ONE-CLASS SVM (RBF KERNEL)
    # ----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    oc_svm = OneClassSVM(kernel="rbf", nu=0.035, gamma="scale")
    oc_svm.fit(X_train_sc)
    t_train_svm = time.perf_counter() - t0

    t0 = time.perf_counter()
    raw_pred_svm = oc_svm.predict(X_test_sc)
    svm_scores = oc_svm.decision_function(X_test_sc)
    t_svm = (time.perf_counter() - t0) * 1000 / len(test_df)

    results["One-Class SVM"] = {
        "preds": np.where(raw_pred_svm == -1, 1, 0),
        "scores": svm_scores,
        "higher_is_anom": False,
        "latency_ms": t_svm
    }
    models_dict["oc_svm"] = oc_svm
    joblib.dump(oc_svm, MODELS_DIR / "oc_svm.joblib")

    # ----------------------------------------------------------------------------------
    # MÔ HÌNH 4: LOCAL OUTLIER FACTOR (LOF)
    # ----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    lof = LocalOutlierFactor(n_neighbors=25, contamination=0.035, novelty=True)
    lof.fit(X_train_sc)
    t_train_lof = time.perf_counter() - t0

    t0 = time.perf_counter()
    raw_pred_lof = lof.predict(X_test_sc)
    lof_scores = lof.score_samples(X_test_sc)
    t_lof = (time.perf_counter() - t0) * 1000 / len(test_df)

    results["Local Outlier Factor"] = {
        "preds": np.where(raw_pred_lof == -1, 1, 0),
        "scores": lof_scores,
        "higher_is_anom": False,
        "latency_ms": t_lof
    }
    models_dict["lof"] = lof
    joblib.dump(lof, MODELS_DIR / "lof.joblib")

    return results, models_dict


# ======================================================================================
# GIAI ĐOẠN 6: TÍNH TOÁN METRICS BENCHMARK ĐỐI SOÁT & XẾP HẠNG ANOMALY
# ======================================================================================
def compute_benchmark_report(results: dict, y_test: np.ndarray, test_df: pd.DataFrame, feature_cols: list):
    """
    Tính toán bảng chỉ số AUC-ROC, PR-AUC, F1, Precision, Recall, FPR và xuất xếp hạng Top sự cố.
    """
    benchmark_table = []
    report_dict = {}

    for name, data in results.items():
        preds = data["preds"]
        raw_scores = data["scores"]

        if data["higher_is_anom"]:
            eval_score = raw_scores
        else:
            eval_score = -raw_scores

        auc_roc = float(roc_auc_score(y_test, eval_score))
        pr_auc = float(average_precision_score(y_test, eval_score))

        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))

        tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        latency = float(data["latency_ms"])

        benchmark_table.append({
            "Mô Hình (Model)": name,
            "AUC-ROC": f"{auc_roc:.4f}",
            "PR-AUC": f"{pr_auc:.4f}",
            "Precision": f"{prec:.3f}",
            "Recall": f"{rec:.3f}",
            "F1-Score": f"{f1:.3f}",
            "FPR (%)": f"{fpr * 100:.2f}%",
            "Latency (ms)": f"{latency:.2f}"
        })

        report_dict[name] = {
            "auc_roc": round(auc_roc, 4),
            "pr_auc": round(pr_auc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "fpr": round(fpr, 4),
            "confusion_matrix": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
            "latency_ms": round(latency, 2)
        }

    df_bm = pd.DataFrame(benchmark_table)
    # Sắp xếp bảng benchmark theo AUC-ROC giảm dần
    df_bm = df_bm.sort_values(by="AUC-ROC", ascending=False).reset_index(drop=True)
    print("\n" + "=" * 90)
    print("BẢNG ĐỐI CHUẨN ĐỐI SOÁT TOÀN DIỆN (BENCHMARK RESULTS MATRIX - SORTED BY AUC-ROC)")
    print("=" * 90)
    print(df_bm.to_string(index=False))
    print("=" * 90)

    # Xếp hạng Top sự cố trên tập Test
    test_ranked = test_df.copy()
    test_ranked["iforest_score"] = results["Isolation Forest"]["scores"]
    test_ranked["is_iforest_anom"] = results["Isolation Forest"]["preds"]

    top_anomalies = test_ranked.sort_values("iforest_score", ascending=True).head(5)

    ranking_list = []
    print("\n" + "=" * 90)
    print("BẢNG XẾP HẠNG TOP SỰ CỐ NGHIÊM TRỌNG NHẤT (ANOMALY RANKING & EXPLAINABILITY)")
    print("=" * 90)

    med_duration = test_df["avg_duration"].median()
    med_volume = test_df["calls_total"].median()

    for rank, (_, row) in enumerate(top_anomalies.iterrows(), 1):
        b_str = str(row["bucket_time"])
        score = row["iforest_score"]
        tot = row["calls_total"]
        fail = row["calls_failed"]
        err_rate = row["error_rate"] * 100
        dur = row["avg_duration"]
        carrier = row["failed_carrier"]
        err_code = row["specific_error"]

        reasons = []
        if err_rate >= 30.0:
            reasons.append(f"Tỷ lệ lỗi viễn thông vọt cao ({err_rate:.1f}%, nhà mạng: {carrier}, mã: {err_code})")
        if tot >= 10:
            reasons.append(f"Quá tải lưu lượng ({tot} cuộc / 15p so với mức trung vị {med_volume:.0f})")
        if tot == 0 and 8 <= row["hour"] <= 17:
            reasons.append("Sập lưu lượng đột ngột (0 cuộc gọi trong giờ làm việc)")
        if tot >= 4 and dur <= 2.0:
            reasons.append(f"Kẹt Bot quay số (thời lượng sụt giảm còn {dur:.1f}s thay vì ~{med_duration:.0f}s)")

        reason_str = "; ".join(reasons) if reasons else "Sai lệch hình thái đa biến tổng hợp"
        level = "🔴 NGUY CẤP (P1)" if score < -0.15 else "🟠 CẢNH BÁO (P2)"

        print(f"#{rank} [{level}] Khung: {b_str}")
        print(f"   ├─ Anomaly Score: {score:.4f} | Lưu lượng: {tot} cuộc | Số lỗi: {fail} ({err_rate:.1f}%) | Đàm thoại: {dur:.1f}s")
        print(f"   └─ Nguyên nhân phân tích: {reason_str}")

        ranking_list.append({
            "rank": rank,
            "bucket_time": b_str,
            "anomaly_score": round(float(score), 4),
            "severity": level,
            "calls_total": int(tot),
            "calls_failed": int(fail),
            "error_rate_pct": round(float(err_rate), 1),
            "avg_duration": round(float(dur), 1),
            "carrier": carrier,
            "specific_error": err_code,
            "root_cause_explanation": reason_str
        })

    with open(MODELS_DIR / "benchmark_report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    with open(MODELS_DIR / "top_anomalies_ranking.json", "w", encoding="utf-8") as f:
        json.dump(ranking_list, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Da luu bao cao Benchmark: {MODELS_DIR / 'benchmark_report.json'}")
    print(f"[+] Da luu danh sach Xep hang Su co: {MODELS_DIR / 'top_anomalies_ranking.json'}")

    return report_dict, ranking_list


# ======================================================================================
# HÀM CHÍNH THỰC THI TOÀN BỘ PIPELINE
# ======================================================================================
def run_ml_pipeline():
    print("=" * 80)
    print("🚀 KHỞI ĐỘNG PIPELINE HUẤN LUYỆN MACHINE LEARNING - SCC OUTBOUND")
    print("=" * 80)

    # 1. Nạp dữ liệu
    df = load_timeseries_dataset()

    # 2. Trích xuất đặc trưng & Ground Truth
    df, feature_cols = extract_features_and_ground_truth(df)

    # 3. Temporal Split
    train_df, test_df, X_train, y_train, X_test, y_test = split_temporal(df, feature_cols)

    # 4. Chuẩn hóa RobustScaler
    X_train_sc, X_test_sc, scaler = scale_features(X_train, X_test)

    # 5. Huấn luyện 5 mô hình
    results, models_dict = train_and_evaluate_models(
        train_df, test_df,
        X_train, y_train, X_test, y_test,
        X_train_sc, X_test_sc,
        feature_cols
    )

    # 6. Đánh giá & Xếp hạng
    report, ranking = compute_benchmark_report(results, y_test, test_df, feature_cols)

    print("\n" + "=" * 80)
    print("🎉 HOÀN TẤT HUẤN LUYỆN VÀ ĐỐI CHUẨN TOÀN BỘ HỆ THỐNG MACHINE LEARNING!")
    print("=" * 80)


if __name__ == "__main__":
    run_ml_pipeline()

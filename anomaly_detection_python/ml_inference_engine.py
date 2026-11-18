# ml_inference_engine.py
"""
========================================================================================
SCC OUTBOUND - MACHINE LEARNING REALTIME INFERENCE ENGINE
========================================================================================
Lớp suy luận thời gian thực (Real-time Inference Engine) cho chuỗi thời gian 15-phút.
- Nạp nhanh mô hình Isolation Forest (.joblib) và bộ chuẩn hóa RobustScaler (.joblib).
- Chấm điểm Anomaly Score trong < 2 mili-giây.
- Phân cấp mức độ sự cố: CRITICAL (P1), WARNING (P2), NORMAL.
- Tự động trích xuất nguyên nhân chi phối (Root Cause Explanation).
========================================================================================
"""

import math
from pathlib import Path
import numpy as np
import joblib

MODELS_DIR = Path(__file__).resolve().parent / "models"


class SCCAnomalyInferenceEngine:
    """Bộ máy suy luận phát hiện bất thường thời gian thực."""

    def __init__(self, model_dir: Path = MODELS_DIR):
        self.model_dir = model_dir
        self.iforest_path = model_dir / "isolation_forest.joblib"
        self.scaler_path = model_dir / "scaler.joblib"

        self.iforest = None
        self.scaler = None
        self._load_artifacts()

    def _load_artifacts(self):
        """Nạp các mô hình nhị phân đã huấn luyện."""
        if self.iforest_path.exists():
            self.iforest = joblib.load(self.iforest_path)
        if self.scaler_path.exists():
            self.scaler = joblib.load(self.scaler_path)

    @property
    def is_ready(self) -> bool:
        return self.iforest is not None

    def predict_bucket(
        self,
        calls_total: int,
        calls_failed: int,
        avg_duration: float,
        hour: int,
        dayofweek: int,
        calls_total_lag1: int = None,
        rolling_mean_4: float = None,
        rolling_std_4: float = None,
        failed_carrier: str = "-",
        specific_error: str = "-"
    ) -> dict:
        """
        Dự đoán trạng thái của 1 khung 15 phút vừa chốt.
        Thời gian thực thi: < 2ms.
        """
        if not self.is_ready:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "severity": "NORMAL",
                "top_reason": "Model chưa được huấn luyện"
            }

        # Tính toán đặc trưng dẫn xuất
        error_rate = calls_failed / calls_total if calls_total > 0 else 0.0
        sin_hour = math.sin(2 * math.pi * hour / 24.0)
        cos_hour = math.cos(2 * math.pi * hour / 24.0)
        lag1 = calls_total if calls_total_lag1 is None else calls_total_lag1
        r_mean = calls_total if rolling_mean_4 is None else rolling_mean_4
        r_std = 0.0 if rolling_std_4 is None else rolling_std_4

        feature_vector = np.array([[
            calls_total,
            calls_failed,
            error_rate,
            avg_duration,
            hour,
            dayofweek,
            sin_hour,
            cos_hour,
            lag1,
            r_mean,
            r_std
        ]])

        # 1. Dự đoán với Isolation Forest
        raw_pred = self.iforest.predict(feature_vector)[0]  # -1: anom, 1: norm
        score = float(self.iforest.decision_function(feature_vector)[0])
        is_iforest_anom = (raw_pred == -1)

        # 2. Luật Thống Kê cứng bảo vệ (Fail-safe Hard Rules)
        is_p1_drop = (calls_total <= 15) and (8 <= hour <= 17) and (dayofweek < 5)
        is_p1_err = (calls_failed >= 20) and (error_rate >= 0.30)
        is_p2_vol = (calls_total >= 550)

        is_anomaly = is_iforest_anom or is_p1_drop or is_p1_err or is_p2_vol

        # 3. Phân cấp mức độ nghiêm trọng
        if is_p1_drop or is_p1_err or score <= -0.15:
            severity = "CRITICAL"
        elif is_p2_vol or is_iforest_anom:
            severity = "WARNING"
        else:
            severity = "NORMAL"

        # 4. Trích xuất lý do chi phối
        reasons = []
        if is_p1_drop:
            reasons.append(f"Sập lưu lượng đột ngột ({calls_total} cuộc trong giờ hành chính)")
        if error_rate >= 0.20:
            reasons.append(f"Tỷ lệ lỗi viễn thông cao ({error_rate*100:.1f}%, nhà mạng: {failed_carrier}, mã: {specific_error})")
        if calls_total >= 500:
            reasons.append(f"Đột biến lưu lượng quá tải ({calls_total} cuộc/15p)")
        if calls_total >= 50 and avg_duration <= 3.0:
            reasons.append(f"Nghi vấn kẹt Bot quay số (thời lượng chỉ đạt {avg_duration:.1f}s)")

        reason_str = "; ".join(reasons) if reasons else ("Điểm bất thường đa biến do ML phát hiện" if is_anomaly else "Vận hành ổn định")

        return {
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": round(score, 4),
            "severity": severity,
            "top_reason": reason_str,
            "error_rate_pct": round(error_rate * 100, 1),
            "calls_total": calls_total,
            "calls_failed": calls_failed,
            "carrier": failed_carrier,
            "specific_error": specific_error
        }


# Chạy test nhanh module
if __name__ == "__main__":
    engine = SCCAnomalyInferenceEngine()
    print(f"Inference Engine Ready: {engine.is_ready}")
    if engine.is_ready:
        sample = engine.predict_bucket(
            calls_total=13,
            calls_failed=3,
            avg_duration=1.2,
            hour=13,
            dayofweek=0,
            failed_carrier="VNPT",
            specific_error="500_SERVER_ERROR"
        )
        print("Kết quả kiểm thử 1 khung mẫu:", sample)

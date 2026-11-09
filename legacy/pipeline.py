from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from db import get_engine
 
OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(exist_ok=True)
 
# 1. Đọc dữ liệu
df = pd.read_sql("SELECT * FROM calls", get_engine())
print(df.dtypes)
print(df.head())
print(df.info())
 
missing = df[df.result_id.isna() | df.end_time.isna()]
print(missing)
 
# Loại các cuộc gọi chưa hoàn tất (chưa có result_id/end_time)
incomplete = df["result_id"].isna()
df.loc[incomplete, "duration"] = pd.NA
df = df.dropna(subset=["result_id", "end_time", "duration"])
df["duration"] = df["duration"].astype("int64")
df = df.reset_index(drop=True)
 
print(f"Số cuộc gọi chưa có result_id: {df['result_id'].isna().sum()}")
print(f"Số cuộc gọi chưa có end_time: {df['end_time'].isna().sum()}")
 
# 2. Thiết lập index thời gian và kiểm tra
df = df.sort_values("start_time").set_index("start_time")

print(type(df.index))
print(df.index.dtype)
print(f"Số timestamp trùng: {df.index.duplicated().sum()}")
print(f"Từ {df.index.min()} đến {df.index.max()}")
print(df.index.to_series().diff().describe())
print(f"Index tăng dần đều: {df.index.is_monotonic_increasing}")
 
diffs = df.index.to_series().diff()
gap_idx = diffs.idxmax()  # timestamp ngay sau khoảng trống lớn nhất
print(f"Khoảng trống lớn nhất: {diffs.max()}")
print(f"Kết thúc trước: {gap_idx - diffs.max()}")
print(f"Bắt đầu lại: {gap_idx}")
print(diffs.sort_values(ascending=False).head())  # top 5 khoảng trống lớn nhất
 
print(df.index.to_period("M").value_counts().sort_index())
 
# 3. Resample theo 2 granularity phù hợp với mật độ dữ liệu thực tế:
#    - hourly trên đoạn dữ liệu dày (tháng 5) -> phân tích pattern trong ngày
#    - daily trên toàn bộ range -> xu hướng tổng thể, ít khung rỗng hơn hourly-full-range
def zero_fill(ts):
    ts["call_count"] = ts["call_count"].fillna(0).astype(int)
    ts["total_duration"] = ts["total_duration"].fillna(0).astype(int)
    return ts
 
ts_hourly = df.loc["2026-05"].resample("H").agg(
    call_count=("call_id", "count"),
    avg_duration=("duration", "mean"),
    total_duration=("duration", "sum"),
)
ts_hourly = zero_fill(ts_hourly)
empty_ratio = (ts_hourly["call_count"] == 0).mean()
print(f"[Hourly - tháng 5] Tổng dòng: {len(ts_hourly)}, tỷ lệ rỗng: {empty_ratio:.1%}")
 
ts_daily = df.resample("D").agg(
    call_count=("call_id", "count"),
    avg_duration=("duration", "mean"),
    total_duration=("duration", "sum"),
)
ts_daily = zero_fill(ts_daily)
empty_ratio_d = (ts_daily["call_count"] == 0).mean()
print(f"[Daily - full range] Tổng dòng: {len(ts_daily)}, tỷ lệ rỗng: {empty_ratio_d:.1%}")
 
# 4. Xuất 2 bảng time-series hoàn chỉnh (deliverable của bài)
ts_hourly.to_csv(OUT_DIR / "outbound_calls_timeseries_hourly_may.csv")
ts_daily.to_csv(OUT_DIR / "outbound_calls_timeseries_daily_full.csv")
print(f"Đã lưu 2 file time-series vào {OUT_DIR}")
 
# 5. Trực quan hóa pattern theo giờ (hourly) và theo ngày (daily)
plt.figure(figsize=(14, 5))
 
plt.subplot(1, 2, 1)
plt.plot(ts_hourly.index, ts_hourly["call_count"], linewidth=0.8)
plt.title("Theo giờ (tháng 5/2026)")
plt.xlabel("Thời gian")
plt.ylabel("Số cuộc gọi")
plt.xticks(rotation=45)
 
plt.subplot(1, 2, 2)
plt.plot(ts_daily.index, ts_daily["call_count"], linewidth=1.2, color="orange")
plt.title("Theo ngày (toàn bộ 5-11/2026)")
plt.xlabel("Thời gian")
plt.ylabel("Số cuộc gọi")
plt.xticks(rotation=45)
 
plt.tight_layout()
plt.savefig(OUT_DIR / "calls_timeseries_overview.png", dpi=150)
plt.show()
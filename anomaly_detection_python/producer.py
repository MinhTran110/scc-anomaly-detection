# producer.py
"""
SCC Outbound: Continuous Multi-Day 15-Minute Bucket Call Event Producer
1. Phát sinh dữ liệu chuỗi thời gian liên tục theo từng KHUNG 15 PHÚT (38 khung: 08:00 -> 17:30).
2. Ghi đều đặn vào stream_buffer.csv: Mỗi lần cập nhật chỉ ghi đúng 1 hoặc 2 cuộc gọi, loại bỏ hiện tượng dồn 6 cuộc cùng một lúc.
3. Tự động chuyển ngày: Hết ngày 17:30 -> Chốt số liệu -> Gửi Báo Cáo Tổng Kết Telegram -> Chuyển sang ngày làm việc tiếp theo.
4. Kế hoạch sự cố ngẫu nhiên thực tế (Stochastic Anomaly Planner) cho từng ngày:
   - 70% cơ hội xuất hiện Đột biến lưu lượng chiến dịch (Traffic Spike P2).
   - 50% cơ hội xuất hiện Sập lưu lượng PBX (Traffic Collapse P1).
   - 60% cơ hội xuất hiện Bão lỗi nghẽn hạ tầng SIP Trunk 503 (Infrastructure Outage P1).
5. Tự động dọn dẹp bộ đệm giữ tối đa 10 ngày gần nhất để hệ thống luôn nhẹ và chạy nhanh.
"""
import sys
import os
import time
import json
import random
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from stream_engine import StreamEngine
from db_writer import DBWriter
try:
    from telegram_notifier import send_telegram_message
except ImportError:
    try:
        from anomaly_detection_python.telegram_notifier import send_telegram_message
    except ImportError:
        send_telegram_message = None

from daily_reporter import process_single_date, export_and_send_daily_report, HOURLY_PROFILE

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STREAM_FILE = DATA_DIR / "stream_buffer.csv"
SEED_FILE = DATA_DIR / "seed_historical_stream.csv"
SIGNAL_FILE = DATA_DIR / "reset_signal.flag"

stream_engine = StreamEngine()
db_writer = DBWriter()
RESULT_TYPES = ["ANSWERED", "NO_ANSWER", "BUSY", "CALLBACK_REQUESTED", "VOICEMAIL"]

def get_next_business_day(cur_date):
    """Tính ngày làm việc tiếp theo (Bỏ qua Thứ Bảy và Chủ Nhật)."""
    next_d = cur_date + timedelta(days=1)
    while next_d.weekday() >= 5: # 5: Thứ 7, 6: Chủ Nhật
        next_d += timedelta(days=1)
    return next_d

def generate_day_anomaly_plan(sim_date):
    """
    Tạo kế hoạch sự cố ngẫu nhiên thực tế cho 1 ngày làm việc:
    - Đảm bảo mỗi ngày đều có cả 3 loại sự cố tiêu biểu:
      + Đột biến lưu lượng chiến dịch (P2 Spike, 🟡)
      + Sập tín hiệu cuộc gọi PBX (P1 Collapse, 🔴 chấm tròn đỏ)
      + Bão lỗi nghẽn hạ tầng SIP Trunk 503 (P1 Outage, 🚨)
    """
    plan = {
        "spike_buckets": set(),
        "collapse_buckets": set(),
        "outage_buckets": set(),
        "spike_volume": random.randint(10, 13),
        "outage_volume": random.randint(4, 6),
        "outage_err_rate": round(random.uniform(0.65, 0.85), 2),
    }

    # 1. P2 Traffic Spike: Xuất hiện trong các khung giờ cao điểm sáng hoặc chiều [9h, 10h, 14h, 15h]
    h_spike = random.choice([9, 10, 14, 15])
    m_spike = random.choice([0, 15, 30, 45])
    t_spike = sim_date.replace(hour=h_spike, minute=m_spike, second=0)
    plan["spike_buckets"].add(t_spike)
    if random.random() < 0.40: # 40% khả năng kéo dài 2 khung
        plan["spike_buckets"].add(t_spike + timedelta(minutes=15))

    # 2. P1 Traffic Collapse: Luôn có sự cố sập lưu lượng (về 0 cuộc) tại khung giờ làm việc cao điểm [10h, 11h, 15h, 16h]
    h_col = random.choice([10, 11, 15, 16])
    m_col = random.choice([0, 15, 30, 45])
    t_col = sim_date.replace(hour=h_col, minute=m_col, second=0)
    while t_col in plan["spike_buckets"]:
        h_col = random.choice([10, 11, 15, 16])
        m_col = (m_col + 15) % 60
        t_col = sim_date.replace(hour=h_col, minute=m_col, second=0)
    plan["collapse_buckets"].add(t_col)

    # 3. P1 SIP Trunk 503 Outage: Luôn có sự cố nghẽn mạng viễn thông trong các khung [13h, 14h]
    h_out = random.choice([13, 14])
    m_out = random.choice([0, 15, 30, 45])
    t_out = sim_date.replace(hour=h_out, minute=m_out, second=0)
    while t_out in plan["spike_buckets"] or t_out in plan["collapse_buckets"]:
        m_out = (m_out + 15) % 60
        t_out = sim_date.replace(hour=h_out, minute=m_out, second=0)
    plan["outage_buckets"].add(t_out)
    if random.random() < 0.40:
        next_out = t_out + timedelta(minutes=15)
        if next_out not in plan["spike_buckets"] and next_out not in plan["collapse_buckets"]:
            plan["outage_buckets"].add(next_out)

    return plan

def run_continuous_producer(bucket_delay_seconds: float = 3.5):
    """
    Producer chạy liên tục đa ngày qua vòng lặp vô hạn.
    Mỗi lần ghi vào buffer chỉ ghi đúng 1 hoặc 2 cuộc gọi đều đặn.
    Hết 17:30 tự động gửi báo cáo Telegram và nhảy sang ngày tiếp theo.
    """
    print("=" * 80)
    print("🚀 SCC OUTBOUND: PRODUCER CHUỖI THỜI GIAN ĐA NGÀY LIÊN TỤC KHỞI ĐỘNG")
    print(f"⏱ Tốc độ: 1 khung 15 phút / ~{bucket_delay_seconds}s (38 khung: 08:00 -> 17:30)")
    print(f"📁 Tệp buffer: {STREAM_FILE}")
    print("🌊 Chế độ ghi buffer: Đều đặn 1 - 2 cuộc gọi / lần cập nhật")
    print("=" * 80)

    # Đảm bảo file buffer tồn tại từ seed nếu chưa có
    if not STREAM_FILE.exists() or STREAM_FILE.stat().st_size < 100:
        if SEED_FILE.exists():
            import shutil
            shutil.copyfile(SEED_FILE, STREAM_FILE)
            print("🌱 Đã nạp dữ liệu nền tảng ban đầu từ seed_historical_stream.csv")

    # Nạp dữ liệu lịch sử ban đầu vào PostgreSQL nếu có
    try:
        if STREAM_FILE.exists():
            init_df = pd.read_csv(STREAM_FILE)
            if not init_df.empty:
                n_synced = db_writer.save_calls_batch(init_df.to_dict("records"))
                db_writer.sync_timeseries_aggregation()
                if n_synced > 0:
                    print(f"🐘 [PostgreSQL Init] Đã đồng bộ {n_synced:,} cuộc gọi ban đầu vào Database.")
    except Exception as e:
        print(f"⚠️ [PostgreSQL Init] Lỗi nạp dữ liệu khởi động: {e}")

    while True:
        # Kiểm tra cờ reset từ Dashboard
        if SIGNAL_FILE.exists():
            SIGNAL_FILE.unlink(missing_ok=True)
            print("🔄 Nhận tín hiệu Reset từ Dashboard! Khởi động lại luồng...")
            if SEED_FILE.exists():
                import shutil
                shutil.copyfile(SEED_FILE, STREAM_FILE)
            time.sleep(1)
            continue

        # Đọc dữ liệu hiện có để xác định ngày và khung cần chạy
        call_id = 100000
        sim_date = None
        start_bucket_idx = 0
        past_records = []
        today_records = []

        try:
            df_buf = pd.read_csv(STREAM_FILE)
            if not df_buf.empty:
                df_buf["start_time"] = pd.to_datetime(df_buf["start_time"])
                df_buf["date"] = df_buf["start_time"].dt.date
                call_id = int(df_buf["call_id"].max()) + 1

                all_dates = sorted(df_buf["date"].unique())
                last_date = all_dates[-1]
                df_last = df_buf[df_buf["date"] == last_date]
                last_buckets = df_last["start_time"].dt.floor("15min").unique()

                # Nếu ngày cuối đã hoàn thành trọn vẹn 38 khung
                if len(last_buckets) >= 38 or any(b.hour == 17 and b.minute >= 15 for b in pd.to_datetime(last_buckets)):
                    # Chuyển sang ngày làm việc tiếp theo
                    next_day = get_next_business_day(last_date)
                    sim_date = datetime(next_day.year, next_day.month, next_day.day, 8, 0, 0)
                    start_bucket_idx = 0
                    past_records = df_buf.drop(columns=["date"]).to_dict("records")
                else:
                    # Tiếp tục ngày đang dở
                    sim_date = datetime(last_date.year, last_date.month, last_date.day, 8, 0, 0)
                    start_bucket_idx = max(0, len(last_buckets) - 1)
                    past_records = df_buf[df_buf["date"] < last_date].drop(columns=["date"]).to_dict("records")
                    today_records = df_last.drop(columns=["date"]).to_dict("records")
        except Exception as e:
            print(f"⚠️ Lỗi đọc buffer ({e}), khởi tạo lại ngày mặc định 2026-10-08...")
            sim_date = datetime(2026, 10, 8, 8, 0, 0)
            start_bucket_idx = 0

        if sim_date is None:
            sim_date = datetime(2026, 10, 8, 8, 0, 0)

        # Lập kế hoạch sự cố ngẫu nhiên cho ngày này
        anomaly_plan = generate_day_anomaly_plan(sim_date)
        bucket_times = pd.date_range(sim_date, sim_date.replace(hour=17, minute=30), freq="15min")
        total_buckets = len(bucket_times) - 1 # Đúng 38 khung

        print("\n" + "=" * 75)
        print(f"📅 BẮT ĐẦU VẬN HÀNH NGÀY: {sim_date.strftime('%A, %d/%m/%Y')}")
        print(f"📊 Kế hoạch sự cố ngẫu nhiên:")
        print(f"   • Spike (P2): {[b.strftime('%H:%M') for b in sorted(anomaly_plan['spike_buckets'])] or 'Không có'}")
        print(f"   • Collapse (P1): {[b.strftime('%H:%M') for b in sorted(anomaly_plan['collapse_buckets'])] or 'Không có'}")
        print(f"   • Outage 503 (P1): {[b.strftime('%H:%M') for b in sorted(anomaly_plan['outage_buckets'])] or 'Không có'}")
        print("=" * 75)

        if start_bucket_idx == 0 and send_telegram_message:
            send_telegram_message(
                f"🚀 <b>[SCC OUTBOUND] BẮT ĐẦU MÔ PHỎNG NGÀY {sim_date.strftime('%d/%m/%Y (%A)')}</b>\n\n"
                "⏱ Luồng dữ liệu vận hành tuần tự theo từng khung 15 phút (08:00 - 17:30)...\n"
                "📡 Kết nối: Redis Stream & Real-time Anomaly Detection Engine."
            )

        day_notified = set()

        for idx in range(start_bucket_idx, total_buckets):
            # Kiểm tra tín hiệu reset đột xuất
            if SIGNAL_FILE.exists():
                print("🔄 Nhận tín hiệu Reset từ Dashboard giữa ngày!")
                break

            b_start = bucket_times[idx]
            b_end = bucket_times[idx + 1]
            cur_h = b_start.hour
            base_mu = HOURLY_PROFILE.get(str(cur_h), {}).get("mu", 4.0)

            # Phân loại trạng thái của khung hiện tại theo kế hoạch sự cố
            is_spike = b_start in anomaly_plan["spike_buckets"]
            is_collapse = b_start in anomaly_plan["collapse_buckets"]
            is_outage = b_start in anomaly_plan["outage_buckets"]

            if is_spike:
                n_calls = anomaly_plan["spike_volume"]
                err_ratio = 0.02
                tag = "🟡 [ĐỘT BIẾN TẢI P2]"
            elif is_collapse:
                n_calls = 0
                err_ratio = 0.0
                tag = "🔴 [SẬP LƯU LƯỢNG P1]"
            elif is_outage:
                n_calls = anomaly_plan["outage_volume"]
                err_ratio = anomaly_plan["outage_err_rate"]
                tag = "🚨 [NGHẼN 503 P1]"
            else:
                # Bình thường: dao động tự nhiên quanh mức kỳ vọng base_mu (3 - 6 cuộc trong giờ cao điểm)
                n_calls = max(2, int(round(np.random.normal(base_mu, 1.0))))
                err_ratio = float(np.clip(np.random.normal(0.02, 0.005), 0.0, 0.04))
                tag = "🟢 [BÌNH THƯỜNG]"

            # Sinh các cuộc gọi thuộc khung 15 phút này (thời gian phân bố đều)
            bucket_calls = []
            if n_calls > 0:
                offsets = sorted([random.randint(5, 885) for _ in range(n_calls)])
                for off in offsets:
                    c_start = b_start + timedelta(seconds=off)
                    if random.random() < err_ratio:
                        res = "503_CONGESTION"
                        dur = random.randint(1, 3)
                    else:
                        res = random.choices(RESULT_TYPES, weights=[0.55, 0.25, 0.10, 0.07, 0.03])[0]
                        dur = random.randint(30, 210) if res == "ANSWERED" else random.randint(5, 20)

                    rec = {
                        "call_id": call_id,
                        "start_time": c_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": (c_start + timedelta(seconds=dur)).strftime("%Y-%m-%d %H:%M:%S"),
                        "duration": dur,
                        "result_code": res
                    }
                    call_id += 1
                    bucket_calls.append(rec)

            # Chia nhỏ danh sách cuộc gọi thành các đợt ghi ĐỀU ĐẶN ĐÚNG 1 HOẶC 2 CUỘC GỌI
            chunks = []
            i = 0
            while i < len(bucket_calls):
                chunk_sz = min(random.choice([4, 7]), len(bucket_calls) - i)
                chunks.append(bucket_calls[i : i + chunk_sz])
                i += chunk_sz

            n_chunks = max(len(chunks), 1)
            sub_delay = bucket_delay_seconds / n_chunks

            if chunks:
                for chunk in chunks:
                    for rec in chunk:
                        stream_engine.publish_call(rec)
                    # Ghi nhận trực tiếp vào bảng calls_stream trong PostgreSQL
                    db_writer.save_calls_batch(chunk)
                    today_records.extend(chunk)

                    # Ghi đều đặn 1 hoặc 2 cuộc gọi ra file buffer
                    all_records = past_records + today_records
                    tmp_file = DATA_DIR / "stream_buffer.tmp"
                    pd.DataFrame(all_records).to_csv(tmp_file, index=False)
                    tmp_file.replace(STREAM_FILE)

                    time.sleep(sub_delay)
            else:
                time.sleep(bucket_delay_seconds)

            # Bản ghi lead tại b_end để Dashboard chốt khung 15 phút
            dummy_lead = {
                "call_id": call_id,
                "start_time": b_end.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": (b_end + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": 5,
                "result_code": "ANSWERED"
            }
            all_records = past_records + today_records + [dummy_lead]
            tmp_file = DATA_DIR / "stream_buffer.tmp"
            pd.DataFrame(all_records).to_csv(tmp_file, index=False)
            tmp_file.replace(STREAM_FILE)

            # Đồng bộ tổng hợp 15 phút vào bảng call_timeseries của PostgreSQL
            db_writer.sync_timeseries_aggregation()

            # Gửi cảnh báo Telegram nếu có sự cố phát sinh
            bucket_key = b_start.strftime("%Y-%m-%d %H:%M")
            if send_telegram_message and bucket_key not in day_notified:
                if is_spike:
                    day_notified.add(bucket_key)
                    send_telegram_message(
                        f"🟡🟡🟡 <b>[SCC OUTBOUND - P2 WARNING: TRAFFIC SPIKE]</b> 🟡🟡🟡\n\n"
                        f"⏰ <b>Khung phát hiện:</b> <code>{b_start.strftime('%H:%M')} ({sim_date.strftime('%d/%m/%Y')})</code>\n"
                        f"📈 <b>Lưu lượng tăng vọt:</b> <b>{n_calls} cuộc</b> (Kỳ vọng: {base_mu:.1f})\n"
                        f"ℹ️ <b>ĐÁNH GIÁ:</b> Đột biến tải chiến dịch hoặc auto-dialer đẩy tốc độ gọi.\n"
                        f"• Khuyến nghị đội NOC theo dõi dung lượng đồng thời để tránh nghẽn kênh."
                    )
                elif is_collapse:
                    day_notified.add(bucket_key)
                    send_telegram_message(
                        f"🔴🔴🔴 <b>[SCC OUTBOUND - P1 RED ALERT: SẬP LƯU LƯỢNG PBX]</b> 🔴🔴🔴\n\n"
                        f"⏰ <b>Khung phát hiện:</b> <code>{b_start.strftime('%H:%M')} ({sim_date.strftime('%d/%m/%Y')})</code>\n"
                        f"📉 <b>Lưu lượng:</b> <b>0 cuộc</b> (Kỳ vọng: {base_mu:.1f})\n"
                        f"⚠️ <b>CẢNH BÁO:</b> Tổng đài PBX mất tín hiệu hoặc đứt kết nối trung kế!\n"
                        f"• Kích hoạt kiểm tra Gateway viễn thông và trung kế SCC Outbound ngay lập tức."
                    )
                elif is_outage:
                    day_notified.add(bucket_key)
                    n_503 = sum(1 for c in bucket_calls if c["result_code"] == "503_CONGESTION")
                    pct_503 = (n_503 / n_calls * 100) if n_calls > 0 else 0
                    send_telegram_message(
                        f"🚨🚨🚨 <b>[SCC OUTBOUND - P1 RED ALERT: NGHẼN MẠNG SIP TRUNK 503]</b> 🚨🚨🚨\n\n"
                        f"⏰ <b>Khung phát hiện:</b> <code>{b_start.strftime('%H:%M')} ({sim_date.strftime('%d/%m/%Y')})</code>\n"
                        f"❌ <b>Số cuộc lỗi 503:</b> <b>{n_503}/{n_calls} cuộc ({pct_503:.1f}%)</b>\n"
                        f"⚠️ <b>YÊU CẦU:</b> Kiểm tra Gateway viễn thông và hạ tầng SIP Trunk ngay lập tức!\n"
                        f"• Điều chuyển hướng sang trung kế dự phòng nếu cuộc gọi không thể thiết lập."
                    )

            print(f"[{b_start.strftime('%H:%M')} -> {b_end.strftime('%H:%M')}] Chốt khung {idx+1:2d}/38: {n_calls:2d} cuộc (chia {len(chunks)} đợt 1-2 cuộc) | {tag}")

        # Kiểm tra nếu vòng lặp kết thúc bình thường (đạt đủ 38 khung lúc 17:30)
        if not SIGNAL_FILE.exists():
            print("\n" + "=" * 75)
            print(f"🏁 [17:30 HẾT NGÀY LÀM VIỆC {sim_date.strftime('%d/%m/%Y')}] ĐÃ HOÀN TẤT 38 KHUNG GIỜ.")
            print("📊 Đang tổng hợp số liệu và gửi Báo Cáo Tổng Kết Ngày kèm ảnh qua Telegram...")
            
            # Tính toán time series và xuất báo cáo ảnh Telegram
            try:
                df_today = pd.DataFrame(today_records)
                if not df_today.empty:
                    df_today["start_time"] = pd.to_datetime(df_today["start_time"])
                    df_today["bucket_time"] = df_today["start_time"].dt.floor("15min")
                    day_ts = process_single_date(df_today, sim_date.date(), is_live_today=False)
                    ok, desc, r_file = export_and_send_daily_report(sim_date.date(), day_ts, force=True)
                    print(f"📤 Kết quả gửi báo cáo tổng kết ngày: {desc} ({r_file.name})")
            except Exception as e:
                print(f"⚠️ Lỗi khi xuất báo cáo tổng kết ngày: {e}")

            # Đồng bộ toàn diện vào PostgreSQL khi hoàn tất ngày
            try:
                db_writer.sync_timeseries_aggregation()
            except Exception as e:
                print(f"⚠️ [PostgreSQL Sync] {e}")

            # Đã vô hiệu hóa cơ chế cắt gọt 10 ngày để toàn bộ dữ liệu lịch sử
            # được tích lũy liên tục qua các ngày (ngày 11, 12, 13...) phục vụ Superset & Analytics.
            tot_accumulated = len(today_records) + len(past_records)
            print(f"📊 [Dữ liệu tích lũy] Toàn bộ lịch sử được bảo toàn: {tot_accumulated:,} cuộc gọi (Không cắt ngày cũ).")

            print("⏱ Tạm dừng 4s để Dashboard hoàn tất hiển thị, sau đó tự động chuyển sang ngày tiếp theo...")
            print("=" * 75 + "\n")
            time.sleep(4.0)

if __name__ == "__main__":
    run_continuous_producer()

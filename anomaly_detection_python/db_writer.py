# db_writer.py
"""
SCC Outbound: Database Writer & Ingestion Module for PostgreSQL
Chức năng:
1. Kết nối an toàn tới PostgreSQL (Fault-tolerant, auto-reconnect, non-blocking).
2. Hỗ trợ ghi song song đa Database (Dual Write: DB1 container nội bộ & DB2 máy chủ ngoài).
3. Tự động đọc cấu hình từ .env hoặc biến môi trường (DB1_*, DB2_*).
4. Tự động khởi tạo bảng calls_stream và call_timeseries nếu chưa tồn tại.
5. Ghi nhận hàng loạt (Batch INSERT) cuộc gọi vào public.calls_stream (ON CONFLICT DO NOTHING).
6. Đồng bộ tổng hợp chuỗi thời gian 15-phút (15-min bucket aggregation) vào public.call_timeseries.
"""
import os
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def _load_env_file():
    """Tự động tìm và đọc file .env nếu biến môi trường chưa được nạp."""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
        Path("/app/.env"),
        Path.cwd() / ".env"
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ or not os.environ[k]:
                                os.environ[k] = v
                break
            except Exception:
                pass

class DBWriter:
    def __init__(self):
        _load_env_file()

        # Cấu hình Mục tiêu 1 (DB1 - scc_postgres nội bộ container)
        db1_host = os.environ.get("DB1_HOST") or os.environ.get("DB_HOST", "db")
        db1_port_raw = os.environ.get("DB1_PORT") or os.environ.get("DB_PORT", "5432")
        db1_port = int(db1_port_raw)
        if db1_host == "db" and db1_port == 5433:
            db1_port = 5432

        db1_name = os.environ.get("DB1_NAME") or os.environ.get("DB_NAME", "scc_calls")
        db1_user = os.environ.get("DB1_USER") or os.environ.get("DB_USER", "postgres")
        db1_pass = os.environ.get("DB1_PASSWORD") or os.environ.get("DB_PASSWORD", "postgrespassword")

        self.targets: List[Dict[str, Any]] = [
            {
                "id": "DB1 [Container scc_calls]",
                "host": db1_host,
                "port": db1_port,
                "dbname": db1_name,
                "user": db1_user,
                "password": db1_pass,
                "conn": None,
                "initialized": False
            }
        ]

        # Cấu hình Mục tiêu 2 (DB2 - Máy chủ ngoài, ví dụ MinhTQ70 trên port 5432)
        db2_host = os.environ.get("DB2_HOST")
        if db2_host:
            db2_port = int(os.environ.get("DB2_PORT", 5432))
            db2_name = os.environ.get("DB2_NAME", "postgres")
            db2_user = os.environ.get("DB2_USER", "postgres")
            db2_pass = os.environ.get("DB2_PASSWORD", "")
            self.targets.append({
                "id": "DB2 [MinhTQ70 / postgres:5432]",
                "host": db2_host,
                "port": db2_port,
                "dbname": db2_name,
                "user": db2_user,
                "password": db2_pass,
                "conn": None,
                "initialized": False
            })

        logging.info(f"🔌 [DBWriter] Đã kích hoạt cơ chế ghi song song {len(self.targets)} Database mục tiêu.")

    def get_connection(self) -> Optional[Any]:
        """Tương thích ngược: Trả về kết nối chính (DB1)."""
        return self._get_target_connection(self.targets[0])

    def _get_target_connection(self, target: Dict[str, Any]) -> Optional[Any]:
        """Khởi tạo hoặc tái sử dụng kết nối tới 1 mục tiêu cụ thể với cơ chế tự phục hồi."""
        conn = target.get("conn")
        try:
            if conn is None or conn.closed != 0:
                conn = psycopg2.connect(
                    host=target["host"],
                    port=target["port"],
                    dbname=target["dbname"],
                    user=target["user"],
                    password=target["password"],
                    connect_timeout=3
                )
                conn.autocommit = True
                target["conn"] = conn
                if not target.get("initialized"):
                    self._ensure_tables(target)
                    target["initialized"] = True
            return conn
        except Exception as e:
            logging.warning(f"⚠️ [DBWriter] Chưa thể kết nối {target['id']} ({target['host']}:{target['port']}/{target['dbname']}): {e}")
            target["conn"] = None
            return None

    def _ensure_tables(self, target: Dict[str, Any]):
        """Đảm bảo các bảng cần thiết tồn tại trong Database mục tiêu."""
        conn = target.get("conn")
        if conn is None or conn.closed != 0:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS public.calls_stream (
                    call_id     bigint NOT NULL PRIMARY KEY,
                    start_time  timestamp without time zone,
                    end_time    timestamp without time zone,
                    duration    integer,
                    result_code character varying(50)
                );

                CREATE TABLE IF NOT EXISTS public.call_timeseries (
                    bucket_time     timestamp without time zone NOT NULL PRIMARY KEY,
                    calls_total     integer NOT NULL DEFAULT 0,
                    calls_connected integer NOT NULL DEFAULT 0,
                    avg_duration    numeric,
                    n_employees     integer NOT NULL DEFAULT 0,
                    is_imputed      boolean NOT NULL DEFAULT false,
                    created_at      timestamp without time zone NOT NULL DEFAULT now()
                );
                """)
            logging.info(f"✅ [DBWriter] Đã đảm bảo schema bảng sẵn sàng trên {target['id']}.")
        except Exception as e:
            logging.error(f"❌ [DBWriter] Lỗi khi tạo bảng trên {target['id']}: {e}")

    def save_calls_batch(self, records: List[Dict[str, Any]]) -> int:
        """Ghi nhận batch danh sách cuộc gọi song song vào tất cả các Database mục tiêu."""
        if not records:
            return 0

        query = """
        INSERT INTO public.calls_stream (call_id, start_time, end_time, duration, result_code)
        VALUES %s
        ON CONFLICT (call_id) DO NOTHING;
        """
        data_tuples = [
            (
                int(r["call_id"]),
                str(r["start_time"]),
                str(r["end_time"]),
                int(r.get("duration", 0)),
                str(r.get("result_code", "UNKNOWN"))
            )
            for r in records
        ]

        success_count = 0
        for target in self.targets:
            conn = self._get_target_connection(target)
            if not conn:
                continue
            try:
                with conn.cursor() as cur:
                    execute_values(cur, query, data_tuples)
                success_count = len(data_tuples)
            except Exception as e:
                logging.error(f"❌ [DBWriter] Lỗi ghi batch cuộc gọi vào {target['id']}: {e}")
                try:
                    if target.get("conn") and not target["conn"].closed:
                        target["conn"].rollback()
                except Exception:
                    pass

        return success_count

    def sync_timeseries_aggregation(self) -> bool:
        """Đồng bộ và tính toán time-series 15 phút từ calls_stream sang call_timeseries trên tất cả mục tiêu."""
        agg_query = """
        INSERT INTO public.call_timeseries (
            bucket_time,
            calls_total,
            calls_connected,
            avg_duration,
            n_employees,
            is_imputed,
            created_at
        )
        WITH max_call AS (
            -- Chỉ quét đến mốc thời gian cuộc gọi mới nhất đã phát sinh (không sinh trước tương lai)
            SELECT MAX(start_time) AS max_time FROM public.calls_stream
        ),
        distinct_days AS (
            SELECT DISTINCT date_trunc('day', start_time) AS work_day
            FROM public.calls_stream
            WHERE start_time IS NOT NULL
        ),
        buckets AS (
            SELECT 
                d.work_day + (s * interval '15 min') AS bucket_time
            FROM distinct_days d
            CROSS JOIN generate_series(32, 69) AS s
            CROSS JOIN max_call mc
            -- Chỉ tạo khung giờ đến thời điểm hiện tại của luồng cuộc gọi
            WHERE mc.max_time IS NOT NULL 
              AND (d.work_day + (s * interval '15 min')) <= mc.max_time
        ),
        call_agg AS (
            SELECT
                date_trunc('hour', start_time) 
                + floor(extract(minute FROM start_time) / 15) * interval '15 min' AS bucket_time,
                COUNT(call_id) AS calls_total,
                COUNT(call_id) FILTER (
                    WHERE result_code IN ('ANSWERED', 'CALLBACK_REQUESTED', 'NOT_INTERESTED')
                ) AS calls_connected,
                ROUND(AVG(duration), 2) AS avg_duration,
                0 AS n_employees
            FROM public.calls_stream
            WHERE start_time IS NOT NULL AND end_time IS NOT NULL
            GROUP BY 1
        )
        SELECT
            b.bucket_time,
            COALESCE(ca.calls_total, 0)     AS calls_total,
            COALESCE(ca.calls_connected, 0) AS calls_connected,
            ca.avg_duration                 AS avg_duration,
            0                               AS n_employees,
            (ca.calls_total IS NULL)        AS is_imputed,
            now()                           AS created_at
        FROM buckets b
        LEFT JOIN call_agg ca ON b.bucket_time = ca.bucket_time
        ON CONFLICT (bucket_time) DO UPDATE SET
            calls_total     = EXCLUDED.calls_total,
            calls_connected = EXCLUDED.calls_connected,
            avg_duration    = EXCLUDED.avg_duration,
            n_employees     = EXCLUDED.n_employees,
            is_imputed      = EXCLUDED.is_imputed;
        """

        overall_ok = False
        for target in self.targets:
            conn = self._get_target_connection(target)
            if not conn:
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(agg_query)
                logging.info(f"📊 [DBWriter] Đã đồng bộ và tính toán xong chuỗi thời gian vào {target['id']}.")
                overall_ok = True
            except Exception as e:
                logging.error(f"❌ [DBWriter] Lỗi đồng bộ call_timeseries trên {target['id']}: {e}")

        return overall_ok

if __name__ == "__main__":
    import sys
    print("🔄 Đang thực hiện Backfill & Đồng bộ chuỗi thời gian cho toàn bộ Database...")
    writer = DBWriter()
    ok = writer.sync_timeseries_aggregation()
    if ok:
        print("✅ Backfill hoàn tất thành công! Mọi khung giờ thiếu trong quá khứ đã được bù đủ.")
    else:
        print("❌ Có lỗi xảy ra trong quá trình đồng bộ.")
        sys.exit(1)


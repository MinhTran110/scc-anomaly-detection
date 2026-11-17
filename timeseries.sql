-- ==============================================================================
-- SCC OUTBOUND TIME-SERIES AGGREGATION & OPERATIONAL ANALYTICS
-- Phiên bản: 3.2 (Bổ sung Định vị lỗi Nhà mạng & Đồng bộ Đa CSDL)
-- ==============================================================================

-- 1. TẠO BẢNG public.call_timeseries & BẢNG ĐỆM calls_stream NẾU CHƯA CÓ
CREATE TABLE IF NOT EXISTS public.call_timeseries
(
    bucket_time     timestamp without time zone NOT NULL,
    calls_total     integer NOT NULL DEFAULT 0,
    calls_connected integer NOT NULL DEFAULT 0,
    calls_failed    integer NOT NULL DEFAULT 0,
    failed_carrier  character varying(50),
    specific_error  character varying(50),
    avg_duration    numeric,
    n_employees     integer NOT NULL DEFAULT 0,
    is_imputed      boolean NOT NULL DEFAULT false,
    created_at      timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT call_timeseries_pkey PRIMARY KEY (bucket_time)
);

CREATE TABLE IF NOT EXISTS public.calls_stream (
    call_id     bigint NOT NULL PRIMARY KEY,
    start_time  timestamp without time zone,
    end_time    timestamp without time zone,
    duration    integer,
    result_code character varying(50),
    carrier     character varying(50) DEFAULT 'VIETTEL'
);

-- Đảm bảo các cột mới luôn tồn tại kể cả trên bảng cũ
ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS calls_failed integer NOT NULL DEFAULT 0;
ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS failed_carrier character varying(50);
ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS specific_error character varying(50);
ALTER TABLE public.calls_stream ADD COLUMN IF NOT EXISTS carrier character varying(50) DEFAULT 'VIETTEL';


-- 2. BUCKET HÓA 15 PHÚT + ZERO-FILL (HỖ TRỢ INCREMENTAL UPSERT - NẠP VI SAI)
-- Đảm bảo tương thích: Nếu có bảng calls_stream thì tổng hợp từ calls_stream
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'calls_stream') THEN
        INSERT INTO public.call_timeseries (
            bucket_time,
            calls_total,
            calls_connected,
            calls_failed,
            failed_carrier,
            specific_error,
            avg_duration,
            n_employees,
            is_imputed,
            created_at
        )
        WITH time_bounds AS (
            SELECT
                COALESCE(date_trunc('day', MIN(start_time)), CURRENT_DATE) AS min_day,
                COALESCE(MAX(start_time), CURRENT_TIMESTAMP) AS max_time
            FROM public.calls_stream
            WHERE start_time IS NOT NULL
        ),
        work_days AS (
            SELECT generate_series(
                min_day,
                date_trunc('day', max_time),
                interval '1 day'
            )::date AS work_day
            FROM time_bounds
            WHERE extract(isodow FROM generate_series(
                min_day,
                date_trunc('day', max_time),
                interval '1 day'
            )) BETWEEN 1 AND 5
        ),
        buckets AS (
            SELECT (d.work_day + (s * interval '15 min'))::timestamp AS bucket_time
            FROM work_days d
            CROSS JOIN generate_series(32, 69) s
            CROSS JOIN time_bounds mc
            WHERE (d.work_day + (s * interval '15 min')) <= mc.max_time
        ),
        call_agg AS (
            SELECT
                date_trunc('hour', start_time) 
                + floor(extract(minute FROM start_time) / 15) * interval '15 min' AS bucket_time,
                COUNT(call_id) AS calls_total,
                COUNT(call_id) FILTER (
                    WHERE result_code IN ('ANSWERED', 'CALLBACK_REQUESTED', 'NOT_INTERESTED')
                ) AS calls_connected,
                COUNT(call_id) FILTER (
                    WHERE result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT')
                ) AS calls_failed,
                (ARRAY_AGG(carrier ORDER BY (result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT')) DESC) 
                 FILTER (WHERE result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT')))[1] AS failed_carrier,
                (ARRAY_AGG(result_code ORDER BY (result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT')) DESC) 
                 FILTER (WHERE result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT')))[1] AS specific_error,
                ROUND(AVG(duration), 2) AS avg_duration,
                0 AS n_employees
            FROM public.calls_stream
            WHERE start_time IS NOT NULL AND end_time IS NOT NULL
            GROUP BY 1
        )
        SELECT
            b.bucket_time,
            COALESCE(ca.calls_total, 0)      AS calls_total,
            COALESCE(ca.calls_connected, 0)  AS calls_connected,
            COALESCE(ca.calls_failed, 0)     AS calls_failed,
            COALESCE(ca.failed_carrier, '-') AS failed_carrier,
            COALESCE(ca.specific_error, '-') AS specific_error,
            COALESCE(ca.avg_duration, 0.0)   AS avg_duration,
            0                                AS n_employees,
            (ca.calls_total IS NULL)         AS is_imputed,
            now()                            AS created_at
        FROM buckets b
        LEFT JOIN call_agg ca ON b.bucket_time = ca.bucket_time
        ON CONFLICT (bucket_time) DO UPDATE SET
            calls_total     = EXCLUDED.calls_total,
            calls_connected = EXCLUDED.calls_connected,
            calls_failed    = EXCLUDED.calls_failed,
            failed_carrier  = EXCLUDED.failed_carrier,
            specific_error  = EXCLUDED.specific_error,
            avg_duration    = EXCLUDED.avg_duration,
            n_employees     = EXCLUDED.n_employees,
            is_imputed      = EXCLUDED.is_imputed;
    END IF;
END $$;


-- ==============================================================================
-- 3. TRUY VẤN DẪN XUẤT (ANALYTICAL & OPERATIONAL QUERIES) — PHIÊN BẢN HIỆN HÀNH
-- ==============================================================================

-- 3.1. Theo GIỜ (Phân tích chu kỳ 24h & Sự cố viễn thông theo giờ)
--      Dùng để phân tích pattern lưu lượng, tỷ lệ kết nối và định vị nhà mạng gặp lỗi theo giờ
SELECT
    date_trunc('hour', bucket_time) AS hour_bucket,
    SUM(calls_total) AS tong_cuoc_goi,
    SUM(calls_connected) AS cuoc_ket_noi,
    SUM(calls_failed) AS cuoc_loi_he_thong,
    ROUND(100.0 * SUM(calls_failed) / NULLIF(SUM(calls_total), 0), 2) AS ty_le_loi_pct,
    (ARRAY_AGG(failed_carrier ORDER BY calls_failed DESC) FILTER (WHERE failed_carrier IS NOT NULL))[1] AS nha_mang_loi_chinh,
    (ARRAY_AGG(specific_error ORDER BY calls_failed DESC) FILTER (WHERE specific_error IS NOT NULL))[1] AS ma_loi_chinh,
    ROUND(SUM(avg_duration * calls_total) / NULLIF(SUM(calls_total), 0), 2) AS thoi_luong_tb_giay
FROM public.call_timeseries
-- Phân tích giai đoạn dữ liệu dày của hệ thống hiện tại (Tháng 10 - Tháng 11/2026)
WHERE bucket_time >= '2026-10-01' AND bucket_time < '2026-12-01' AND calls_total > 0
GROUP BY 1
ORDER BY 1;


-- 3.2. Theo NGÀY (Báo cáo tổng hợp vận hành từng ngày trong toàn bộ lịch sử)
--      Dùng để theo dõi xu hướng SLA vận hành, tỷ lệ nghe máy và giám sát sự cố gián đoạn viễn thông
SELECT
    date_trunc('day', bucket_time)::date AS ngay,
    SUM(calls_total) AS tong_cuoc_goi,
    SUM(calls_connected) AS cuoc_nghe_may,
    ROUND(100.0 * SUM(calls_connected) / NULLIF(SUM(calls_total), 0), 1) AS ty_le_ket_noi_pct,
    SUM(calls_failed) AS cuoc_gian_doan,
    ROUND(100.0 * SUM(calls_failed) / NULLIF(SUM(calls_total), 0), 2) AS ty_le_loi_pct,
    (ARRAY_AGG(failed_carrier ORDER BY calls_failed DESC) FILTER (WHERE failed_carrier IS NOT NULL))[1] AS nha_mang_loi_chinh,
    (ARRAY_AGG(specific_error ORDER BY calls_failed DESC) FILTER (WHERE specific_error IS NOT NULL))[1] AS ma_loi_chinh,
    ROUND(SUM(avg_duration * calls_total) / NULLIF(SUM(calls_total), 0), 1) AS thoi_luong_tb_giay
FROM public.call_timeseries
WHERE calls_total > 0
GROUP BY 1
ORDER BY 1;


-- 3.3. TỔNG HỢP THEO NHÀ MẠNG (Carrier Fault Breakdown)
--      Dùng cho kỹ thuật viên NOC đối soát chất lượng dịch vụ của từng nhà mạng viễn thông
SELECT
    COALESCE(failed_carrier, 'TOÀN MẠNG ỔN ĐỊNH') AS nha_mang,
    COUNT(*) AS so_khung_15phut,
    SUM(calls_total) AS tong_cuoc_phat_sinh,
    SUM(calls_failed) AS tong_cuoc_loi,
    ROUND(100.0 * SUM(calls_failed) / NULLIF(SUM(calls_total), 0), 2) AS ty_le_loi_pct,
    (ARRAY_AGG(specific_error ORDER BY calls_failed DESC) FILTER (WHERE specific_error IS NOT NULL))[1] AS ma_loi_chinh
FROM public.call_timeseries
WHERE calls_failed > 0
GROUP BY 1
ORDER BY tong_cuoc_loi DESC;


-- ==============================================================================
-- 4. KIỂM THỬ ĐỐI SOÁT DỮ LIỆU (DATA RECONCILIATION & QUALITY AUDIT)
-- ==============================================================================

-- 4.1. Tổng số khung đã tạo, số khung zero-fill, tỷ lệ khung rỗng
SELECT
    COUNT(*)                                             AS tong_khung,
    SUM((is_imputed)::int)                               AS so_khung_rong,
    ROUND(100.0 * SUM((is_imputed)::int) / COUNT(*), 1) AS ty_le_rong
FROM public.call_timeseries;

-- 4.2. Đối soát số lượng cuộc gọi tổng hợp so với dữ liệu nguồn
SELECT
    (SELECT SUM(calls_total) FROM public.call_timeseries) AS tong_cuoc_timeseries,
    (SELECT SUM(calls_failed) FROM public.call_timeseries) AS tong_loi_timeseries,
    COALESCE(
        (SELECT COUNT(*) FROM public.calls_stream WHERE start_time IS NOT NULL),
        (SELECT COUNT(*) FROM public.calls WHERE start_time IS NOT NULL)
    ) AS tong_cuoc_nguon;

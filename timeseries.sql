-- 1. TẠO BẢNG public.call_timeseries 

CREATE TABLE IF NOT EXISTS public.call_timeseries
(
    bucket_time     timestamp without time zone NOT NULL,
    calls_total     integer NOT NULL DEFAULT 0,
    calls_connected integer NOT NULL DEFAULT 0,
    avg_duration    numeric,
    n_employees     integer NOT NULL DEFAULT 0,
    is_imputed      boolean NOT NULL DEFAULT false,
    created_at      timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT call_timeseries_pkey PRIMARY KEY (bucket_time)
);
 
 
-- SELECT result_code, COUNT(*) AS so_luong
-- FROM public.call_results
-- GROUP BY result_code
-- ORDER BY so_luong DESC;
 

-- 2. BUCKET HÓA 15 PHÚT + ZERO-FILL (HỖ TRỢ INCREMENTAL UPSERT - NẠP VI SAI)

INSERT INTO public.call_timeseries (
    bucket_time,
    calls_total,
    calls_connected,
    avg_duration,
    n_employees,
    is_imputed
)
WITH filtered_calls AS (
    -- Chỉ nhận cuộc gọi hợp lệ đã kết thúc
    SELECT
        c.call_id,
        c.start_time,
        c.duration,
        c.employee_id,
        r.result_code
    FROM public.calls c
    LEFT JOIN public.call_results r ON r.result_id = c.result_id
    WHERE c.result_id IS NOT NULL
      AND c.end_time IS NOT NULL
),
bounds AS (
    SELECT
        MIN(start_time) AS min_t,
        MAX(start_time) AS max_t
    FROM filtered_calls
),
buckets AS (
    -- Trục thời gian liên tục 15 phút (đảm bảo không mất khung rỗng)
    SELECT generate_series(
        date_trunc('hour', (SELECT min_t FROM bounds)),
        date_trunc('hour', (SELECT max_t FROM bounds)) + interval '1 hour',
        interval '15 min'
    ) AS bucket_time
),
call_agg AS (
    SELECT
        date_trunc('hour', start_time) 
        + floor(extract(minute FROM start_time) / 15) * interval '15 min' AS bucket_time,
        COUNT(call_id) AS calls_total,
        COUNT(call_id) FILTER (
            WHERE result_code IN ('ANSWERED', 'CALLBACK_REQUESTED', 'NOT_INTERESTED')
        ) AS calls_connected,
        AVG(duration) AS avg_duration,
        COUNT(DISTINCT employee_id) AS n_employees
    FROM filtered_calls
    GROUP BY 1
)
SELECT
    b.bucket_time,
    COALESCE(ca.calls_total, 0)     AS calls_total,
    COALESCE(ca.calls_connected, 0) AS calls_connected,
    ca.avg_duration                 AS avg_duration,
    COALESCE(ca.n_employees, 0)     AS n_employees,
    (ca.calls_total IS NULL)        AS is_imputed
FROM buckets b
LEFT JOIN call_agg ca ON b.bucket_time = ca.bucket_time
ON CONFLICT (bucket_time) DO UPDATE SET
    calls_total     = EXCLUDED.calls_total,
    calls_connected = EXCLUDED.calls_connected,
    avg_duration    = EXCLUDED.avg_duration,
    n_employees     = EXCLUDED.n_employees,
    is_imputed      = EXCLUDED.is_imputed;
 
 

-- 3. TRUY VẤN DẪN XUẤT — thay cho 2 bảng vật lý cũ

-- 3.1. Theo GIỜ, giới hạn tháng 5/2026 (đoạn dữ liệu dày)
--      Dùng để phân tích pattern trong ngày / train mô hình dự báo theo giờ
SELECT
    date_trunc('hour', bucket_time) AS bucket_time,
    SUM(calls_total) AS call_count,
    SUM(avg_duration * calls_total) / NULLIF(SUM(calls_total), 0) AS avg_duration
FROM public.call_timeseries
WHERE bucket_time >= '2026-05-01' AND bucket_time < '2026-06-01'
GROUP BY 1
ORDER BY 1;
 
-- 3.2. Theo NGÀY, toàn bộ khoảng dữ liệu hiện có
--      Dùng để thể hiện xu hướng tổng thể, ít khung rỗng hơn hourly-full-range
SELECT
    date_trunc('day', bucket_time) AS bucket_time,
    SUM(calls_total) AS call_count,
    SUM(avg_duration * calls_total) / NULLIF(SUM(calls_total), 0) AS avg_duration
FROM public.call_timeseries
GROUP BY 1
ORDER BY 1;
 
 

-- 4. KIỂM THỬ 
 
-- 4.1. Tổng số khung đã tạo, số khung zero-fill, tỷ lệ khung rỗng
SELECT
    COUNT(*)                                         AS tong_khung,
    SUM((is_imputed)::int)                           AS so_khung_rong,
    ROUND(100.0 * SUM((is_imputed)::int) / COUNT(*), 1) AS ty_le_rong
FROM public.call_timeseries;
 
-- 4.2. Reconciliation: tổng calls_total phải khớp đúng số cuộc gọi
--      thật (đã lọc) trong toàn bộ khoảng dữ liệu
SELECT
    (SELECT SUM(calls_total) FROM public.call_timeseries) AS tong_tu_bang,
    (SELECT COUNT(*) FROM public.calls
     WHERE result_id IS NOT NULL AND end_time IS NOT NULL) AS tong_tu_calls;


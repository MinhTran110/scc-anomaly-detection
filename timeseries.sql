-- ==============================================================================
-- SCC OUTBOUND TIME-SERIES AGGREGATION & RELATIONAL TELECOM DATABASE
-- Phiên bản: 4.1 (Tối ưu Cú pháp Chuẩn tương thích 100% Công cụ sinh ERD & pgAdmin)
-- ==============================================================================

BEGIN;

-- ==============================================================================
-- PHẦN 1: ĐỊNH NGHĨA SCHEMA QUAN HỆ CHUẨN (TƯƠNG THÍCH HOÀN HẢO ERD TOOL)
-- ==============================================================================

-- 1.1. BẢNG KHÁCH HÀNG (customers)
CREATE TABLE IF NOT EXISTS public.customers
(
    customer_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name   TEXT NOT NULL,
    phone       VARCHAR(20) NOT NULL,
    email       VARCHAR(100),
    address     TEXT,
    created_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON public.customers (phone);


-- 1.2. BẢNG NHÂN VIÊN / TELESALE & QUẢN LÝ (employees)
CREATE TABLE IF NOT EXISTS public.employees
(
    employee_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_code VARCHAR(30) NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         VARCHAR(100) UNIQUE,
    phone         VARCHAR(20) UNIQUE,
    position      VARCHAR(50) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    hire_date     DATE,
    created_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employees_code ON public.employees (employee_code);


-- 1.3. BẢNG CHIẾN DỊCH GỌI RA (campaigns)
CREATE TABLE IF NOT EXISTS public.campaigns
(
    campaign_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_name TEXT NOT NULL,
    description   TEXT,
    start_date    DATE NOT NULL,
    end_date      DATE,
    status        VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'running', 'paused', 'completed', 'canceled')),
    manager_id    INTEGER NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
    created_by    INTEGER NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
    created_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_status ON public.campaigns (status);
CREATE INDEX IF NOT EXISTS idx_campaigns_manager ON public.campaigns (manager_id);


-- 1.4. BẢNG MỤC TIÊU CHIẾN DỊCH (campaign_targets)
CREATE TABLE IF NOT EXISTS public.campaign_targets
(
    campaign_id INTEGER NOT NULL REFERENCES public.campaigns(campaign_id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES public.customers(customer_id) ON DELETE CASCADE,
    added_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    status      VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'in_progress', 'done', 'failed', 'declined')),
    PRIMARY KEY (campaign_id, customer_id)
);

CREATE INDEX IF NOT EXISTS idx_targets_customer ON public.campaign_targets (customer_id);
CREATE INDEX IF NOT EXISTS idx_targets_status ON public.campaign_targets (status);


-- 1.5. BẢNG DANH MỤC TRẠNG THÁI / MÃ LỖI KẾT QUẢ CUỘC GỌI (call_results)
CREATE TABLE IF NOT EXISTS public.call_results
(
    result_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_code     VARCHAR(50) NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    is_system_error BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_call_results_code ON public.call_results (result_code);


-- 1.6. BẢNG CHI TIẾT CUỘC GỌI PHÁT SINH (calls)
CREATE TABLE IF NOT EXISTS public.calls
(
    call_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    start_time  TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_time    TIMESTAMP WITHOUT TIME ZONE,
    duration    INTEGER NOT NULL DEFAULT 0,
    carrier     VARCHAR(50) NOT NULL DEFAULT 'VIETTEL',
    notes       TEXT,
    result_id   INTEGER REFERENCES public.call_results(result_id) ON DELETE SET NULL,
    employee_id INTEGER NOT NULL REFERENCES public.employees(employee_id) ON DELETE RESTRICT,
    customer_id INTEGER NOT NULL REFERENCES public.customers(customer_id) ON DELETE RESTRICT,
    campaign_id INTEGER REFERENCES public.campaigns(campaign_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_calls_start_time ON public.calls (start_time);
CREATE INDEX IF NOT EXISTS idx_calls_employee_time ON public.calls (employee_id, start_time);
CREATE INDEX IF NOT EXISTS idx_calls_result_id ON public.calls (result_id);
CREATE INDEX IF NOT EXISTS idx_calls_carrier ON public.calls (carrier);
CREATE INDEX IF NOT EXISTS idx_calls_campaign_cust ON public.calls (campaign_id, customer_id);


-- 1.7. BẢNG BỘ ĐỆM DÒNG DỮ LIỆU CUỘC GỌI (calls_stream)
CREATE TABLE IF NOT EXISTS public.calls_stream (
    call_id     BIGINT NOT NULL PRIMARY KEY,
    start_time  TIMESTAMP WITHOUT TIME ZONE,
    end_time    TIMESTAMP WITHOUT TIME ZONE,
    duration    INTEGER,
    result_code VARCHAR(50),
    carrier     VARCHAR(50) DEFAULT 'VIETTEL'
);


-- 1.8. BẢNG CHUỖI THỜI GIAN 15 PHÚT (call_timeseries - Aggregate Mart)
CREATE TABLE IF NOT EXISTS public.call_timeseries
(
    bucket_time     TIMESTAMP WITHOUT TIME ZONE NOT NULL PRIMARY KEY,
    calls_total     INTEGER NOT NULL DEFAULT 0,
    calls_connected INTEGER NOT NULL DEFAULT 0,
    calls_failed    INTEGER NOT NULL DEFAULT 0,
    failed_carrier  VARCHAR(50) NOT NULL DEFAULT '-',
    specific_error  VARCHAR(50) NOT NULL DEFAULT '-',
    avg_duration    NUMERIC DEFAULT 0.0,
    n_employees     INTEGER NOT NULL DEFAULT 0,
    is_imputed      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS calls_failed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS failed_carrier VARCHAR(50) DEFAULT '-';
ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS specific_error VARCHAR(50) DEFAULT '-';
ALTER TABLE public.calls_stream ADD COLUMN IF NOT EXISTS carrier VARCHAR(50) DEFAULT 'VIETTEL';


-- 1.9. NẠP DỮ LIỆU DANH MỤC BAN ĐẦU CHO call_results (SEED DATA)
INSERT INTO public.call_results (result_code, description, is_system_error)
VALUES
    ('ANSWERED', 'Khách hàng bắt máy và đàm thoại thành công', false),
    ('BUSY', 'Máy bận hoặc khách bấm từ chối', false),
    ('NO_ANSWER', 'Đổ chuông nhưng khách không nhấc máy', false),
    ('CALLBACK_REQUESTED', 'Khách hẹn gọi lại sau', false),
    ('NOT_INTERESTED', 'Khách hàng không có nhu cầu', false),
    ('VOICEMAIL', 'Chuyển hướng vào hộp thư thoại', false),
    ('WRONG_NUMBER', 'Sai số điện thoại / Thuê bao không tồn tại', false),
    ('503_CONGESTION', 'Nghẽn mạch luồng SIP Trunk Viễn thông', true),
    ('504_GATEWAY_TIMEOUT', 'Hết thời gian chờ Gateway SBC Nhà mạng', true),
    ('500_SERVER_ERROR', 'Lỗi nội bộ hệ thống Tổng đài / Softswitch PBX', true),
    ('429_TOO_MANY_REQUESTS', 'Vượt quá hạn mức tần suất gọi CPS do nhà mạng siết', true),
    ('408_REQUEST_TIMEOUT', 'Hết hạn yêu cầu thiết lập SIP Session', true),
    ('DROP_TRAFFIC', 'Sập tín hiệu đường truyền viễn thông (0 cuộc gọi)', true)
ON CONFLICT (result_code) DO UPDATE SET
    description = EXCLUDED.description,
    is_system_error = EXCLUDED.is_system_error;

-- 1.10. NẠP DỮ LIỆU BAN ĐẦU CHO CÁC BẢNG QUAN HỆ (SEED DATA)
INSERT INTO public.employees (employee_id, employee_code, full_name, email, phone, position, status)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'MGR001', 'Nguyễn Văn Quản Lý', 'quanly@scc.vn', '0901000001', 'Manager', 'active'),
    (2, 'EMP002', 'Trần Thị Thu Trang', 'trangtt@scc.vn', '0901000002', 'Telesale', 'active'),
    (3, 'EMP003', 'Lê Hoàng Long', 'longlh@scc.vn', '0901000003', 'Telesale', 'active'),
    (4, 'EMP004', 'Phạm Minh Đức', 'ducpm@scc.vn', '0901000004', 'Telesale', 'active'),
    (5, 'EMP005', 'Hoàng Bảo Ngọc', 'ngochb@scc.vn', '0901000005', 'Telesale', 'active'),
    (6, 'EMP006', 'Vũ Quốc Anh', 'anhvq@scc.vn', '0901000006', 'Telesale', 'active')
ON CONFLICT (employee_id) DO NOTHING;

INSERT INTO public.campaigns (campaign_id, campaign_name, description, start_date, end_date, status, manager_id, created_by)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'Chiến dịch Outbound Mặc định Q4', 'Chiến dịch quay số tự động chăm sóc khách hàng', '2026-10-01', '2026-12-31', 'running', 1, 1)
ON CONFLICT (campaign_id) DO NOTHING;

INSERT INTO public.customers (customer_id, full_name, phone, email, address)
OVERRIDING SYSTEM VALUE
SELECT i, 'Khách Hàng #' || i, '090' || LPAD(i::text, 7, '0'), 'customer' || i || '@gmail.com', 'Hà Nội, Việt Nam'
FROM generate_series(1, 200) i
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO public.campaign_targets (campaign_id, customer_id, status)
SELECT 1, i, 'queued'
FROM generate_series(1, 200) i
ON CONFLICT (campaign_id, customer_id) DO NOTHING;

COMMIT;


-- ==============================================================================
-- PHẦN 2: BUCKET HÓA 15 PHÚT + ZERO-FILL (INCREMENTAL UPSERT VÀO call_timeseries)
-- ==============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'calls_stream') 
       AND (SELECT COUNT(*) FROM public.calls_stream) > 0 THEN
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
-- PHẦN 3: CÁC TRUY VẤN DẪN XUẤT VẬN HÀNH & GIÁM SÁT NOC
-- ==============================================================================

-- 3.1. Theo GIỜ
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
WHERE calls_total > 0
GROUP BY 1
ORDER BY 1;


-- 3.2. Theo NGÀY
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


-- 3.3. TỔNG HỢP THEO NHÀ MẠNG
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
-- PHẦN 4: KIỂM THỬ ĐỐI SOÁT DỮ LIỆU
-- ==============================================================================
SELECT
    COUNT(*)                                             AS tong_khung,
    SUM((is_imputed)::int)                               AS so_khung_rong,
    ROUND(100.0 * SUM((is_imputed)::int) / COUNT(*), 1) AS ty_le_rong
FROM public.call_timeseries;

SELECT
    (SELECT SUM(calls_total) FROM public.call_timeseries) AS tong_cuoc_timeseries,
    (SELECT SUM(calls_failed) FROM public.call_timeseries) AS tong_loi_timeseries,
    COALESCE(
        (SELECT COUNT(*) FROM public.calls_stream WHERE start_time IS NOT NULL),
        (SELECT COUNT(*) FROM public.calls WHERE start_time IS NOT NULL)
    ) AS tong_cuoc_nguon;

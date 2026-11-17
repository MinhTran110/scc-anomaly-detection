-- =============================================================================
-- MIGRATION: BỔ SUNG CARRIER, PHÂN LOẠI LỖI & THEO DÕI SỰ CỐ VIỄN THÔNG
-- Áp dụng cho: Database chính (MinhTQ70) và Database phụ (scc_postgres)
-- =============================================================================

BEGIN;

-- 1. Bổ sung trường carrier vào bảng calls (nếu chưa có)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'calls') THEN
        ALTER TABLE public.calls ADD COLUMN IF NOT EXISTS carrier VARCHAR(50) DEFAULT 'VIETTEL';
    END IF;
END $$;

-- 2. Bổ sung trường carrier vào bảng calls_stream (nếu chưa có)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'calls_stream') THEN
        ALTER TABLE public.calls_stream ADD COLUMN IF NOT EXISTS carrier VARCHAR(50) DEFAULT 'VIETTEL';
    END IF;
END $$;

-- 3. Bổ sung trường is_system_error vào bảng call_results (nếu có bảng này)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'call_results') THEN
        ALTER TABLE public.call_results ADD COLUMN IF NOT EXISTS is_system_error BOOLEAN NOT NULL DEFAULT false;

        -- Phân loại các mã lỗi kỹ thuật mạng viễn thông / hệ thống
        UPDATE public.call_results SET is_system_error = true 
        WHERE result_code IN ('503_CONGESTION', '500_SERVER_ERROR', '504_GATEWAY_TIMEOUT', '429_TOO_MANY_REQUESTS', '408_REQUEST_TIMEOUT');

        -- Đảm bảo các kết quả người dùng bình thường là false
        UPDATE public.call_results SET is_system_error = false 
        WHERE result_code IN ('ANSWERED', 'BUSY', 'NO_ANSWER', 'CALLBACK_REQUESTED', 'NOT_INTERESTED', 'VOICEMAIL');
    END IF;
END $$;

-- 4. Bổ sung các trường thống kê lỗi vào bảng call_timeseries
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'call_timeseries') THEN
        ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS calls_failed INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS failed_carrier VARCHAR(50);
        ALTER TABLE public.call_timeseries ADD COLUMN IF NOT EXISTS specific_error VARCHAR(50);
    END IF;
END $$;

COMMIT;

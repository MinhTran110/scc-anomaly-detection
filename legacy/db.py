import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
 
# Tìm .env ở thư mục gốc project (1 cấp trên file này nếu để trong src/,
# hoặc cùng cấp nếu để trực tiếp ở gốc) - không phụ thuộc bạn đứng ở đâu
# khi gõ lệnh python.
BASE_DIR = Path(__file__).resolve().parent
for candidate in [BASE_DIR / ".env", BASE_DIR.parent / ".env"]:
    if candidate.exists():
        load_dotenv(dotenv_path=candidate)
        print(f"Đã nạp .env từ: {candidate}")
        break
else:
    print("CẢNH BÁO: không tìm thấy file .env ở", BASE_DIR, "hoặc", BASE_DIR.parent)
 
 
def get_engine():
    """Tạo SQLAlchemy engine kết nối tới database từ .env."""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Thiếu biến trong .env: {missing}")
 
    # URL.create() tự động escape ký tự đặc biệt trong mật khẩu (@, $, *, %,...)
    # KHÔNG tự ghép chuỗi f"...{password}..." vì sẽ hỏng nếu mật khẩu có ký tự URL đặc biệt.
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )
    return create_engine(url)
 
 
if __name__ == "__main__":
    # Chạy trực tiếp file này để test kết nối: python src/db.py
    engine = get_engine()
    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT COUNT(*) FROM calls"))
        print("Kết nối OK. Số dòng trong bảng calls:", result.scalar())
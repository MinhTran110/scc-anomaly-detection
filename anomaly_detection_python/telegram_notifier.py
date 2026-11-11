# telegram_notifier.py
import os
import requests
from pathlib import Path

# Nạp cấu hình từ biến môi trường hoặc file .env nếu có
def _load_env():
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        return
    for path in [Path(".env"), Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent / ".env"]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k not in os.environ:
                            os.environ[k] = v
            break

_load_env()

# Cấu hình Token và Chat ID lấy từ biến môi trường
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
raw_chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in raw_chat_ids.split(",") if cid.strip()] if raw_chat_ids else []
TELEGRAM_PROXIES = {
    "http": os.getenv("HTTP_PROXY", "http://proxy.fpt.vn:80"),
    "https": os.getenv("HTTPS_PROXY", "http://proxy.fpt.vn:80")
}

def send_telegram_message(message: str):
    """Gửi tin nhắn văn bản qua Telegram có hỗ trợ proxy FPT."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("ĐIỀN"):
        print("[Telegram] Chưa cấu hình BOT_TOKEN hoặc CHAT_ID, bỏ qua gửi tin.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    success = False
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload, proxies=TELEGRAM_PROXIES, timeout=10)
            if res.json().get("ok"):
                success = True
        except Exception as e:
            print(f"[Telegram Error] Gửi tin tới {chat_id} thất bại: {e}")
    return success

def send_telegram_photo(caption: str, photo_path: Path):
    """Gửi ảnh đính kèm tin nhắn tổng kết qua Telegram có hỗ trợ proxy FPT."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("ĐIỀN") or not photo_path.exists():
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    success = False
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                res = requests.post(url, data=data, files=files, proxies=TELEGRAM_PROXIES, timeout=15)
                if res.json().get("ok"):
                    success = True
        except Exception as e:
            print(f"[Telegram Error] Gửi ảnh tới {chat_id} thất bại: {e}")
    return success
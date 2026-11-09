# telegram_notifier.py
import requests
from pathlib import Path

# Cấu hình Token và Chat ID của bạn ở đây
TELEGRAM_BOT_TOKEN = "8766045148:AAGDiMEkFpS4fZeshHZfMmctwdBXrFnwldc"
TELEGRAM_CHAT_IDS = ["-5321779393", "8112925591"]
TELEGRAM_PROXIES = {
    "http": "http://proxy.fpt.vn:80",
    "https": "http://proxy.fpt.vn:80"
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
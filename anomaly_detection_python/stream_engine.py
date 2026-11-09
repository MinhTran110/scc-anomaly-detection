# stream_engine.py
"""
Stream Engine: Non-blocking Message Broker Client
Hỗ trợ:
1. Redis Stream (XADD, XREADGROUP, XACK) - Chuẩn Production chống lock file.
2. In-Memory Thread-safe Ring Buffer - Tự động kích hoạt khi chưa có Redis server (Fallback Mode).
"""
import os
import json
import logging
from collections import deque
from threading import Lock
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class StreamEngine:
    def __init__(self, redis_host: str = None, redis_port: int = None, stream_key: str = "scc_call_stream"):
        if redis_host is None:
            redis_host = os.environ.get("REDIS_HOST", "localhost")
        if redis_port is None:
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
        self.stream_key = stream_key
        self.redis_client = None
        self.use_redis = False
        
        # In-Memory fallback buffer (Thread-safe)
        self._local_buffer = deque(maxlen=100000)
        self._lock = Lock()
        
        try:
            import redis
            client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True, socket_timeout=2)
            client.ping()
            self.redis_client = client
            self.use_redis = True
            logging.info(f"✅ Đã kết nối Redis Stream tại {redis_host}:{redis_port} [Stream Key: {stream_key}]")
            
            # Khởi tạo consumer group nếu chưa có
            try:
                self.redis_client.xgroup_create(stream_key, "scc_aggregator_group", id="0", mkstream=True)
            except Exception:
                pass # Group đã tồn tại
        except Exception as e:
            self.use_redis = False
            logging.warning(f"⚠️ Không thể kết nối Redis ({e}). Tự động kích hoạt chế độ: IN-MEMORY THREAD-SAFE STREAM (Fallback Mode).")

    def publish_call(self, record: dict) -> bool:
        """Producer đẩy sự kiện cuộc gọi vào Stream (Non-blocking)."""
        if self.use_redis and self.redis_client:
            try:
                serialized = {k: str(v) for k, v in record.items()}
                self.redis_client.xadd(self.stream_key, serialized)
                return True
            except Exception as e:
                logging.error(f"Lỗi khi xadd vào Redis: {e}")
        
        # Fallback local buffer
        with self._lock:
            self._local_buffer.append(record)
        return True

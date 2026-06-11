"""
统一 JSON 文件缓存，所有 connector 共享。

缓存目录：storage/.cache/
命名规则：{key_hash}.json，内含 {"key": str, "data": any, "expires_at": float|None}
expires_at=None 表示永久缓存（历史财报等不变数据）。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 默认历史回溯期数，供所有 connector 使用
LOOKBACK_PERIODS: int = 8

_CACHE_DIR = Path(__file__).parent.parent / "storage" / ".cache"


class ConnectorCache:
    def __init__(self, cache_dir: Path = _CACHE_DIR) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self._dir / f"{h}.json"

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        expires_at = entry.get("expires_at")
        if expires_at is not None:
            if datetime.now(timezone.utc).timestamp() > expires_at:
                p.unlink(missing_ok=True)
                return None
        return entry.get("data")

    def set(self, key: str, value: Any, ttl_hours: int = 24) -> None:
        """缓存数据，ttl_hours 后过期。"""
        expires_at = datetime.now(timezone.utc).timestamp() + ttl_hours * 3600
        entry = {"key": key, "data": value, "expires_at": expires_at}
        self._path(key).write_text(
            json.dumps(entry, ensure_ascii=False, default=str), encoding="utf-8"
        )

    def set_permanent(self, key: str, value: Any) -> None:
        """永久缓存，不过期（历史财报等不变数据）。"""
        entry = {"key": key, "data": value, "expires_at": None}
        self._path(key).write_text(
            json.dumps(entry, ensure_ascii=False, default=str), encoding="utf-8"
        )

    def invalidate(self, code: str) -> int:
        """删除所有 key 中包含该股票代码的缓存文件，返回删除数量。"""
        removed = 0
        for p in self._dir.glob("*.json"):
            try:
                entry = json.loads(p.read_text(encoding="utf-8"))
                if code in entry.get("key", ""):
                    p.unlink()
                    removed += 1
            except (json.JSONDecodeError, OSError):
                continue
        return removed


# 模块级单例
_cache = ConnectorCache()


def get_cache() -> ConnectorCache:
    return _cache

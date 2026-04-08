from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class StoragePaths:
    base_dir: Path

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    def json_file(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"


_lock = Lock()


def _paths() -> StoragePaths:
    base_dir = Path(__file__).resolve().parents[1]
    return StoragePaths(base_dir=base_dir)


def ensure_data_dir() -> Path:
    paths = _paths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    return paths.data_dir


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(name: str, default: Any) -> Any:
    ensure_data_dir()
    path = _paths().json_file(name)
    if not path.exists():
        return default
    with _lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default


def write_json(name: str, data: Any) -> None:
    ensure_data_dir()
    path = _paths().json_file(name)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with _lock:
        path.write_text(payload, encoding="utf-8")


def upsert_dict_item(name: str, item_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    existing = read_json(name, default={})
    if not isinstance(existing, dict):
        existing = {}
    existing[item_id] = item
    write_json(name, existing)
    return existing[item_id]


def get_dict_item(name: str, item_id: str) -> Optional[Dict[str, Any]]:
    existing = read_json(name, default={})
    if not isinstance(existing, dict):
        return None
    value = existing.get(item_id)
    return value if isinstance(value, dict) else None


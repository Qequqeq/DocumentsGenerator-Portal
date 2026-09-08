# -*- coding: utf-8 -*-
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from app.config import get_settings


class SelfHostService:
    @staticmethod
    def get_requests_file() -> Path:
        settings = get_settings()
        return settings.base_dir / "selfhost_requests.json"

    @staticmethod
    def get_all_requests() -> List[Dict[str, Any]]:
        requests_file = SelfHostService.get_requests_file()
        if not requests_file.exists():
            return []

        try:
            content = requests_file.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception:
            return []

    @staticmethod
    def add_request(name: str, contact: str, comment: str) -> None:
        requests = SelfHostService.get_all_requests()

        requests.append({
            "name": name,
            "contact": contact,
            "comment": comment,
            "created_at": datetime.now().isoformat(),
        })

        requests_file = SelfHostService.get_requests_file()
        requests_file.write_text(
            json.dumps(requests, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
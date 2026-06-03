from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ScrapeDataset


def save_dataset(dataset: ScrapeDataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_dataset(path: Path) -> ScrapeDataset:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    return ScrapeDataset.model_validate(data)

import json
import os
import re
from pathlib import Path
from typing import Dict


def _default_alias_path() -> Path:
    # default: package-relative config/skill-aliases.json
    base = Path(__file__).resolve().parent.parent
    return base / "config" / "skill-aliases.json"


class AliasNormalizer:
    def __init__(self, alias_path: str = None):
        path = Path(alias_path) if alias_path else _default_alias_path()
        if not path.exists():
            self.alias_map: Dict[str, str] = {}
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # normalize keys to simple lower forms
        self.alias_map = {self._canon_key(k): v for k, v in data.items()}

    @staticmethod
    def _canon_key(s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s

    def normalize(self, raw: str) -> str:
        if not raw:
            return raw
        key = self._canon_key(raw)
        if key in self.alias_map:
            return self.alias_map[key]
        # fallback: title-case common separators while preserving known dots (e.g., Node.js)
        s = raw.strip()
        # common canonicalization: keep existing capitalization for dot-containing tokens
        if "." in s:
            return s.title()
        return s.title()


__all__ = ["AliasNormalizer"]
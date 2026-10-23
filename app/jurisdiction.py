"""Jurisdiction tree: which jurisdictions exist, their aliases, and which ones apply to which."""
from __future__ import annotations

import json
import re
from pathlib import Path


class JurisdictionTree:
    def __init__(self, nodes: dict[str, dict] | None = None):
        self.nodes = nodes or {}
        self._alias: dict[str, str] = {}
        for name, info in self.nodes.items():
            self._alias[name.lower()] = name
            for a in info.get("aliases", []):
                self._alias[a.lower()] = name

    @classmethod
    def load(cls, path: Path) -> "JurisdictionTree":
        if not path.exists():
            return cls({})
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @property
    def names(self) -> list[str]:
        return list(self.nodes)

    def resolve(self, name: str | None) -> str | None:
        return self._alias.get(name.strip().lower()) if name and name.strip() else None

    def detect(self, text: str) -> tuple[str, str] | None:
        """Longest alias found in text -> (canonical name, alias). Child names beat parent names."""
        low = text.lower()
        best: tuple[str, str] | None = None
        for alias, canon in self._alias.items():
            if re.search(rf"\b{re.escape(alias)}\b", low):
                if best is None or len(alias) > len(best[1]):
                    best = (canon, alias)
        return best

    def applicable(self, name: str) -> list[str]:
        """The jurisdiction itself plus its ancestors (national law applies inside a province)."""
        chain, cur, guard = [], name, 0
        while cur and guard < 10:
            chain.append(cur)
            cur = self.nodes.get(cur, {}).get("parent")
            guard += 1
        return chain

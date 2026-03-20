"""Provider abstraction for low-frequency research data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from widget.research.models import ResearchSnapshot


class ResearchProvider(ABC):
    @abstractmethod
    def supports(self, symbol: str, category: str) -> bool:
        ...

    @abstractmethod
    def fetch(self, symbol: str, category: str) -> Optional[ResearchSnapshot]:
        ...

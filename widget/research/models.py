"""Normalized research snapshot dataclass."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ResearchSnapshot:
    """One daily low-frequency research snapshot for a symbol."""

    symbol: str
    date: str
    fetched_at: str = ""

    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    pb: Optional[float] = None
    peg: Optional[float] = None

    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    target_mean_price: Optional[float] = None

    market_cap: Optional[float] = None
    currency: str = ""

    inventory: Optional[float] = None
    capex: Optional[float] = None
    book_value_equity: Optional[float] = None
    book_value_per_share: Optional[float] = None
    shares_outstanding: Optional[float] = None

    delta_forward_pe: Optional[float] = None
    delta_pb: Optional[float] = None
    delta_forward_eps: Optional[float] = None
    delta_target_mean_price: Optional[float] = None
    target_revision_proxy_pct: Optional[float] = None

    valuation_mode: str = "FWD_PE"
    provider: str = ""
    source_metadata: dict[str, str] = field(default_factory=dict)
    quality_metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.fetched_at:
            self.fetched_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ResearchSnapshot":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in known})

    def merge(self, other: "ResearchSnapshot") -> "ResearchSnapshot":
        merged = {}
        for key in self.__dataclass_fields__:
            value = getattr(self, key)
            other_value = getattr(other, key)

            if key in {"source_metadata", "quality_metadata"}:
                combined = {}
                if isinstance(other_value, dict):
                    combined.update(other_value)
                if isinstance(value, dict):
                    combined.update(value)
                value = combined
            elif key == "provider":
                providers = []
                for part in (value, other_value):
                    if not part:
                        continue
                    for provider in str(part).split(","):
                        provider = provider.strip()
                        if provider and provider not in providers:
                            providers.append(provider)
                value = ",".join(providers)
            elif value is None:
                value = other_value

            merged[key] = value

        return ResearchSnapshot(**merged)

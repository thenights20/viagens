from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Offer:
    source: str
    title: str
    price: float
    url: str
    store_name: str
    official: bool
    available: bool = True
    original_price: float | None = None
    product_id: str | None = None
    product_key: str = ""
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Anomaly:
    offer: Offer
    baseline_price: float
    baseline_kind: str
    baseline_samples: int
    drop_pct: float
    savings: float
    confidence: str
    revalidated: bool = False
    verification_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.offer.to_dict()
        data.update(
            {
                "baseline_price": round(self.baseline_price, 2),
                "baseline_kind": self.baseline_kind,
                "baseline_samples": self.baseline_samples,
                "drop_pct": round(self.drop_pct, 1),
                "savings": round(self.savings, 2),
                "confidence": self.confidence,
                "revalidated": self.revalidated,
                "verification_note": self.verification_note,
                "status": "active" if self.revalidated and self.offer.available else "unconfirmed",
            }
        )
        return data

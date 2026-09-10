from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Offer


class Source(ABC):
    name: str

    def __init__(self) -> None:
        self.health = {"ok": True, "message": "ok", "items": 0}

    @abstractmethod
    def collect(self) -> list[Offer]:
        raise NotImplementedError

    @abstractmethod
    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        raise NotImplementedError

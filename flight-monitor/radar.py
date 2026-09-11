from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Sequence

MAD_TO_SIGMA = 1.4826
DEFAULT_SCALE_FLOOR = 0.03


def quantile(values: Sequence[float], q: float) -> float | None:
    clean = sorted(float(v) for v in values if v is not None and float(v) > 0)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    q = min(1.0, max(0.0, q))
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[lo]
    weight = pos - lo
    return clean[lo] * (1 - weight) + clean[hi] * weight


def percentile_rank(values: Sequence[float], price: float) -> float:
    clean = [float(v) for v in values if v is not None and float(v) > 0]
    if not clean:
        return 100.0
    return round(sum(1 for v in clean if v <= price) / len(clean) * 100, 1)


def booking_bucket(days_before: int) -> str:
    if days_before <= 7:
        return "0-7"
    if days_before <= 21:
        return "8-21"
    if days_before <= 60:
        return "22-60"
    return "61+"


def departure_season(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    return f"M{d.month:02d}"


def observed_day(observed_at: str) -> str:
    return observed_at[:10] if observed_at else ""


def days_before_departure(obs: dict) -> int:
    try:
        dep = date.fromisoformat(obs["departure_date"])
        stamp = datetime.fromisoformat(obs["observed_at"].replace("Z", "+00:00")).date()
        return max(0, (dep - stamp).days)
    except Exception:
        return 999


@dataclass(slots=True)
class RobustStats:
    samples: int
    distinct_days: int
    median: float
    mad: float
    scale: float
    minimum: float
    maximum: float
    p05: float
    p10: float
    p20: float
    p30: float
    p50: float
    values: tuple[float, ...]

    def z_score(self, price: float) -> float:
        if self.scale <= 0:
            return 0.0
        return round((price - self.median) / self.scale, 2)

    def percentile(self, price: float) -> float:
        return percentile_rank(self.values, price)

    def discount_pct(self, price: float) -> float:
        if self.median <= 0:
            return 0.0
        return round(max(0.0, (self.median - price) / self.median * 100), 1)


def summarise(values: Sequence[float], distinct_days: int = 0, scale_floor: float = DEFAULT_SCALE_FLOOR) -> RobustStats | None:
    clean = [float(v) for v in values if v is not None and float(v) > 0]
    if not clean:
        return None
    med = statistics.median(clean)
    mad = statistics.median(abs(v - med) for v in clean)
    scale = max(mad * MAD_TO_SIGMA, med * scale_floor)
    return RobustStats(
        samples=len(clean),
        distinct_days=distinct_days,
        median=round(med, 2),
        mad=round(mad, 2),
        scale=round(scale, 4),
        minimum=round(min(clean), 2),
        maximum=round(max(clean), 2),
        p05=round(quantile(clean, 0.05) or med, 2),
        p10=round(quantile(clean, 0.10) or med, 2),
        p20=round(quantile(clean, 0.20) or med, 2),
        p30=round(quantile(clean, 0.30) or med, 2),
        p50=round(quantile(clean, 0.50) or med, 2),
        values=tuple(clean),
    )


def _daily_minima(observations: Iterable[dict]) -> tuple[list[float], int]:
    by_day: dict[str, float] = {}
    raw: list[float] = []
    for obs in observations:
        try:
            price = float(obs["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if price <= 0:
            continue
        raw.append(price)
        day = observed_day(str(obs.get("observed_at", "")))
        if day:
            by_day[day] = min(by_day.get(day, price), price)
    values = list(by_day.values()) if len(by_day) >= 3 else raw
    return values, len(by_day)


def choose_baseline(
    observations: Sequence[dict],
    candidate: dict,
    *,
    exclude_run_id: str | None,
    min_bucket_samples: int = 5,
    min_season_samples: int = 5,
    scale_floor: float = DEFAULT_SCALE_FLOOR,
) -> tuple[RobustStats | None, str]:
    history = []
    for obs in observations:
        if exclude_run_id and obs.get("scan_id") == exclude_run_id:
            continue
        if str(obs.get("observed_at", "")) == str(candidate.get("observed_at", "")):
            continue
        history.append(obs)
    if not history:
        return None, "sem histórico"

    bucket = candidate.get("booking_bucket") or booking_bucket(days_before_departure(candidate))
    season = candidate.get("departure_season") or departure_season(candidate["departure_date"])

    same_bucket_season = [
        x for x in history
        if (x.get("booking_bucket") or booking_bucket(days_before_departure(x))) == bucket
        and (x.get("departure_season") or departure_season(x["departure_date"])) == season
    ]
    values, days = _daily_minima(same_bucket_season)
    if len(values) >= min_season_samples:
        return summarise(values, days, scale_floor), f"rota + antecedência {bucket} + mês"

    same_bucket = [
        x for x in history
        if (x.get("booking_bucket") or booking_bucket(days_before_departure(x))) == bucket
    ]
    values, days = _daily_minima(same_bucket)
    if len(values) >= min_bucket_samples:
        return summarise(values, days, scale_floor), f"rota + antecedência {bucket}"

    values, days = _daily_minima(history)
    return summarise(values, days, scale_floor), "histórico geral da rota"


def _discount_points(discount: float) -> float:
    return min(30.0, max(0.0, discount / 40.0 * 30.0))


def _rarity_points(percentile: float) -> float:
    if percentile <= 5:
        return 20.0
    if percentile <= 10:
        return 17.0
    if percentile <= 20:
        return 12.0
    if percentile <= 30:
        return 7.0
    if percentile <= 40:
        return 3.0
    return 0.0


def _z_points(z: float) -> float:
    if z <= -3:
        return 15.0
    if z <= -2:
        return 12.0
    if z <= -1.5:
        return 9.0
    if z <= -1:
        return 5.0
    return 0.0


def _saving_points(saving: float) -> float:
    if saving >= 1500:
        return 10.0
    if saving >= 1000:
        return 8.0
    if saving >= 600:
        return 6.0
    if saving >= 350:
        return 4.0
    if saving >= 200:
        return 2.0
    return 0.0


def _quality_points(candidate: dict, route_observations: Sequence[dict]) -> float:
    stops = int(candidate.get("stops_count") or 0)
    stop_points = 5.0 if stops == 0 else 3.0 if stops == 1 else 1.0 if stops == 2 else 0.0

    duration = int(candidate.get("duration_minutes") or 0)
    durations = [
        int(x.get("duration_minutes") or 0)
        for x in route_observations
        if int(x.get("duration_minutes") or 0) > 0
    ]
    if not duration or not durations:
        duration_points = 2.0
    else:
        med = statistics.median(durations)
        ratio = duration / med if med else 1.0
        if ratio <= 1.05:
            duration_points = 5.0
        elif ratio <= 1.25:
            duration_points = 3.0
        elif ratio <= 1.60:
            duration_points = 1.0
        else:
            duration_points = 0.0
    return stop_points + duration_points


def score_candidate(
    candidate: dict,
    route_observations: Sequence[dict],
    stats: RobustStats | None,
    *,
    external_typical_price: float | None = None,
    confirmation: str = "none",
) -> dict:
    price = float(candidate["price"])
    baseline_price = stats.median if stats else None
    baseline_kind = "histórico próprio" if stats else "sem baseline"

    if (not baseline_price or baseline_price <= 0) and external_typical_price and external_typical_price > price:
        baseline_price = float(external_typical_price)
        baseline_kind = "preço típico Google"

    discount = 0.0
    saving = 0.0
    percentile = 100.0
    z = 0.0
    new_low = False
    near_low = False

    if baseline_price and baseline_price > 0:
        discount = max(0.0, (baseline_price - price) / baseline_price * 100)
        saving = max(0.0, baseline_price - price)
    if stats:
        percentile = stats.percentile(price)
        z = stats.z_score(price)
        new_low = price < stats.minimum
        near_low = price <= stats.minimum * 1.05

    points = 0.0
    points += _discount_points(discount)
    points += _rarity_points(percentile) if stats else min(16.0, float(candidate.get("provider_discount_pct") or 0) / 3)
    points += _z_points(z) if stats else 0.0
    points += 10.0 if new_low else 6.0 if near_low else 0.0
    points += _saving_points(saving)
    points += _quality_points(candidate, route_observations)

    if confirmation == "second_source":
        points += 10.0
    elif confirmation == "same_source_recheck":
        points += 5.0

    score = int(round(min(100.0, points)))
    distinct_days = stats.distinct_days if stats else 0
    samples = stats.samples if stats else 0

    if stats:
        if distinct_days < 2:
            score = min(score, 74)
        elif distinct_days < 4:
            score = min(score, 84)
        elif samples < 8:
            score = min(score, 89)
    elif external_typical_price:
        score = min(score, 82)
    else:
        score = min(score, 59)

    if score >= 90 and confirmation == "second_source" and distinct_days >= 4:
        label = "🔥🔥🔥 TARIFA ANORMAL / POSSÍVEL MISTAKE FARE"
    elif score >= 80:
        label = "🔥🔥 SUPER DEAL"
    elif score >= 70:
        label = "🔥 DEAL"
    elif score >= 60:
        label = "🟢 BOM PREÇO"
    else:
        label = "NORMAL"

    return {
        "deal_score": score,
        "status": label,
        "baseline_price": round(baseline_price, 2) if baseline_price else None,
        "baseline_kind": baseline_kind,
        "discount_pct": round(discount, 1),
        "savings": round(saving, 2),
        "percentile": round(percentile, 1) if stats else None,
        "z_score": round(z, 2) if stats else None,
        "history_count": samples,
        "history_days": distinct_days,
        "p05": stats.p05 if stats else None,
        "p10": stats.p10 if stats else None,
        "p20": stats.p20 if stats else None,
        "p30": stats.p30 if stats else None,
        "p50": stats.p50 if stats else round(baseline_price, 2) if baseline_price else None,
        "lowest_observed": stats.minimum if stats else None,
        "is_new_low": new_low,
        "near_historical_low": near_low,
        "confirmation": confirmation,
    }


def should_repeat_alert(
    previous: dict | None,
    *,
    current_price: float,
    current_score: int,
    today: date,
    improvement_pct: float = 5.0,
    cooldown_days: int = 7,
) -> bool:
    if not previous:
        return True
    try:
        old_price = float(previous["price"])
        old_score = int(previous.get("score", 0))
        last = date.fromisoformat(str(previous["date"]))
    except Exception:
        return True
    improved = old_price > 0 and current_price <= old_price * (1 - improvement_pct / 100.0)
    score_jump = current_score >= old_score + 8
    cooled_down = (today - last).days >= cooldown_days
    return improved or score_jump or cooled_down

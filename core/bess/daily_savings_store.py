"""DailySavingsStore - Immutable daily savings history built from actual periods."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from core.bess import time_utils
from core.bess.prediction_snapshot import PredictionSnapshot
from core.bess.time_utils import get_period_count

logger = logging.getLogger(__name__)

PERSIST_PATH = Path("/data/bess_daily_savings.json")


@dataclass
class DailySavingsRecord:
    """Finalized daily savings rollup from actual sensor periods."""

    date: date
    grid_only_cost: float
    solar_only_cost: float
    optimized_cost: float
    total_savings: float
    solar_savings: float
    battery_contribution: float
    predicted_total_savings: float
    period_count: int
    complete: bool
    currency: str
    finalized_at: datetime


def _record_from_dict(d: dict) -> DailySavingsRecord:
    return DailySavingsRecord(
        date=date.fromisoformat(d["date"]),
        grid_only_cost=d["grid_only_cost"],
        solar_only_cost=d["solar_only_cost"],
        optimized_cost=d["optimized_cost"],
        total_savings=d["total_savings"],
        solar_savings=d["solar_savings"],
        battery_contribution=d["battery_contribution"],
        predicted_total_savings=d["predicted_total_savings"],
        period_count=d["period_count"],
        complete=d["complete"],
        currency=d["currency"],
        finalized_at=datetime.fromisoformat(d["finalized_at"]),
    )


def _first_prediction_snapshot(
    store_date: date, snapshots: list[PredictionSnapshot]
) -> PredictionSnapshot | None:
    day_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.snapshot_timestamp.date() == store_date
    ]
    if not day_snapshots:
        return None

    return min(
        day_snapshots,
        key=lambda snapshot: (
            snapshot.optimization_period,
            snapshot.snapshot_timestamp,
        ),
    )


def build_daily_savings_record(
    store_date: date,
    periods: list,
    prediction_snapshots: list[PredictionSnapshot],
    currency: str,
    finalized_at: datetime | None = None,
) -> DailySavingsRecord | None:
    """Build a daily savings record from stored actual periods.

    Returns None when no actual periods were recorded (finalization should be skipped).
    """
    actual_periods = [
        period
        for period in periods
        if period is not None and period.data_source == "actual"
    ]
    period_count = len(actual_periods)
    if period_count == 0:
        return None

    grid_only_cost = sum(period.economic.grid_only_cost for period in actual_periods)
    solar_only_cost = sum(period.economic.solar_only_cost for period in actual_periods)
    optimized_cost = sum(period.economic.hourly_cost for period in actual_periods)

    total_savings = grid_only_cost - optimized_cost
    solar_savings = grid_only_cost - solar_only_cost
    battery_contribution = solar_only_cost - optimized_cost

    expected_periods = get_period_count(store_date)
    complete = period_count == expected_periods

    first_snapshot = _first_prediction_snapshot(store_date, prediction_snapshots)
    predicted_total_savings = (
        first_snapshot.predicted_daily_savings if first_snapshot is not None else 0.0
    )

    return DailySavingsRecord(
        date=store_date,
        grid_only_cost=grid_only_cost,
        solar_only_cost=solar_only_cost,
        optimized_cost=optimized_cost,
        total_savings=total_savings,
        solar_savings=solar_savings,
        battery_contribution=battery_contribution,
        predicted_total_savings=predicted_total_savings,
        period_count=period_count,
        complete=complete,
        currency=currency,
        finalized_at=finalized_at or time_utils.now(),
    )


class DailySavingsStore:
    """Append-only persistent storage for finalized daily savings records."""

    def __init__(self, persist_path: Path = PERSIST_PATH):
        self._records: list[DailySavingsRecord] = []
        self._persist_path = persist_path
        self._load_from_disk()
        logger.debug("Initialized DailySavingsStore")

    def save_record(self, record: DailySavingsRecord) -> bool:
        """Persist a record. Returns False if the date already exists."""
        if any(existing.date == record.date for existing in self._records):
            logger.info(
                "Daily savings record for %s already exists, skipping write",
                record.date,
            )
            return False

        self._records.append(record)
        self._save_to_disk()
        logger.info("Saved daily savings record for %s", record.date)
        return True

    def list_records(self, days: int = 30) -> list[DailySavingsRecord]:
        """List records newest-first. days=0 returns all records."""
        sorted_records = sorted(
            self._records, key=lambda record: record.date, reverse=True
        )
        if days == 0:
            return sorted_records
        return sorted_records[:days]

    def get_record_count(self) -> int:
        return len(self._records)

    def _save_to_disk(self) -> None:
        data = {"records": [asdict(record) for record in self._records]}

        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w") as file:
                json.dump(data, file, default=str)
            logger.debug(
                "Persisted %d daily savings records to %s",
                len(self._records),
                self._persist_path,
            )
        except Exception as error:
            logger.warning("Failed to persist daily savings records: %s", error)

    def _load_from_disk(self) -> None:
        if not self._persist_path.exists():
            logger.debug("No persisted daily savings file found")
            return

        try:
            with open(self._persist_path) as file:
                data = json.load(file)

            raw_records = data.get("records", [])
            self._records = [_record_from_dict(record) for record in raw_records]
            logger.info(
                "Loaded %d persisted daily savings records from disk",
                len(self._records),
            )
        except Exception as error:
            logger.warning("Failed to load persisted daily savings records: %s", error)

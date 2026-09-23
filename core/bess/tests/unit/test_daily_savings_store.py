"""Unit tests for DailySavingsStore."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.bess.daily_savings_store import DailySavingsRecord, DailySavingsStore

TIMEZONE = ZoneInfo("Europe/Stockholm")


def _sample_record(
    record_date: date = date(2026, 3, 23),
    total_savings: float = 16.7,
) -> DailySavingsRecord:
    return DailySavingsRecord(
        date=record_date,
        grid_only_cost=45.20,
        solar_only_cost=32.10,
        optimized_cost=28.50,
        total_savings=total_savings,
        solar_savings=13.10,
        battery_contribution=3.60,
        predicted_total_savings=14.00,
        period_count=96,
        complete=True,
        currency="SEK",
        finalized_at=datetime(2026, 3, 24, 0, 5, tzinfo=TIMEZONE),
    )


class TestDailySavingsStore:
    def test_save_and_reload_from_disk(self, tmp_path):
        path = tmp_path / "bess_daily_savings.json"
        store = DailySavingsStore(persist_path=path)
        record = _sample_record()

        assert store.save_record(record) is True
        assert store.get_record_count() == 1

        reloaded = DailySavingsStore(persist_path=path)
        records = reloaded.list_records(days=0)
        assert len(records) == 1
        assert records[0].date == date(2026, 3, 23)
        assert records[0].total_savings == pytest.approx(16.7)
        assert records[0].currency == "SEK"

    def test_immutability_skips_duplicate_dates(self, tmp_path):
        path = tmp_path / "bess_daily_savings.json"
        store = DailySavingsStore(persist_path=path)

        assert store.save_record(_sample_record(total_savings=16.7)) is True
        assert store.save_record(_sample_record(total_savings=99.0)) is False
        assert store.get_record_count() == 1
        assert store.list_records(days=0)[0].total_savings == pytest.approx(16.7)

    def test_list_records_days_filter(self, tmp_path):
        path = tmp_path / "bess_daily_savings.json"
        store = DailySavingsStore(persist_path=path)

        store.save_record(_sample_record(date(2026, 3, 21), 10.0))
        store.save_record(_sample_record(date(2026, 3, 22), 11.0))
        store.save_record(_sample_record(date(2026, 3, 23), 12.0))

        recent = store.list_records(days=2)
        assert [record.date.isoformat() for record in recent] == [
            "2026-03-23",
            "2026-03-22",
        ]

        all_records = store.list_records(days=0)
        assert len(all_records) == 3

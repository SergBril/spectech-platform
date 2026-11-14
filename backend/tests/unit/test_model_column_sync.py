"""Синхронизация моделей с БД: round-trip запись/чтение новых колонок.

Колонки добавлены в модели по фактам information_schema (все nullable),
FK проверены по pg_constraint — их нет (гол Integer). Типы: acts ×11,
bank_transactions ×2, vehicles ×1. RequestStatus дополнен до 14 значений
PG enum request_status (has_responses, expired, draft).
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.bank_statement import BankStatement, BankTransaction
from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestStatus
from app.models.finance import Act

ACT_NEW_COLUMNS = [
    ("act_type", "work"),
    ("counterparty_inn", "7701234567"),
    ("counterparty_name", "ООО Ромашка"),
    ("driver_id", 123),
    ("paid_amount", 1500.5),
    ("payment_status", "paid"),
    ("period_start", date(2025, 12, 1)),
    ("period_end", date(2025, 12, 31)),
    ("shift_task_id", 456),
    ("signed_at", datetime(2025, 12, 20, 10, 30)),
    ("signed_by", 789),
]


@pytest.fixture
def act(db_session, sample_contractor):
    a = Act(
        document_number="ACT-SYNC-001",
        client_id=sample_contractor.id,
        act_date=date(2025, 12, 15),
        company_id=sample_contractor.company_id,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture
def bank_tx(db_session, company):
    statement = BankStatement(
        company_id=company.id,
        file_name="sync.txt",
        file_size=100,
        storage_path="sync/sync.txt",
        account_number="40702810000000000001",
        date_start=date(2025, 12, 1),
        date_end=date(2025, 12, 31),
    )
    db_session.add(statement)
    db_session.commit()
    db_session.refresh(statement)

    tx = BankTransaction(
        statement_id=statement.id,
        company_id=company.id,
        bank_transaction_id="SYNC-TX-001",
        document_type="payment_order",
        document_number="123",
        document_date=date(2025, 12, 15),
        direction="incoming",
        amount=Decimal("1000.00"),
        processed_date=date(2025, 12, 15),
        counterparty_name="ООО Ромашка",
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


class TestActNewColumns:
    @pytest.mark.parametrize("column,value", ACT_NEW_COLUMNS)
    def test_write_read(self, db_session, act, column, value):
        setattr(act, column, value)
        act_id = act.id
        db_session.commit()
        db_session.expunge(act)

        fresh = db_session.get(Act, act_id)
        assert getattr(fresh, column) == value

    def test_all_nullable_by_default(self, db_session, act):
        act_id = act.id
        db_session.expunge(act)
        fresh = db_session.get(Act, act_id)
        for column, _ in ACT_NEW_COLUMNS:
            assert getattr(fresh, column) is None

    def test_signed_by_client_at_preserved(self, db_session, act):
        """Существующая signed_by_client_at не сломана добавлением signed_at."""
        client_ts = datetime(2025, 12, 21, 12, 0)
        act.signed_by_client_at = client_ts
        act.signed_at = datetime(2025, 12, 20, 10, 30)
        act_id = act.id
        db_session.commit()
        db_session.expunge(act)

        fresh = db_session.get(Act, act_id)
        assert fresh.signed_by_client_at == client_ts
        assert fresh.signed_at == datetime(2025, 12, 20, 10, 30)


class TestBankTransactionNewColumns:
    def test_matched_act_id_write_read(self, db_session, bank_tx, act):
        bank_tx.matched_act_id = act.id
        tx_id = bank_tx.id
        act_id = act.id
        db_session.commit()
        db_session.expunge(bank_tx)

        fresh = db_session.get(BankTransaction, tx_id)
        assert fresh.matched_act_id == act_id

    def test_source_write_read(self, db_session, bank_tx):
        bank_tx.source = "1c"
        tx_id = bank_tx.id
        db_session.commit()
        db_session.expunge(bank_tx)

        fresh = db_session.get(BankTransaction, tx_id)
        assert fresh.source == "1c"

    def test_nullable_by_default(self, db_session, bank_tx):
        tx_id = bank_tx.id
        db_session.expunge(bank_tx)
        fresh = db_session.get(BankTransaction, tx_id)
        assert fresh.matched_act_id is None
        assert fresh.source is None


class TestVehicleOwnerRate:
    def test_write_read(self, db_session, sample_vehicle):
        sample_vehicle.owner_rate = Decimal("2500.00")
        vehicle_id = sample_vehicle.id
        db_session.commit()
        db_session.expunge(sample_vehicle)

        fresh = db_session.get(Vehicle, vehicle_id)
        assert fresh.owner_rate == Decimal("2500.00")

    def test_nullable_by_default(self, db_session, sample_vehicle):
        vehicle_id = sample_vehicle.id
        db_session.expunge(sample_vehicle)
        fresh = db_session.get(Vehicle, vehicle_id)
        assert fresh.owner_rate is None


class TestRequestStatusSync:
    def test_enum_matches_db(self):
        """Набор зафиксирован по pg_enum: 14 значений request_status."""
        assert {s.value for s in RequestStatus} == {
            "new",
            "processing",
            "assigned",
            "confirmed",
            "released",
            "in_progress",
            "completed",
            "signed",
            "closed",
            "cancelled",
            "disputed",
            "has_responses",
            "expired",
            "draft",
        }

    @pytest.mark.parametrize(
        "status",
        [RequestStatus.has_responses, RequestStatus.expired, RequestStatus.draft],
    )
    def test_new_status_write_read(self, db_session, company, status):
        req = Request(
            company_id=company.id,
            planned_start=datetime(2025, 12, 1, 9, 0),
            planned_end=datetime(2025, 12, 1, 18, 0),
            status=status,
        )
        db_session.add(req)
        db_session.flush()
        req_id = req.id
        db_session.commit()
        db_session.expunge(req)

        fresh = db_session.get(Request, req_id)
        assert fresh.status == status

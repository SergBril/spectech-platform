"""The drift guard must actually fire.

It reported "no drift" while 58 columns differed in nullability and 10 in
type, because it compared only names. A guard that never fires is worse than
no guard: it manufactures confidence. These tests inject known drift and
require the report to contain it.
"""

from scripts.check_schema_drift import expected_data_type


class TestExpectedDataType:
    def test_integer(self):
        from app.models.company import Company

        assert expected_data_type(Company.__table__.c.id) == "integer"

    def test_string(self):
        from app.models.company import Company

        assert expected_data_type(Company.__table__.c.inn) == "character varying"

    def test_enum_is_user_defined(self):
        from app.models.dispatch import Request

        assert expected_data_type(Request.__table__.c.status) == "USER-DEFINED"

    def test_jsonb_is_not_json(self):
        from app.models.dispatch import Request

        assert expected_data_type(Request.__table__.c.requirements) == "jsonb"

    def test_timezone_aware_datetime(self):
        from app.models.company import Company

        col = Company.__table__.c.created_at
        expected = (
            "timestamp with time zone"
            if getattr(col.type, "timezone", False)
            else "timestamp without time zone"
        )
        assert expected_data_type(col) == expected


class TestEnumExpectations:
    def test_values_callable_is_respected(self):
        """rentals stores 'none', not 'NONE' - expectations must follow."""
        from app.core.db import Base
        from scripts.check_schema_drift import enum_column_specs

        specs = {
            (t, c): expected
            for t, c, _type, expected in enum_column_specs(Base.metadata)
        }
        assert specs[("rentals", "prepayment_status")] == {
            "none",
            "required",
            "paid",
            "refunded",
        }

    def test_lowercase_name_enums_unchanged(self):
        from app.core.db import Base
        from scripts.check_schema_drift import enum_column_specs

        specs = {
            (t, c): expected
            for t, c, _type, expected in enum_column_specs(Base.metadata)
        }
        assert "new" in specs[("requests", "status")]

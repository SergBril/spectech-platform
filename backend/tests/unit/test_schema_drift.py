"""Unit-тесты функций сравнения check_schema_drift (подставные данные, без БД)."""

from enum import Enum as PyEnum

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy import Enum as SqlEnum

from scripts.check_schema_drift import (
    collect_drift,
    diff_sets,
    enum_column_specs,
    format_report,
)


class Color(PyEnum):
    red = "RED_VALUE"
    green = "GREEN_VALUE"


class FakeConn:
    """Подставное соединение: отвечает на два запроса collect_drift.

    Строки колонок — 3-кортежи (table, column, udt_name).
    """

    def __init__(self, column_rows, enum_rows):
        self._columns = column_rows
        self._enums = enum_rows

    def execute(self, stmt):
        sql = str(stmt)
        if "information_schema.columns" in sql:
            return iter(self._columns)
        if "pg_enum" in sql:
            return iter(self._enums)
        raise AssertionError(f"неожиданный запрос: {sql}")


def _metadata():
    md = MetaData()
    Table(
        "t",
        md,
        Column("a", Integer, primary_key=True),
        Column("b", Integer),
        Column("color", SqlEnum(Color, name="color_type")),
    )
    return md


def _rows(*extra):
    base = [("t", "a", "int4"), ("t", "b", "int4"), ("t", "color", "color_type")]
    return base + list(extra)


class TestDiffSets:
    def test_no_drift(self):
        assert diff_sets({"a", "b"}, {"a", "b"}) == {
            "model_only": [],
            "db_only": [],
        }

    def test_model_only(self):
        assert diff_sets({"a", "b"}, {"a"}) == {
            "model_only": ["b"],
            "db_only": [],
        }

    def test_db_only(self):
        assert diff_sets({"a"}, {"a", "c"}) == {
            "model_only": [],
            "db_only": ["c"],
        }

    def test_both_directions_sorted(self):
        assert diff_sets({"z", "a"}, {"y", "b"}) == {
            "model_only": ["a", "z"],
            "db_only": ["b", "y"],
        }


class TestEnumColumnSpecs:
    def test_python_enum_uses_names_not_values(self):
        md = MetaData()
        Table("t", md, Column("color", SqlEnum(Color, name="color_type")))
        specs = enum_column_specs(md)
        assert specs == [("t", "color", "color_type", {"red", "green"})]

    def test_string_enum_and_non_native_skipped(self):
        md = MetaData()
        Table(
            "t",
            md,
            Column("status", SqlEnum("a", "b", name="status_type")),
            Column("plain", String(20)),
            Column("nn", SqlEnum(Color, name="nn_type", native_enum=False)),
        )
        specs = enum_column_specs(md)
        assert specs == [("t", "status", "status_type", {"a", "b"})]


class TestCollectDrift:
    def test_clean_schema(self):
        conn = FakeConn(_rows(), [("color_type", "red"), ("color_type", "green")])
        report = collect_drift(conn, _metadata())
        assert report["missing_tables"] == []
        assert report["columns"] == []
        assert report["enums"] == []
        assert report["varchar_enums"] == []

    def test_column_drift_both_directions(self):
        rows = [("t", "a", "int4"), ("t", "c", "int4"), ("t", "color", "color_type")]
        conn = FakeConn(rows, [("color_type", "red"), ("color_type", "green")])
        report = collect_drift(conn, _metadata())
        assert report["columns"] == [
            {"table": "t", "model_only": ["b"], "db_only": ["c"]}
        ]

    def test_missing_table_and_exclusion(self):
        conn = FakeConn([], [])
        report = collect_drift(conn, _metadata())
        assert report["missing_tables"] == ["t"]

        report = collect_drift(conn, _metadata(), excluded=frozenset({"t"}))
        assert report["missing_tables"] == []

    def test_enum_drift(self):
        conn = FakeConn(_rows(), [("color_type", "red"), ("color_type", "blue")])
        report = collect_drift(conn, _metadata())
        assert report["enums"] == [
            {
                "table": "t",
                "column": "color",
                "type": "color_type",
                "model_only": ["green"],
                "db_only": ["blue"],
            }
        ]

    def test_enum_type_absent_in_pg_enum(self):
        conn = FakeConn(_rows(), [])
        report = collect_drift(conn, _metadata())
        assert report["enums"][0]["error"] == "enum-тип отсутствует в pg_enum"

    def test_varchar_enum_skipped_as_info(self):
        """Колонка VARCHAR в БД — не native enum, сравнение пропускается."""
        rows = [("t", "a", "int4"), ("t", "b", "int4"), ("t", "color", "varchar")]
        conn = FakeConn(rows, [])
        report = collect_drift(conn, _metadata())
        assert report["enums"] == []
        assert report["varchar_enums"] == ["t.color"]

    def test_enum_type_mismatch_is_drift(self):
        """Колонка — другой native enum-тип в БД → дрейф."""
        rows = [("t", "a", "int4"), ("t", "b", "int4"), ("t", "color", "other_type")]
        conn = FakeConn(rows, [("other_type", "x")])
        report = collect_drift(conn, _metadata())
        assert "other_type != color_type" in report["enums"][0]["error"]

    def test_db_only_tables_informational(self):
        conn = FakeConn(
            _rows(("legacy", "x", "int4")),
            [("color_type", "red"), ("color_type", "green")],
        )
        report = collect_drift(conn, _metadata())
        assert report["db_only_tables"] == ["legacy"]
        assert report["columns"] == []


class TestFormatReport:
    def test_clean_report_exit_zero(self):
        report = {
            "tables_checked": 1,
            "missing_tables": [],
            "columns": [],
            "enums": [],
            "varchar_enums": [],
            "db_only_tables": [],
        }
        assert "ДРЕЙФ НЕ ОБНАРУЖЕН (exit 0)" in format_report(report)

    def test_drift_report_exit_one(self):
        report = {
            "tables_checked": 1,
            "missing_tables": [],
            "columns": [{"table": "t", "model_only": ["b"], "db_only": []}],
            "enums": [],
            "varchar_enums": [],
            "db_only_tables": [],
        }
        text = format_report(report)
        assert "ОБНАРУЖЕН ДРЕЙФ (exit 1)" in text
        assert "КОЛОНКИ t" in text

"""Архив документов, правила автоназначения, финансовый дашборд.

Восемь обработчиков были написаны без декораторов: страницы получали 404 на всё.
Публикация проверена тестами, потому что за отсутствующим декоратором может
прятаться сломанный обработчик - так было с шаблонами уведомлений.
"""


def test_archive_accepts_multipart_and_finds_the_document(auth_client):
    """Страница шлёт FormData; Body не читает поля формы и дал бы 422."""
    add = auth_client.post(
        "/api/v1/shifts/documents/archive",
        data={
            "title": "Акт по объекту Северный",
            "doc_type": "act",
            "doc_number": "A-1",
        },
    )
    assert add.status_code == 200, add.text

    search = auth_client.get(
        "/api/v1/shifts/documents/archive", params={"q": "Северный"}
    )
    assert search.status_code == 200, search.text
    assert "Северный" in search.text, "добавленный документ не находится"


def test_archive_auto_index_runs(auth_client):
    r = auth_client.post("/api/v1/shifts/documents/archive/auto-index-acts")
    assert r.status_code == 200, r.text


def test_auto_assign_rule_lifecycle(auth_client):
    created = auth_client.post(
        "/api/v1/shifts/auto-assign/rules",
        json={
            "name": "Категория C",
            "rule_type": "license_category",
            "priority": 5,
            "config": {"category": "C"},
        },
    )
    assert created.status_code == 200, created.text

    listed = auth_client.get("/api/v1/shifts/auto-assign/rules")
    assert listed.status_code == 200, listed.text
    rules = listed.json()
    assert isinstance(rules, list)
    rule = next((x for x in rules if x["name"] == "Категория C"), None)
    assert rule is not None, f"правило не появилось в списке: {rules}"

    deleted = auth_client.delete(f"/api/v1/shifts/auto-assign/rules/{rule['id']}")
    assert deleted.status_code == 200, deleted.text
    after = auth_client.get("/api/v1/shifts/auto-assign/rules").json()
    assert all(x["id"] != rule["id"] for x in after), "правило не удалено"


def test_finance_dashboard_returns_the_year_summary_and_months(auth_client):
    r = auth_client.get("/api/v1/shifts/stats/finance-dashboard", params={"year": 2026})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year"] == 2026
    assert set(body["summary"]) >= {
        "total_revenue",
        "total_expenses",
        "total_margin",
        "total_margin_pct",
    }
    assert isinstance(body["months"], list) and body["months"], "нет помесячных данных"


def test_finance_dashboard_export_returns_a_workbook(auth_client):
    import io

    import openpyxl

    r = auth_client.get(
        "/api/v1/shifts/stats/finance-dashboard/export", params={"year": 2026}
    )
    assert r.status_code == 200, r.text
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.active.max_row >= 1

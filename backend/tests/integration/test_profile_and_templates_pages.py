"""Профиль и шаблоны уведомлений: обработчики были написаны, но не опубликованы.

Без декораторов функции не попадают в app.routes, и страницы получали 404.
Публикация сама по себе не гарантия: проверяем, что обработчик действительно
работает и отдаёт то, что читает страница.
"""


def test_profile_returns_the_current_user(auth_client, admin_user):
    r = auth_client.get("/api/v1/shifts/profile/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == admin_user.email
    assert "full_name" in body and "phone" in body
    assert "max_bound" in body


def test_profile_update_persists(auth_client, db_session, admin_user):
    r = auth_client.put(
        "/api/v1/shifts/profile/me",
        json={"full_name": "Иван Петров", "phone": "+79990001122"},
    )
    assert r.status_code == 200, r.text
    assert set(r.json()["changes"]) == {"full_name", "phone"}

    again = auth_client.get("/api/v1/shifts/profile/me")
    assert again.json()["full_name"] == "Иван Петров"
    assert again.json()["phone"] == "+79990001122"


def test_templates_list_and_init(auth_client):
    r = auth_client.get("/api/v1/shifts/notification-templates")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    init = auth_client.post("/api/v1/shifts/notification-templates/init-defaults")
    assert init.status_code == 200, init.text
    assert "created" in init.json()

    after = auth_client.get("/api/v1/shifts/notification-templates")
    assert after.status_code == 200
    assert after.json(), "после инициализации шаблонов нет"


def test_template_update_persists(auth_client):
    auth_client.post("/api/v1/shifts/notification-templates/init-defaults")
    items = auth_client.get("/api/v1/shifts/notification-templates").json()
    assert items
    tmpl_id = items[0]["id"]

    r = auth_client.put(
        f"/api/v1/shifts/notification-templates/{tmpl_id}",
        json={"subject": "Новая тема", "body": "Новый текст", "is_active": False},
    )
    assert r.status_code == 200, r.text

    updated = next(
        t
        for t in auth_client.get("/api/v1/shifts/notification-templates").json()
        if t["id"] == tmpl_id
    )
    assert updated["subject"] == "Новая тема"
    assert updated["body"] == "Новый текст"
    assert updated["is_active"] is False

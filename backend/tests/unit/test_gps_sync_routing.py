"""Routing tests for GPS sync: positions must never mix between vehicles."""

from types import SimpleNamespace as NS

from app.tasks.mapix_sync_task import (
    _account_key,
    _build_routes,
    _object_ids,
    _route_positions,
)


def _veh(vid, ids, provider="mapix", login="atr", api_url="u"):
    return NS(
        id=vid,
        name=f"Vehicle {vid}",
        gps_provider=provider,
        gps_provider_config={
            "login": login,
            "api_url": api_url,
            "object_ids": ids,
        },
    )


def _pos(oid):
    return NS(raw_data={"object_id": oid} if oid else {})


class TestObjectIdParsing:
    def test_csv_string(self):
        assert _object_ids({"object_ids": "18625, 18539 ,6097"}) == [
            "18625",
            "18539",
            "6097",
        ]

    def test_list_of_ints(self):
        assert _object_ids({"object_ids": [18625, 18539]}) == ["18625", "18539"]

    def test_empty_and_missing(self):
        assert _object_ids({}) == []
        assert _object_ids(None) == []
        assert _object_ids({"object_ids": ""}) == []
        assert _object_ids({"object_ids": ", ,"}) == []


class TestAccountKey:
    def test_same_account_grouped(self):
        a = _account_key("mapix", {"login": "atr", "api_url": "u"})
        b = _account_key("mapix", {"login": "atr", "api_url": "u"})
        assert a == b

    def test_different_login_separate(self):
        a = _account_key("mapix", {"login": "atr"})
        b = _account_key("mapix", {"login": "other"})
        assert a != b


class TestBuildRoutes:
    def test_multi_object_claim_is_reported(self):
        route, ambiguous, accounts, multi = _build_routes([_veh(1, "18625,18539,6097")])
        assert multi == [(1, "Vehicle 1", ["18625", "18539", "6097"])]
        assert route == {"18625": 1, "18539": 1, "6097": 1}
        assert not ambiguous

    def test_one_object_per_vehicle_single_account(self):
        vs = [_veh(1, "18625"), _veh(2, "18539"), _veh(3, "6097")]
        route, ambiguous, accounts, multi = _build_routes(vs)
        assert multi == []
        assert not ambiguous
        assert len(accounts) == 1, "same login must be polled once"
        acc = accounts[("mapix", "u", "atr")]
        assert sorted(acc["ids"]) == ["18539", "18625", "6097"]
        assert route == {"18625": 1, "18539": 2, "6097": 3}

    def test_conflicting_claim_marked_ambiguous(self):
        route, ambiguous, _, _ = _build_routes([_veh(1, "111"), _veh(2, "111")])
        assert ambiguous == {"111"}


class TestRoutePositions:
    def test_positions_split_per_vehicle(self):
        vs = [_veh(1, "18625"), _veh(2, "18539"), _veh(3, "6097")]
        route, ambiguous, accounts, _ = _build_routes(vs)
        acc = accounts[("mapix", "u", "atr")]
        by_vehicle, skipped = _route_positions(
            [_pos("18625"), _pos("18539"), _pos("6097")], route, ambiguous, acc
        )
        assert {k: len(v) for k, v in by_vehicle.items()} == {1: 1, 2: 1, 3: 1}
        assert not any(skipped.values())

    def test_ambiguous_object_skipped(self):
        route, ambiguous, accounts, _ = _build_routes([_veh(1, "111"), _veh(2, "111")])
        acc = next(iter(accounts.values()))
        by_vehicle, skipped = _route_positions([_pos("111")], route, ambiguous, acc)
        assert not by_vehicle
        assert skipped["ambiguous"] == 1

    def test_unmapped_object_skipped(self):
        route, ambiguous, accounts, _ = _build_routes([_veh(1, "111")])
        acc = next(iter(accounts.values()))
        by_vehicle, skipped = _route_positions([_pos("999")], route, ambiguous, acc)
        assert not by_vehicle, "must not dump foreign coords into a random vehicle"
        assert skipped["unmapped"] == 1

    def test_legacy_adapter_single_vehicle_fallback(self):
        route, ambiguous, accounts, _ = _build_routes(
            [_veh(7, "", provider="wialon", login="w")]
        )
        acc = next(iter(accounts.values()))
        by_vehicle, skipped = _route_positions([_pos(None)], route, ambiguous, acc)
        assert {k: len(v) for k, v in by_vehicle.items()} == {7: 1}

    def test_legacy_adapter_two_vehicles_refused(self):
        route, ambiguous, accounts, _ = _build_routes(
            [
                _veh(7, "", provider="wialon", login="w"),
                _veh(8, "", provider="wialon", login="w"),
            ]
        )
        acc = next(iter(accounts.values()))
        by_vehicle, skipped = _route_positions([_pos(None)], route, ambiguous, acc)
        assert not by_vehicle, "cannot attribute without object_id"
        assert skipped["no_id"] == 1


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """Minimal session: the sync loop never reaches writes when positions=[]."""

    def __init__(self, rows):
        self._rows = rows
        self.commits = 0

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass

    def add(self, *args):
        pass


def _encrypted_veh(vid, oid, password, login="atr", api_url="https://gps.mapix.su"):
    return NS(
        id=vid,
        name=f"Vehicle {vid}",
        gps_provider="mapix",
        gps_provider_config={
            "login": login,
            "api_url": api_url,
            "password": password,
            "object_ids": [oid],
        },
    )


class TestCredentialsReachTheAdapter:
    """The task must delegate decryption to the factory, never read the secret."""

    def test_account_key_ignores_the_password(self):
        from app.core.crypto import encrypt_secret

        plain = _account_key("mapix", {"login": "atr", "api_url": "u", "password": "p"})
        enc = _account_key(
            "mapix", {"login": "atr", "api_url": "u", "password": encrypt_secret("p")}
        )
        assert plain == enc

    def test_encrypted_and_legacy_vehicles_share_one_account(self):
        """Transition period: one provider account must stay one request."""
        from app.core.crypto import encrypt_secret

        vehicles = [
            _encrypted_veh(1, "111", encrypt_secret("same")),
            _encrypted_veh(2, "222", "same"),
        ]
        route, ambiguous, accounts, multi = _build_routes(vehicles)
        assert len(accounts) == 1
        assert not ambiguous
        assert set(route) == {"111", "222"}

    def test_task_hands_the_factory_an_untouched_ciphertext(self, monkeypatch):
        from app.core.crypto import encrypt_secret
        from app.tasks import mapix_sync_task as task

        secret = encrypt_secret("open-sesame")
        vehicles = [_encrypted_veh(1, "111", secret)]
        seen = {}

        def spy(provider, cfg):
            seen["provider"] = provider
            seen["cfg"] = dict(cfg)
            return NS(get_all_positions_sync=lambda: [])

        monkeypatch.setattr(task, "SessionLocal", lambda: _FakeDB(vehicles))
        monkeypatch.setattr(task, "_broadcast_latest", lambda db: None)
        monkeypatch.setattr(task, "create_gps_adapter", spy)

        task.sync_gps_positions()

        assert seen["provider"] == "mapix"
        assert seen["cfg"]["password"] == secret
        assert seen["cfg"]["password"].startswith("enc::")

    def test_adapter_ends_up_with_the_open_password(self, monkeypatch):
        """Full chain through the real factory: DB ciphertext -> adapter plaintext."""
        from app.core.crypto import encrypt_secret
        from app.services.gps_providers.mapix import MapixAdapter
        from app.tasks import mapix_sync_task as task

        vehicles = [_encrypted_veh(1, "111", encrypt_secret("open-sesame"))]
        captured = {}

        def fake_fetch(self):
            captured["password"] = self.password
            captured["login"] = self.login
            captured["object_ids"] = list(self.object_ids)
            return []

        monkeypatch.setattr(task, "SessionLocal", lambda: _FakeDB(vehicles))
        monkeypatch.setattr(task, "_broadcast_latest", lambda db: None)
        monkeypatch.setattr(MapixAdapter, "get_all_positions_sync", fake_fetch)

        task.sync_gps_positions()

        assert captured["password"] == "open-sesame"
        assert captured["login"] == "atr"
        assert captured["object_ids"] == ["111"]

    def test_legacy_plaintext_still_reaches_the_adapter(self, monkeypatch):
        from app.services.gps_providers.mapix import MapixAdapter
        from app.tasks import mapix_sync_task as task

        vehicles = [_encrypted_veh(1, "111", "plain-legacy")]
        captured = {}

        def fake_fetch(self):
            captured["password"] = self.password
            return []

        monkeypatch.setattr(task, "SessionLocal", lambda: _FakeDB(vehicles))
        monkeypatch.setattr(task, "_broadcast_latest", lambda db: None)
        monkeypatch.setattr(MapixAdapter, "get_all_positions_sync", fake_fetch)

        task.sync_gps_positions()

        assert captured["password"] == "plain-legacy"

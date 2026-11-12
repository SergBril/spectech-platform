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

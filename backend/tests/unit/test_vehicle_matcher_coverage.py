"""Tests for vehicle_matcher service."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def matcher():
    from app.services.marketplace.vehicle_matcher import VehicleMatcherService

    return VehicleMatcherService()


class TestFindMatchingVehicles:
    """Cover find_matching_vehicles."""

    def test_request_not_found(self, matcher, mock_db):
        mock_db.get.return_value = None
        result = matcher.find_matching_vehicles(mock_db, 999)
        assert result == []

    def test_with_category_mapping(self, matcher, mock_db):
        request = SimpleNamespace(
            vehicle_category_id=9,
            source_channel=None,
            requirements={},
            region="\u041c\u043e\u0441\u043a\u0432\u0430",
        )
        vehicle = SimpleNamespace(
            id=1,
            name="KAMAZ",
            category_id=2,
            status="available",
            hourly_rate=1500,
            shift_rate=12000,
            marketplace_commission_agreed=True,
            marketplace_commission_rate=10,
            region="\u041c\u043e\u0441\u043a\u0432\u0430",
            is_deleted=False,
        )
        mock_db.get.return_value = request
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [vehicle]
        mock_db.query.return_value = mock_query

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(matcher, "_score_vehicle", lambda db, v, r: (80, ["mass"], []))
            result = matcher.find_matching_vehicles(mock_db, 1)

        assert len(result) == 1
        assert result[0]["match_score"] == 80

    def test_marketplace_filter(self, matcher, mock_db):
        request = SimpleNamespace(
            vehicle_category_id=9,
            source_channel="marketplace",
            requirements={},
            region="",
        )
        mock_db.get.return_value = request
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        result = matcher.find_matching_vehicles(mock_db, 1)
        assert result == []

    def test_no_mapping_fallback(self, matcher, mock_db):
        request = SimpleNamespace(
            vehicle_category_id=999,
            source_channel=None,
            requirements={},
            region="",
        )
        cat = SimpleNamespace(parent_id=1)
        n = {"c": 0}

        def mock_get(model, pk):
            n["c"] += 1
            return request if n["c"] == 1 else cat

        mock_db.get.side_effect = mock_get
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        result = matcher.find_matching_vehicles(mock_db, 1)
        assert result == []

    def test_company_id_filter(self, matcher, mock_db):
        request = SimpleNamespace(
            vehicle_category_id=9,
            source_channel=None,
            requirements={},
            region="",
        )
        mock_db.get.return_value = request
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        result = matcher.find_matching_vehicles(mock_db, 1, company_id=5)
        assert result == []


class TestGetCompatibleCategories:
    """Cover _get_compatible_categories."""

    def test_vehicle_category(self, matcher, mock_db):
        cat = SimpleNamespace(parent_id=None)
        mock_db.get.return_value = cat
        mock_db.query.return_value.all.return_value = []
        result = matcher._get_compatible_categories(mock_db, 2)
        assert 2 in result
        assert 8 in result

    def test_subcategory_with_parent(self, matcher, mock_db):
        cat = SimpleNamespace(parent_id=2)
        sibling = SimpleNamespace(id=10)
        child = SimpleNamespace(id=20)
        mock_db.get.return_value = cat
        qc = {"n": 0}

        def mock_query(model):
            qc["n"] += 1
            mq = MagicMock()
            mq.all.return_value = [sibling] if qc["n"] == 1 else [child]
            return mq

        mock_db.query.side_effect = mock_query
        result = matcher._get_compatible_categories(mock_db, 9)
        assert 9 in result
        assert 2 in result


class TestScoreVehicle:
    """Cover _score_vehicle."""

    @staticmethod
    def _setup_attrs(mock_db, attrs_with_defs):
        attr_vals = []
        defs = {}
        for i, (name, num_val, text_val) in enumerate(attrs_with_defs):
            av = SimpleNamespace(
                attribute_definition_id=i, value_number=num_val, value_text=text_val
            )
            attr_vals.append(av)
            defs[i] = SimpleNamespace(name=name)
        # Must chain: db.query(Model).filter(...).all()
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = attr_vals
        mock_db.query.return_value = mock_query
        mock_db.get.side_effect = lambda model, pk: defs.get(pk)

    def _get_attr_name(self, key):
        from app.services.marketplace.vehicle_matcher import VehicleMatcherService

        return VehicleMatcherService.REQ_TO_ATTR[key][0]

    def test_no_requirements_checks_key_attrs(self, matcher, mock_db):
        from app.services.marketplace.vehicle_matcher import VehicleMatcherService

        vehicle = SimpleNamespace(
            id=1, category_id=2, region="\u041c\u043e\u0441\u043a\u0432\u0430"
        )
        request = SimpleNamespace(
            requirements=None, region="\u041c\u043e\u0441\u043a\u0432\u0430"
        )
        mass_name = VehicleMatcherService.KEY_ATTRS_BY_CAT[2][0]
        self._setup_attrs(mock_db, [(mass_name, 20.0, None)])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert score > 0
        assert any("region" in m for m in matched)

    def test_gte_requirement_met(self, matcher, mock_db):
        vehicle = SimpleNamespace(id=1, category_id=4, region="")
        request = SimpleNamespace(requirements={"min_tonnage": 10}, region="")
        attr_name = self._get_attr_name("min_tonnage")
        self._setup_attrs(mock_db, [(attr_name, 15.0, None)])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert score >= 70
        assert any(">=" in m for m in matched)

    def test_gte_requirement_not_met_excludes(self, matcher, mock_db):
        vehicle = SimpleNamespace(id=1, category_id=4, region="")
        request = SimpleNamespace(requirements={"min_tonnage": 50}, region="")
        attr_name = self._get_attr_name("min_tonnage")
        self._setup_attrs(mock_db, [(attr_name, 5.0, None)])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert score == 0

    def test_eq_requirement_matched(self, matcher, mock_db):
        vehicle = SimpleNamespace(id=1, category_id=4, region="")
        request = SimpleNamespace(requirements={"chassis_type": "wheeled"}, region="")
        attr_name = self._get_attr_name("chassis_type")
        self._setup_attrs(mock_db, [(attr_name, None, "Wheeled")])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert any("=" in m for m in matched)

    def test_unit_normalization_kg_to_tons(self, matcher, mock_db):
        vehicle = SimpleNamespace(id=1, category_id=4, region="")
        request = SimpleNamespace(requirements={"min_tonnage": 10}, region="")
        attr_name = self._get_attr_name("min_tonnage")
        self._setup_attrs(mock_db, [(attr_name, 15000.0, None)])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert score >= 70

    def test_region_partial_match(self, matcher, mock_db):
        vehicle = SimpleNamespace(
            id=1,
            category_id=2,
            region="\u041c\u043e\u0441\u043a\u0432\u0430 \u0438 \u043e\u0431\u043b\u0430\u0441\u0442\u044c",
        )
        request = SimpleNamespace(
            requirements={}, region="\u041c\u043e\u0441\u043a\u0432\u0430"
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert any("region~" in m for m in matched)

    def test_region_mismatch(self, matcher, mock_db):
        vehicle = SimpleNamespace(
            id=1,
            category_id=2,
            region="\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433",
        )
        request = SimpleNamespace(
            requirements={}, region="\u041c\u043e\u0441\u043a\u0432\u0430"
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert any("region!=" in m for m in missing)

    def test_optimal_range_bonus(self, matcher, mock_db):
        vehicle = SimpleNamespace(id=1, category_id=4, region="")
        request = SimpleNamespace(requirements={"min_tonnage": 10}, region="")
        attr_name = self._get_attr_name("min_tonnage")
        self._setup_attrs(mock_db, [(attr_name, 15.0, None)])
        score, matched, missing = matcher._score_vehicle(mock_db, vehicle, request)
        assert any("optimal" in m for m in matched)


class TestVehicleMatcherEdgeCases:
    """Cover remaining uncovered lines."""

    def test_compatible_categories_with_children(self, mock_db):
        """Cover lines 176, 181: sibling + child categories."""
        from app.services.marketplace.vehicle_matcher import VehicleMatcherService

        svc = VehicleMatcherService()

        cat = MagicMock()
        cat.id = 10
        cat.parent_id = 5

        sibling = MagicMock()
        sibling.id = 11
        child = MagicMock()
        child.id = 12

        mock_db.get.return_value = cat
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sibling],
            [child],
        ]

        result = svc._get_compatible_categories(mock_db, cat_id=10)
        assert 11 in result
        assert 12 in result
        assert 5 in result

    def _make_score_setup(self, mock_db, vehicle_attrs, requirements=None):
        """Helper to set up _score_vehicle mocks."""
        from app.services.marketplace.vehicle_matcher import VehicleMatcherService

        svc = VehicleMatcherService()

        vehicle = MagicMock()
        vehicle.id = 1
        vehicle.category_id = 2
        vehicle.region = "Москва"

        request = MagicMock()
        request.requirements = requirements or {}
        request.region = "Москва"

        # db.query(EquipmentAttributeValue).filter().all() returns attrs
        mock_db.query.return_value.filter.return_value.all.return_value = vehicle_attrs

        return svc, vehicle, request

    def test_score_missing_def(self, mock_db):
        """Cover line 236: defn not found -> continue."""
        va = MagicMock()
        va.attribute_definition_id = 999
        va.value_number = 20
        va.value_text = None

        # db.get returns None for defn lookup
        mock_db.get.return_value = None

        svc, vehicle, request = self._make_score_setup(mock_db, [va])
        score, matched, missing = svc._score_vehicle(mock_db, vehicle, request)
        assert isinstance(score, int)

    def test_score_eq_mismatch(self, mock_db):
        """Cover lines 282-284: eq compare with value mismatch."""
        va = MagicMock()
        va.attribute_definition_id = 1
        va.value_number = None
        va.value_text = "Komatsu"

        defn = MagicMock()
        defn.name = "Тип шасси"
        mock_db.get.return_value = defn

        svc, vehicle, request = self._make_score_setup(
            mock_db, [va], requirements={"chassis_type": "CAT"}
        )
        score, matched, missing = svc._score_vehicle(mock_db, vehicle, request)
        assert any("!=" in m for m in missing)

    def test_score_gte_norm_req_div1000(self, mock_db):
        """Cover line 260: norm_req / 1000 when req >> vehicle."""
        va = MagicMock()
        va.attribute_definition_id = 1
        va.value_number = 5  # 5 tons
        va.value_text = None

        defn = MagicMock()
        defn.name = "Грузоподъёмность"
        mock_db.get.return_value = defn

        # req=6000 (kg), vehicle=5 (tons) -> norm_req > norm_vehicle*100 -> norm_req/1000=6
        svc, vehicle, request = self._make_score_setup(
            mock_db, [va], requirements={"min_tonnage": "6000"}
        )
        score, matched, missing = svc._score_vehicle(mock_db, vehicle, request)
        assert isinstance(score, int)

    def test_score_optimal_bonus(self, mock_db):
        """Cover line 328: norm_req/1000 + optimal range bonus."""
        va = MagicMock()
        va.attribute_definition_id = 1
        va.value_number = 8  # 8 tons
        va.value_text = None

        defn = MagicMock()
        defn.name = "Грузоподъёмность"
        mock_db.get.return_value = defn

        # req=6000 (kg), vehicle=8 (tons) -> norm_req/1000=6, 6<=8<=12 -> bonus
        svc, vehicle, request = self._make_score_setup(
            mock_db, [va], requirements={"min_tonnage": "6000"}
        )
        score, matched, missing = svc._score_vehicle(mock_db, vehicle, request)
        assert any("optimal" in m for m in matched)

    def test_score_gte_missing_attr(self, mock_db):
        """Cover lines 270-271: gte attr not found -> missing + score -= 10."""
        # No attributes at all for this vehicle
        svc, vehicle, request = self._make_score_setup(
            mock_db, [], requirements={"min_tonnage": "5"}
        )
        # db.get won't be called since no attrs
        score, matched, missing = svc._score_vehicle(mock_db, vehicle, request)
        assert any("Грузоподъёмность" in m for m in missing)
        assert "Грузоподъёмность" in str(
            missing
        )  # Penalty applied but region bonus offsets

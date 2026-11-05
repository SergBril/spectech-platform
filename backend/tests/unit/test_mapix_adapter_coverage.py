"""Tests for MapixAdapter GPS provider."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def adapter():
    from app.services.gps_providers.mapix import MapixAdapter

    return MapixAdapter(
        {
            "api_url": "https://test.mapix.su",
            "login": "testuser",
            "password": "testpass",
            "object_ids": ["obj1", "obj2"],
        }
    )


class TestEnsureSession:
    """Cover _ensure_session (lines 55-102)."""

    @pytest.mark.asyncio
    async def test_returns_cached_session(self, adapter):
        adapter._session_valid = True
        mock_cookies = MagicMock()
        mock_cookies.items.return_value = [("PHPSESSID", "abc123")]
        adapter._cookies = mock_cookies

        client = AsyncMock()
        await adapter._ensure_session(client)
        assert result is True
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_credentials(self, adapter):
        adapter.login = ""
        adapter._session_valid = False
        client = AsyncMock()
        await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_success(self, adapter):
        adapter._session_valid = False
        adapter._cookies = None

        mock_response = MagicMock()
        mock_response.status_code = 200

        client = AsyncMock()
        client.post.return_value = mock_response
        # Simulate cookies being set after auth
        client.cookies = {"PHPSESSID": "new_session", "t_uid": "uid123"}

        await adapter._ensure_session(client)
        assert result is True
        assert adapter._session_valid is True

    @pytest.mark.asyncio
    async def test_auth_http_error(self, adapter):
        adapter._session_valid = False
        adapter._cookies = None

        mock_response = MagicMock()
        mock_response.status_code = 403

        client = AsyncMock()
        client.post.return_value = mock_response
        client.cookies = {}

        await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_no_phpsessid(self, adapter):
        adapter._session_valid = False
        adapter._cookies = None

        mock_response = MagicMock()
        mock_response.status_code = 200

        client = AsyncMock()
        client.post.return_value = mock_response
        client.cookies = {"some_other_cookie": "value"}

        await adapter._ensure_session(client)
        assert result is False

    @pytest.mark.asyncio
    async def test_auth_exception(self, adapter):
        adapter._session_valid = False
        adapter._cookies = None

        client = AsyncMock()
        client.post.side_effect = Exception("Network error")

        await adapter._ensure_session(client)
        assert result is False


class TestFetchPositions:
    """Cover _fetch_positions (lines 210-248)."""

    @pytest.mark.asyncio
    async def test_session_fails(self, adapter):
        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                await adapter._fetch_positions()

        assert result == []

    @pytest.mark.asyncio
    async def test_with_object_ids(self, adapter):
        from app.services.gps_providers.base import GpsPointData

        point = GpsPointData(
            latitude=55.75,
            longitude=37.61,
            speed=45,
            heading=180,
            engine_on=True,
            recorded_at=datetime.now(UTC),
            raw_data={},
        )

        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch.object(
                    adapter,
                    "_ensure_session",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    adapter,
                    "_fetch_object_data",
                    new_callable=AsyncMock,
                    return_value=point,
                ),
            ):
                await adapter._fetch_positions()

        assert len(result) == 2  # Two object_ids, both return a point

    @pytest.mark.asyncio
    async def test_fallback_to_main_page(self, adapter):
        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch.object(
                    adapter,
                    "_ensure_session",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    adapter,
                    "_fetch_object_data",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch.object(
                    adapter,
                    "_fetch_positions_from_main_page",
                    new_callable=AsyncMock,
                    return_value=[],
                ) as mock_main,
            ):
                await adapter._fetch_positions()

        mock_main.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_object_ids_uses_main_page(self):
        from app.services.gps_providers.mapix import MapixAdapter

        adapter_no_ids = MapixAdapter(
            {
                "api_url": "https://test.mapix.su",
                "login": "testuser",
                "password": "testpass",
                "object_ids": "",
            }
        )

        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch.object(
                    adapter_no_ids,
                    "_ensure_session",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    adapter_no_ids,
                    "_fetch_positions_from_main_page",
                    new_callable=AsyncMock,
                    return_value=[],
                ) as mock_main,
            ):
                await adapter_no_ids._fetch_positions()

        mock_main.assert_called_once()


class TestGetTrack:
    """Cover get_track (lines 287-315)."""

    @pytest.mark.asyncio
    async def test_session_fails(self, adapter):
        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 5, tzinfo=UTC)

        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                await adapter.get_track(date_from, date_to)

        assert result == []

    @pytest.mark.asyncio
    async def test_track_success(self, adapter):
        from app.services.gps_providers.base import GpsPointData

        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 5, tzinfo=UTC)

        points = [
            GpsPointData(
                latitude=55.75,
                longitude=37.61,
                speed=45,
                heading=180,
                engine_on=True,
                recorded_at=datetime.now(UTC),
                raw_data={},
            )
        ]

        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch.object(
                    adapter,
                    "_ensure_session",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    adapter,
                    "_fetch_positions_from_main_page",
                    new_callable=AsyncMock,
                    return_value=points,
                ),
            ):
                await adapter.get_track(date_from, date_to)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_track_exception(self, adapter):
        date_from = datetime(2026, 11, 1, tzinfo=UTC)
        date_to = datetime(2026, 11, 5, tzinfo=UTC)

        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(side_effect=Exception("Boom"))
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await adapter.get_track(date_from, date_to)

        assert result == []


class TestTestConnection:
    """Cover test_connection and _test_connection_impl (lines 316-end)."""

    @pytest.mark.asyncio
    async def test_connection_success(self, adapter):
        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=True
            ):
                await adapter._test_connection_impl()

        assert result is True

    @pytest.mark.asyncio
    async def test_connection_failure(self, adapter):
        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_client = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(
                adapter, "_ensure_session", new_callable=AsyncMock, return_value=False
            ):
                await adapter._test_connection_impl()

        assert result is False

    @pytest.mark.asyncio
    async def test_connection_exception(self, adapter):
        with patch("app.services.gps_providers.mapix.create_retry_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network down")
            )
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await adapter._test_connection_impl()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_with_db(self, adapter):
        mock_db = MagicMock()
        with patch.object(
            adapter, "_logged_call", new_callable=AsyncMock, return_value=True
        ) as mock_logged:
            await adapter.test_connection(db=mock_db, company_id=1)
        assert result is True
        mock_logged.assert_called_once()


class TestFetchObjectData:
    """Cover _fetch_object_data (lines 103-153)."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"success": True, "lat": 55.75, "long": 37.61})

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is not None
        assert result.latitude == 55.75

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 404

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Not JSON</html>"

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_success_false(self, adapter):
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"success": False})

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_coords(self, adapter):
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"success": True, "lat": 0, "long": 0})

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_object_data(client, "obj1")
        assert result is None

    @pytest.mark.asyncio
    async def test_request_exception(self, adapter):
        client = AsyncMock()
        client.get.side_effect = Exception("Timeout")

        await adapter._fetch_object_data(client, "obj1")
        assert result is None


class TestFetchPositionsFromMainPage:
    """Cover _fetch_positions_from_main_page (lines 154-209)."""

    @pytest.mark.asyncio
    async def test_parse_html_with_objects(self, adapter):
        html = """
        <script>
        var objects = [
            {ObjectId:"18625", Number:"KAMAZ-001", X:"37.6173", Y:"55.7558", Unixdt:"1730800000"},
            {ObjectId:"18626", Number:"CAT-320", X:"37.2540", Y:"55.7760", Unixdt:"1730800100"}
        ];
        </script>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_positions_from_main_page(client)
        assert len(result) == 2
        assert result[0].latitude == 55.7558

    @pytest.mark.asyncio
    async def test_empty_page(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>No data</html>"

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 500

        client = AsyncMock()
        client.get.return_value = mock_response

        await adapter._fetch_positions_from_main_page(client)
        assert result == []

    @pytest.mark.asyncio
    async def test_request_exception(self, adapter):
        client = AsyncMock()
        client.get.side_effect = Exception("Connection refused")

        await adapter._fetch_positions_from_main_page(client)
        assert result == []

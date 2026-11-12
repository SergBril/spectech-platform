"""Background GPS sync: poll providers and store positions per vehicle."""

import logging
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.catalog import Vehicle
from app.models.telematics import GpsPoint
from app.services.gps_providers.factory import create_gps_adapter

logger = logging.getLogger("spectech.tasks.gps_sync")

_skip_counts: dict[int, int] = {}


def _object_ids(config: dict | None) -> list[str]:
    """Normalise provider object ids from a vehicle config."""
    raw = (config or {}).get("object_ids") or []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(x).strip() for x in raw if str(x).strip()]


def _account_key(provider: str, config: dict | None) -> tuple:
    c = config or {}
    return (provider, c.get("api_url", ""), c.get("login", ""))


def _build_routes(vehicles):
    """Map provider object_id -> vehicle_id and group vehicles by account.

    Polling once per account (instead of once per vehicle) avoids hitting the
    provider N times when several vehicles share one login.
    """
    route: dict[str, int] = {}
    ambiguous: set[str] = set()
    accounts: dict[tuple, dict] = {}
    multi: list[tuple] = []

    for v in vehicles:
        cfg = v.gps_provider_config or {}
        ids = _object_ids(cfg)
        if len(ids) > 1:
            multi.append((v.id, v.name, ids))
        for oid in ids:
            if oid in route and route[oid] != v.id:
                ambiguous.add(oid)
            route[oid] = v.id
        acc = accounts.setdefault(
            _account_key(v.gps_provider, cfg),
            {"config": cfg, "ids": set(), "vehicles": []},
        )
        acc["ids"].update(ids)
        acc["vehicles"].append(v)

    return route, ambiguous, accounts, multi


def _route_positions(positions, route, ambiguous, acc):
    """Attribute each position to its own vehicle. Never mix machines."""
    by_vehicle = defaultdict(list)
    skipped = {"ambiguous": 0, "unmapped": 0, "no_id": 0}

    for pos in positions:
        oid = str((pos.raw_data or {}).get("object_id") or "").strip()
        if oid:
            if oid in ambiguous:
                skipped["ambiguous"] += 1
                continue
            target = route.get(oid)
            if target is None:
                skipped["unmapped"] += 1
                continue
        else:
            # Legacy adapters without object_id: only safe if the account
            # maps to exactly one vehicle.
            if len(acc["vehicles"]) != 1:
                skipped["no_id"] += 1
                continue
            target = acc["vehicles"][0].id
        by_vehicle[target].append(pos)

    return by_vehicle, skipped


def sync_gps_positions() -> None:
    """Poll GPS providers and store new positions. Runs every 60s."""
    db: Session = SessionLocal()
    try:
        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.gps_provider.isnot(None),
                Vehicle.gps_provider_config.isnot(None),
                Vehicle.is_deleted == False,  # noqa: E711
            )
            .all()
        )
        if not vehicles:
            return

        logger.info(
            "\U0001f504 GPS sync: found %d vehicle(s) with GPS provider", len(vehicles)
        )

        route, ambiguous, accounts, multi = _build_routes(vehicles)

        for vid, vname, ids in multi:
            logger.warning(
                "\u26a0\ufe0f Vehicle #%s (%s) claims %d provider objects %s: "
                "positions of different machines share one track, so mileage, "
                "engine hours and fuel figures are unreliable. "
                "Assign one object_id per vehicle.",
                vid,
                vname,
                len(ids),
                ids,
            )
        if ambiguous:
            logger.warning(
                "\u26a0\ufe0f GPS objects claimed by several vehicles, skipping: %s",
                sorted(ambiguous),
            )

        vname_by_id = {v.id: v.name for v in vehicles}
        total_new_points = 0

        for key, acc in accounts.items():
            provider = key[0]
            cfg = dict(acc["config"])
            if acc["ids"]:
                cfg["object_ids"] = sorted(acc["ids"])
            try:
                adapter = create_gps_adapter(provider, cfg)
                positions = adapter.get_all_positions_sync()
                if not positions:
                    continue

                by_vehicle, skipped = _route_positions(positions, route, ambiguous, acc)
                if any(skipped.values()):
                    logger.warning(
                        "\u26a0\ufe0f GPS [%s] unattributed positions skipped: %s",
                        provider,
                        skipped,
                    )

                for vid, vpositions in by_vehicle.items():
                    stamps = [p.recorded_at for p in vpositions if p.recorded_at]
                    seen: set = set()
                    if stamps:
                        seen = set(
                            db.execute(
                                select(GpsPoint.recorded_at).where(
                                    GpsPoint.vehicle_id == vid,
                                    GpsPoint.recorded_at.in_(stamps),
                                )
                            ).scalars()
                        )

                    new_points = 0
                    for pos in vpositions:
                        if pos.latitude == 0 and pos.longitude == 0:
                            continue
                        if not pos.recorded_at:
                            continue
                        if pos.recorded_at in seen:
                            continue
                        seen.add(pos.recorded_at)

                        db.add(
                            GpsPoint(
                                vehicle_id=vid,
                                latitude=pos.latitude,
                                longitude=pos.longitude,
                                altitude=getattr(pos, "altitude", None),
                                speed=pos.speed,
                                heading=pos.heading,
                                engine_on=pos.engine_on,
                                fuel_level=getattr(pos, "fuel_level", None),
                                engine_hours=getattr(pos, "engine_hours", None),
                                signal_quality=getattr(pos, "signal_quality", None),
                                recorded_at=pos.recorded_at,
                                received_at=datetime.now(UTC),
                                device_id=(
                                    pos.raw_data.get("imei") if pos.raw_data else None
                                ),
                                raw_data=pos.raw_data,
                            )
                        )
                        new_points += 1

                    name = vname_by_id.get(vid, f"Vehicle #{vid}")
                    if new_points > 0:
                        total_new_points += new_points
                        _skip_counts[vid] = 0
                        logger.info(
                            "\u2705 Vehicle #%s (%s) [%s]: %d new GPS points",
                            vid,
                            name,
                            provider,
                            new_points,
                        )
                    else:
                        _skip_counts[vid] = _skip_counts.get(vid, 0) + 1
                        skip = _skip_counts[vid]
                        if skip % 10 == 1:
                            logger.warning(
                                "\u26a0\ufe0f Vehicle #%s (%s) [%s]: skipped %d "
                                "cycles (no new data)",
                                vid,
                                name,
                                provider,
                                skip,
                            )

            except Exception as e:
                logger.error(
                    "\u274c GPS sync failed for account [%s] %s: %s", provider, key, e
                )
                db.rollback()

        if total_new_points > 0:
            db.commit()
            _broadcast_latest(db)

    except Exception as e:
        logger.error("\u274c GPS sync task error: %s", e)
    finally:
        db.close()


def _broadcast_latest(db: Session) -> None:
    """Push the latest position per vehicle over WebSocket.

    CROSS JOIN LATERAL ... LIMIT 1 does one backward index scan on
    (vehicle_id, recorded_at) per vehicle. The previous GROUP BY max() +
    self-join scanned every chunk twice: measured 8.0 ms vs 0.22 ms, and
    the full scan degrades linearly as the hypertable grows.
    Selecting only the broadcast fields also drops row width 560 -> 53.
    """
    try:
        import asyncio

        from sqlalchemy import text

        from app.services.websocket_manager import manager

        rows = (
            db.execute(
                text(
                    """
                SELECT v.id AS vehicle_id, v.name AS vehicle_name,
                       g.latitude, g.longitude, g.speed, g.heading,
                       g.engine_on, g.fuel_level, g.recorded_at
                FROM vehicles v
                CROSS JOIN LATERAL (
                    SELECT p.latitude, p.longitude, p.speed, p.heading,
                           p.engine_on, p.fuel_level, p.recorded_at
                    FROM gps_points p
                    WHERE p.vehicle_id = v.id
                    ORDER BY p.recorded_at DESC
                    LIMIT 1
                ) g
                WHERE v.is_deleted = false
                """
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            return

        positions = [
            {
                "vehicle_id": r["vehicle_id"],
                "vehicle_name": r["vehicle_name"] or f"Vehicle #{r['vehicle_id']}",
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "speed": r["speed"],
                "heading": r["heading"],
                "engine_on": r["engine_on"],
                "fuel_level": r["fuel_level"],
                "recorded_at": (
                    r["recorded_at"].isoformat() if r["recorded_at"] else None
                ),
            }
            for r in rows
        ]

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(manager.broadcast_positions(positions))
        finally:
            loop.close()
        logger.info("\U0001f4e1 Broadcast %d positions via WebSocket", len(positions))
    except Exception as ws_err:
        logger.warning("\u26a0\ufe0f WebSocket broadcast failed: %s", ws_err)

"""Зашифровать секреты GPS-конфига у существующей техники.

По умолчанию dry-run. Запись только с --apply. Идемпотентен: уже зашифрованные
значения пропускаются. Значения никогда не затираются пустотой, в отчёт и логи
попадают только id техники и статус.
"""

import argparse
import json
import sys
from collections import Counter

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.services.gps_providers.secrets import GPS_SECRET_KEYS, encrypt_gps_secrets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="записать изменения")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== encrypt_gps_secrets [{mode}] ===")

    engine = create_engine(settings.database_url)
    counts: Counter[str] = Counter()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, gps_provider_config FROM vehicles "
                "WHERE gps_provider_config IS NOT NULL ORDER BY id"
            )
        ).all()
        for vid, cfg in rows:
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except Exception:
                    counts["unparsable"] += 1
                    print(f"  vehicle {vid}: unparsable config, skipped")
                    continue
            if not isinstance(cfg, dict) or not cfg:
                counts["no_config"] += 1
                continue

            pending = [
                k
                for k in GPS_SECRET_KEYS
                if isinstance(cfg.get(k), str)
                and cfg[k]
                and not cfg[k].startswith("enc::")
            ]
            already = [
                k
                for k in GPS_SECRET_KEYS
                if isinstance(cfg.get(k), str) and cfg[k].startswith("enc::")
            ]
            for k in already:
                counts["already_encrypted"] += 1
            if not pending:
                counts["nothing_to_do"] += 1
                print(f"  vehicle {vid}: nothing to encrypt")
                continue

            new_cfg = encrypt_gps_secrets(cfg)
            for k in pending:
                counts["encrypted"] += 1
            print(f"  vehicle {vid}: {mode} encrypt {pending}")
            if args.apply:
                conn.execute(
                    text(
                        "UPDATE vehicles SET gps_provider_config = :cfg WHERE id = :vid"
                    ),
                    {"cfg": json.dumps(new_cfg, ensure_ascii=False), "vid": vid},
                )

    engine.dispose()
    print(f"\ncounts: {dict(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

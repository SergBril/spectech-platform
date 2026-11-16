"""Перешифровка секретов компаний активным ENCRYPTION_KEY.

Запуск (cwd=/app в контейнере или backend/ локально):
    python scripts/rotate_company_secrets.py           # dry-run (по умолчанию)
    python scripts/rotate_company_secrets.py --apply   # запись в БД

Правила:
  - поля: companies.diadoc_api_key, companies.sbis_token;
  - пустые значения пропускаются;
  - легаси-открытые (без префикса enc::) НЕ трогаются, попадают в отчёт;
  - при ошибке расшифровки значение ПРОПУСКАЕТСЯ и НИКОГДА не перезаписывается "";
  - значения, уже зашифрованные активным ключом, не меняются (идемпотентность);
  - в логи/отчёт не попадают сами секреты — только company_id, поле и статус.

Exit code: 0 — без ошибок, 1 — есть нечитаемые значения (failed > 0).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.crypto import (  # noqa: E402
    ENC_PREFIX,
    decrypt_secret,
    is_encrypted_with_active_key,
    rotate_secret,
)
from app.core.db import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402

SECRET_FIELDS = ("diadoc_api_key", "sbis_token")


def rotate_company_secrets(db, apply: bool) -> tuple[dict, list[dict]]:
    """Перешифровать секреты компаний активным ключом.

    Возвращает (counts, report). В report только company_id/поле/статус —
    без значений секретов. Запись в БД только при apply=True.
    """
    counts = {
        "rotated": 0,
        "skipped_empty": 0,
        "skipped_plaintext": 0,
        "failed": 0,
        "already_current": 0,
    }
    report: list[dict] = []

    companies = db.execute(select(Company)).scalars().all()
    for company in companies:
        for field in SECRET_FIELDS:
            value = getattr(company, field)
            entry = {"company_id": company.id, "field": field}
            if not value:
                counts["skipped_empty"] += 1
                report.append({**entry, "status": "skipped_empty"})
                continue
            if not value.startswith(ENC_PREFIX):
                counts["skipped_plaintext"] += 1
                report.append({**entry, "status": "skipped_plaintext"})
                continue
            if is_encrypted_with_active_key(value):
                counts["already_current"] += 1
                report.append({**entry, "status": "already_current"})
                continue
            if decrypt_secret(value) == "":
                # Нечитаемое значение НЕ перезаписываем пустотой — только отчёт.
                counts["failed"] += 1
                report.append({**entry, "status": "failed_decrypt"})
                continue
            if apply:
                setattr(company, field, rotate_secret(value))
            counts["rotated"] += 1
            report.append({**entry, "status": "rotated" if apply else "would_rotate"})

    if apply and counts["rotated"]:
        db.commit()
    return counts, report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Перешифровка секретов компаний активным ENCRYPTION_KEY"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="записать изменения (по умолчанию dry-run)",
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== rotate_company_secrets [{mode}] ===")
    with SessionLocal() as db:
        try:
            counts, report = rotate_company_secrets(db, apply=args.apply)
        except Exception:
            db.rollback()
            raise

    for entry in report:
        if entry["status"] not in ("skipped_empty", "already_current"):
            print(
                f"company_id={entry['company_id']} "
                f"field={entry['field']} status={entry['status']}"
            )
    print(f"counts: {counts}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

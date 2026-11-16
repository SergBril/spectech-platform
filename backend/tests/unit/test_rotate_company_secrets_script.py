"""AW: скрипт перешифровки scripts/rotate_company_secrets.py.

dry-run не пишет; --apply перешифровывает активным ключом; legacy plaintext
и нечитаемые значения не трогаются (никогда не перезаписываются "");
повторный запуск идемпотентен; в отчёте нет самих секретов.
"""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import ENC_PREFIX, encrypt_secret, is_encrypted_with_active_key
from app.models.company import Company

pytestmark = [pytest.mark.unit]

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "rotate_company_secrets.py"
)
_spec = importlib.util.spec_from_file_location("rotate_company_secrets", SCRIPT_PATH)
rotate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rotate_mod)


@pytest.fixture
def keys():
    return Fernet.generate_key().decode(), Fernet.generate_key().decode()


def _seal(value, key):
    with patch("app.core.crypto.settings") as st:
        st.ENCRYPTION_KEY = key
        st.ENCRYPTION_KEY_PREVIOUS = ""
        st.environment = "production"
        return encrypt_secret(value)


@pytest.fixture
def companies(db_session, keys):
    old, new = keys
    c_rot = Company(
        name="Rot Co",
        legal_name="ООО Рот",
        inn="7700000051",
        diadoc_api_key=_seal("key-one", old),
        sbis_token=_seal("token-one", old),
    )
    c_plain = Company(
        name="Plain Co",
        legal_name="ООО Плейн",
        inn="7700000052",
        diadoc_api_key="legacy-plain-key",
        sbis_token=None,
    )
    c_bad = Company(
        name="Bad Co",
        legal_name="ООО Бэд",
        inn="7700000053",
        diadoc_api_key=ENC_PREFIX + "garbage",
        sbis_token=_seal("token-three", new),
    )
    db_session.add_all([c_rot, c_plain, c_bad])
    db_session.commit()
    for c in (c_rot, c_plain, c_bad):
        db_session.refresh(c)
    return c_rot, c_plain, c_bad


@pytest.fixture
def active_new(keys):
    old, new = keys
    with patch("app.core.crypto.settings") as st:
        st.ENCRYPTION_KEY = new
        st.ENCRYPTION_KEY_PREVIOUS = old
        st.environment = "production"
        yield


def test_dry_run_does_not_write(db_session, companies, active_new):
    c_rot, _, _ = companies
    before = c_rot.diadoc_api_key
    counts, report = rotate_mod.rotate_company_secrets(db_session, apply=False)
    db_session.refresh(c_rot)
    assert c_rot.diadoc_api_key == before
    assert counts["rotated"] == 2
    assert counts["skipped_plaintext"] == 1
    assert counts["skipped_empty"] == 1
    assert counts["failed"] == 1
    assert counts["already_current"] == 1
    assert all(e["status"] != "rotated" for e in report)


def test_apply_rotates_to_active_key(db_session, companies, active_new):
    c_rot, c_plain, c_bad = companies
    counts, _ = rotate_mod.rotate_company_secrets(db_session, apply=True)
    db_session.refresh(c_rot)
    db_session.refresh(c_plain)
    db_session.refresh(c_bad)
    assert counts["rotated"] == 2
    assert is_encrypted_with_active_key(c_rot.diadoc_api_key) is True
    assert is_encrypted_with_active_key(c_rot.sbis_token) is True
    assert c_plain.diadoc_api_key == "legacy-plain-key"
    assert c_bad.diadoc_api_key == ENC_PREFIX + "garbage"


def test_failed_never_overwritten_with_empty(db_session, companies, active_new):
    _, _, c_bad = companies
    rotate_mod.rotate_company_secrets(db_session, apply=True)
    db_session.refresh(c_bad)
    assert c_bad.diadoc_api_key == ENC_PREFIX + "garbage"


def test_idempotent_second_run(db_session, companies, active_new):
    c_rot, _, _ = companies
    rotate_mod.rotate_company_secrets(db_session, apply=True)
    db_session.refresh(c_rot)
    after_first = c_rot.diadoc_api_key
    counts, _ = rotate_mod.rotate_company_secrets(db_session, apply=True)
    db_session.refresh(c_rot)
    assert counts["rotated"] == 0
    assert c_rot.diadoc_api_key == after_first


def test_report_contains_no_secrets(db_session, companies, active_new):
    _, report = rotate_mod.rotate_company_secrets(db_session, apply=False)
    text = str(report)
    assert "key-one" not in text
    assert "token-one" not in text
    assert "legacy-plain-key" not in text
    assert all(set(e) == {"company_id", "field", "status"} for e in report)

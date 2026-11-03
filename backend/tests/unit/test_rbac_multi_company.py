"""Unit tests for RBAC: multi-company, get_current_company_id, role checks."""

import pytest
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.company import Company
from app.models.user_company import UserCompany


class TestGetCurrentCompanyId:
    """Tests for deps.get_current_company_id with multi-company support."""

    def _create_user(
        self,
        db_session: Session,
        company_id: int | None = None,
        is_superuser: bool = False,
    ) -> User:
        user = User(
            email=f"rbac_test_{id(db_session)}_{company_id}@test.com",
            full_name="RBAC Test User",
            password_hash="test_hash",
            company_id=company_id,
            is_superuser=is_superuser,
            status="active",
        )
        db_session.add(user)
        db_session.flush()
        return user

    def test_regular_user_returns_own_company(self, db_session: Session):
        """Обычный пользователь возвращает свою company_id."""
        from app.api.deps import get_current_company_id

        company = Company(
            name="RC Co",
            legal_name="RC",
            inn="7700000020",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        user = self._create_user(db_session, company_id=company.id)
        db_session.commit()

        result = get_current_company_id(user=user, x_company_id=None, db=db_session)
        assert result == company.id

    def test_user_without_company_raises_403(self, db_session: Session):
        """Пользователь без компании и без user_companies получает 403."""
        from fastapi import HTTPException

        from app.api.deps import get_current_company_id

        user = self._create_user(db_session, company_id=None)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_current_company_id(user=user, x_company_id=None, db=db_session)

        assert exc_info.value.status_code == 403

    def test_multi_company_user_via_user_companies(self, db_session: Session):
        """Multi-company пользователь без company_id получает компанию из user_companies."""
        from app.api.deps import get_current_company_id

        company = Company(
            name="MC Co",
            legal_name="MC",
            inn="7700000021",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        # Пользователь БЕЗ company_id, но с записью в user_companies
        user = self._create_user(db_session, company_id=None)
        uc = UserCompany(
            user_id=user.id, company_id=company.id, role="admin", is_active=True
        )
        db_session.add(uc)
        db_session.commit()

        result = get_current_company_id(user=user, x_company_id=None, db=db_session)
        assert result == company.id

    def test_inactive_user_company_skipped(self, db_session: Session):
        """Неактивная запись в user_companies пропускается."""
        from fastapi import HTTPException

        from app.api.deps import get_current_company_id

        company = Company(
            name="IC Co",
            legal_name="IC",
            inn="7700000022",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        user = self._create_user(db_session, company_id=None)
        uc = UserCompany(
            user_id=user.id, company_id=company.id, role="member", is_active=False
        )
        db_session.add(uc)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_current_company_id(user=user, x_company_id=None, db=db_session)

        assert exc_info.value.status_code == 403

    def test_superuser_with_header(self, db_session: Session):
        """Superuser с X-Company-Id header получает указанную компанию."""
        from app.api.deps import get_current_company_id

        company = Company(
            name="SU Co",
            legal_name="SU",
            inn="7700000023",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        user = self._create_user(db_session, company_id=None, is_superuser=True)
        db_session.commit()

        result = get_current_company_id(
            user=user, x_company_id=str(company.id), db=db_session
        )
        assert result == company.id

    def test_superuser_without_header_gets_first_active(self, db_session: Session):
        """Superuser без header получает первую активную компанию."""
        from app.api.deps import get_current_company_id

        company = Company(
            name="SU2 Co",
            legal_name="SU2",
            inn="7700000024",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()

        user = self._create_user(db_session, company_id=None, is_superuser=True)
        db_session.commit()

        result = get_current_company_id(user=user, x_company_id=None, db=db_session)
        assert result == company.id

    def test_superuser_invalid_header_raises_400(self, db_session: Session):
        """Superuser с невалидным X-Company-Id получает 400."""
        from fastapi import HTTPException

        from app.api.deps import get_current_company_id

        user = self._create_user(db_session, company_id=None, is_superuser=True)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_current_company_id(
                user=user, x_company_id="not_a_number", db=db_session
            )

        assert exc_info.value.status_code == 400

    def test_superuser_nonexistent_company_raises_404(self, db_session: Session):
        """Superuser с несуществующей компанией получает 404."""
        from fastapi import HTTPException

        from app.api.deps import get_current_company_id

        user = self._create_user(db_session, company_id=None, is_superuser=True)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_current_company_id(user=user, x_company_id="99999", db=db_session)

        assert exc_info.value.status_code == 404


class TestRbacPermissionChecks:
    """Tests for rbac_service permission checking."""

    def test_has_permission_valid_role(self):
        """Валидная роль имеет соответствующие права."""
        from app.services.rbac_service import has_permission

        assert has_permission("admin", "vehicles:create") is True
        assert has_permission("admin", "vehicles:read") is True

    def test_has_permission_viewer_limited(self):
        """Viewer имеет только права на чтение."""
        from app.services.rbac_service import has_permission

        assert has_permission("viewer", "vehicles:read") is True
        assert has_permission("viewer", "vehicles:create") is False

    def test_has_permission_dispatcher_role(self):
        """Dispatcher имеет ограниченные права."""
        from app.services.rbac_service import has_permission

        # dispatcher может читать, но не удалять
        assert has_permission("dispatcher", "vehicles:read") is True
        assert has_permission("dispatcher", "vehicles:delete") is False

    def test_check_permission_superuser_bypass(self, db_session: Session):
        """Superuser всегда получает True."""
        from app.services.rbac_service import check_permission

        user = User(
            email="super@rbac.test",
            full_name="Super",
            password_hash="hash",
            is_superuser=True,
            status="active",
        )
        db_session.add(user)
        db_session.commit()

        assert check_permission(db_session, user, "anything", "everything") is True

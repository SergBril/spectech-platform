"""
Factory для создания тестовых пользователей.
"""
import factory
from factory.fuzzy import FuzzyText
from app.models.auth import User
from app.core.security import get_password_hash


class UserFactory(factory.Factory):
    """Factory для создания тестовых пользователей."""
    
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f"user{n}@spectech.dev")
    full_name = factory.Faker("name")
    password_hash = factory.LazyFunction(lambda: get_password_hash("testpass123"))
    is_active = True
    is_superuser = False
    company_id = 1


class SuperUserFactory(UserFactory):
    """Factory для создания суперпользователей."""
    is_superuser = True


class InactiveUserFactory(UserFactory):
    """Factory для создания неактивных пользователей."""
    is_active = False
"""CLI команда для запуска seed данных."""

import click

from app.core.db import SessionLocal
from app.core.seed_data import run_seed


@click.command()
def seed():
    """Создать начальные данные (роли, permissions, пользователи)."""
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed()

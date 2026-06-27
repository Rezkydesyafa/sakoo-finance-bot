from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Category


DEFAULT_CATEGORIES: tuple[dict[str, str], ...] = (
    {"name": "Makanan", "type": "expense"},
    {"name": "Transportasi", "type": "expense"},
    {"name": "Tagihan", "type": "expense"},
    {"name": "Belanja", "type": "expense"},
    {"name": "Hiburan", "type": "expense"},
    {"name": "Kesehatan", "type": "expense"},
    {"name": "Pendidikan", "type": "expense"},
    {"name": "Gaji", "type": "income"},
    {"name": "Tabungan", "type": "income"},
    {"name": "Lainnya", "type": "expense"},
)


def seed_default_categories(db: Session) -> int:
    existing_categories = set(
        db.execute(select(Category.name, Category.type)).all()
    )
    categories_to_create = [
        Category(name=category["name"], type=category["type"])
        for category in DEFAULT_CATEGORIES
        if (category["name"], category["type"]) not in existing_categories
    ]

    if categories_to_create:
        db.add_all(categories_to_create)
        db.flush()

    return len(categories_to_create)


def run() -> None:
    with SessionLocal() as db:
        created_count = seed_default_categories(db)
        db.commit()
        print(f"Seeded {created_count} default categories.")


if __name__ == "__main__":
    run()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Category


DEFAULT_CATEGORIES: tuple[dict[str, object], ...] = (
    {
        "name": "Makanan",
        "type": "expense",
        "keywords": [
            "ayam", "bakso", "cafe", "geprek", "gofood", "grabfood",
            "jajan", "kopi", "makan", "makanan", "minum", "nasi",
            "resto", "sarapan", "seblak", "teh", "warung",
        ],
    },
    {
        "name": "Transportasi",
        "type": "expense",
        "keywords": [
            "angkot", "bbm", "bensin", "bus", "gojek", "grab",
            "kereta", "maxim", "mrt", "ojek", "ojol", "parkir",
            "taksi", "tol", "transport",
        ],
    },
    {
        "name": "Tagihan",
        "type": "expense",
        "keywords": [
            "air", "cicilan", "internet", "kos", "kontrakan", "kuota",
            "listrik", "paket", "pdam", "pulsa", "sewa", "tagihan", "wifi",
        ],
    },
    {
        "name": "Belanja",
        "type": "expense",
        "keywords": [
            "barang", "baju", "belanja", "checkout", "dana", "gopay",
            "lazada", "ovo", "produk", "sepatu", "shopee",
            "supermarket", "tokopedia",
        ],
    },
    {
        "name": "Hiburan",
        "type": "expense",
        "keywords": [
            "bioskop", "game", "hiburan", "liburan", "netflix",
            "nonton", "spotify",
        ],
    },
    {
        "name": "Kesehatan",
        "type": "expense",
        "keywords": [
            "dokter", "kesehatan", "klinik", "obat", "rumah sakit",
            "rs", "vitamin",
        ],
    },
    {
        "name": "Pendidikan",
        "type": "expense",
        "keywords": [
            "buku", "fotokopi", "jurnal", "kampus", "kelas", "kuliah",
            "kursus", "makalah", "pendidikan", "praktikum", "print",
            "sekolah", "skripsi", "tugas", "ukt",
        ],
    },
    {
        "name": "Gaji",
        "type": "income",
        "keywords": [
            "bonus", "freelance", "gaji", "invoice", "pendapatan",
            "salary", "upah",
        ],
    },
    {
        "name": "Uang Saku",
        "type": "income",
        "keywords": ["uang saku", "uang jajan"],
    },
    {
        "name": "Tabungan",
        "type": "income",
        "keywords": ["investasi", "nabung", "saving", "tabung", "tabungan"],
    },
    {"name": "Lainnya", "type": "expense", "keywords": []},
    {"name": "Lainnya", "type": "income", "keywords": []},
)


def seed_default_categories(db: Session) -> int:
    existing_categories = {
        (row[0], row[1]): row
        for row in db.execute(select(Category.name, Category.type, Category.id)).all()
    }
    created = 0

    for cat_def in DEFAULT_CATEGORIES:
        name = str(cat_def["name"])
        cat_type = str(cat_def["type"])
        keywords = cat_def.get("keywords") or []
        key = (name, cat_type)

        if key in existing_categories:
            # Update keywords and is_default on existing categories
            cat_id = existing_categories[key][2]
            category = db.get(Category, cat_id)
            if category is not None:
                if not category.keywords:
                    category.keywords = keywords  # type: ignore[assignment]
                category.is_default = True
                category.is_active = True
        else:
            db.add(
                Category(
                    name=name,
                    type=cat_type,
                    keywords=keywords,  # type: ignore[arg-type]
                    is_default=True,
                    is_active=True,
                )
            )
            created += 1

    db.flush()
    return created


def run() -> None:
    with SessionLocal() as db:
        created_count = seed_default_categories(db)
        db.commit()
        print(f"Seeded {created_count} default categories.")


if __name__ == "__main__":
    run()

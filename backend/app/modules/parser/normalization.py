from __future__ import annotations

import re


CATEGORY_KEYWORD_ALIASES: tuple[tuple[str, str], ...] = (
    ("grabcar", "grab transportasi"),
    ("grab bike", "grab ojek"),
    ("grabfood", "makanan gofood"),
    ("go food", "gofood makanan"),
    ("go-ride", "gojek ojek"),
    ("gojek", "gojek ojek transportasi"),
    ("gosend", "kurir transportasi"),
    ("ojol", "ojek online transportasi"),
    ("maxim", "ojek transportasi"),
    ("indriver", "ojek transportasi"),
    ("pertamax", "bbm bensin transportasi"),
    ("pertalite", "bbm bensin transportasi"),
    ("solar", "bbm bensin transportasi"),
    ("e toll", "tol transportasi"),
    ("e-toll", "tol transportasi"),
    ("pln", "listrik tagihan"),
    ("pdam", "air tagihan"),
    ("indihome", "internet wifi tagihan"),
    ("biznet", "internet wifi tagihan"),
    ("first media", "internet wifi tagihan"),
    ("wifi", "internet tagihan"),
    ("kuota", "paket data pulsa tagihan"),
    ("token listrik", "listrik tagihan"),
    ("shopee", "belanja marketplace"),
    ("tokped", "tokopedia belanja marketplace"),
    ("tokopedia", "belanja marketplace"),
    ("lazada", "belanja marketplace"),
    ("bukalapak", "belanja marketplace"),
    ("tiktok shop", "belanja marketplace"),
    ("alfamart", "belanja supermarket"),
    ("indomaret", "belanja supermarket"),
    ("netflix", "hiburan streaming"),
    ("spotify", "hiburan streaming musik"),
    ("steam", "hiburan game"),
    ("ps plus", "hiburan game"),
    ("disney", "hiburan streaming"),
    ("vidio", "hiburan streaming"),
    ("xxi", "bioskop hiburan"),
    ("cgv", "bioskop hiburan"),
    ("apotek", "obat kesehatan"),
    ("apotik", "obat kesehatan"),
    ("bpjs", "asuransi kesehatan"),
    ("halodoc", "dokter kesehatan"),
    ("alodokter", "dokter kesehatan"),
    ("lab", "laboratorium kesehatan"),
    ("rs ", "rumah sakit kesehatan "),
    ("spp", "sekolah pendidikan"),
    ("ukt", "kuliah pendidikan"),
    ("udemy", "kursus pendidikan"),
    ("coursera", "kursus pendidikan"),
    ("bootcamp", "kursus pendidikan"),
    ("skill academy", "kursus pendidikan"),
    ("duolingo", "kelas bahasa pendidikan"),
    ("salary", "gaji income pemasukan"),
    ("payroll", "gaji income pemasukan"),
    ("thr", "bonus gaji income"),
    ("invoice", "freelance gaji income"),
    ("fee", "honor gaji income"),
    ("honor", "gaji income"),
    ("dividen", "investasi tabungan income"),
    ("dividend", "investasi tabungan income"),
    ("reksadana", "investasi tabungan"),
    ("saham", "investasi tabungan"),
    ("deposito", "tabungan income"),
    ("dana darurat", "tabungan saving"),
)


def normalize_category_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"rp\.?\s*\d+(?:[.,]\d+)*", " nominal ", normalized)
    normalized = re.sub(r"\d+(?:[.,]\d+)?\s*(ribu|rb|k|juta|jt)", " nominal ", normalized)
    normalized = re.sub(r"\b\d+[/-]\d+(?:[/-]\d+)?\b", " tanggal ", normalized)

    for source, replacement in CATEGORY_KEYWORD_ALIASES:
        normalized = normalized.replace(source, replacement)

    normalized = re.sub(r"[^a-zA-Z\u00c0-\u024f\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

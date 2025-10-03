# app/special/akdariyyah.py
from typing import List, Tuple
from schemas import Heir, FurudhItem

ID_ZAWJ = 3; ID_UMM = 18; ID_JADD = 6; ID_UKHT_ABAWAYN = 21

def _q(heirs: List[Heir], i: int) -> int:
    return next((h.quantity for h in heirs if h.id == i), 0)

def is_akdariyyah(heirs: List[Heir]) -> bool:
    # syarat minimal: zawj, umm, jadd, ≥1 ukht abawain; tanpa anak/cucu/ayah
    has_zawj = _q(heirs, ID_ZAWJ) > 0
    has_umm  = _q(heirs, ID_UMM) > 0
    has_jadd = _q(heirs, ID_JADD) > 0
    has_ukht = _q(heirs, ID_UKHT_ABAWAYN) > 0
    has_kids = any(_q(heirs, i) > 0 for i in [1,16,5,17])
    has_father = _q(heirs, 2) > 0
    return has_zawj and has_umm and has_jadd and has_ukht and (not has_kids) and (not has_father)

def apply_akdariyyah(furudh: List[FurudhItem], heirs: List[Heir]) -> Tuple[List[FurudhItem], List[str]]:
    """
    Modifikasi daftar furudh agar mengikuti langkah Akdariyyah.
    Kita pakai narasi Zahrah: Zawj 1/2, Umm 1/6, Jadd 1/6, Ukht ikut muqasamah dengan Jadd (2:1) pada sisa.
    """
    notes = []
    notes.append("Masalah Akdariyyah terdeteksi: Zawj, Umm, Jadd, Ukht Abawain tanpa keturunan & ayah.")
    # Bersihkan item ukht yang sebelumnya mungkin diberi 1/2/2-3 oleh engine umum
    filtered = []
    for f in furudh:
        if f.heir.id == ID_UKHT_ABAWAYN:
            # Ukht tidak mendapat fard di Akdariyyah; akan diproses sebagai muqasamah dgn jadd
            continue
        filtered.append(f)
    # Pastikan Zawj=1/2, Umm=1/6, Jadd=1/6
    def upsert_fraction(lst, hid, name_id, name_ar, qty, frac, num, den, reason):
        # hapus existing hid
        lst[:] = [x for x in lst if x.heir.id != hid]
        lst.append(FurudhItem(
            heir=f.heir.__class__(id=hid, name_id=name_id, name_ar=name_ar),
            quantity=qty, fraction=frac, numerator=num, denominator=den, reason=reason
        ))

    # ambil qty sesuai heirs
    qz = _q(heirs, ID_ZAWJ)
    qu = _q(heirs, ID_UMM)
    qj = _q(heirs, ID_JADD)
    quk= _q(heirs, ID_UKHT_ABAWAYN)

    upsert_fraction(filtered, ID_ZAWJ, "Suami", "زوج", qz, "1/2", 1, 2, "Akdariyyah: Suami tetap 1/2.")
    upsert_fraction(filtered, ID_UMM,  "Ibu",   "أم", qu, "1/6", 1, 6, "Akdariyyah: Ibu 1/6 karena bersama Jadd.")
    upsert_fraction(filtered, ID_JADD, "Kakek","جد", qj, "1/6", 1, 6, "Akdariyyah: Jadd 1/6 lalu muqasamah dengan Ukht.")
    # masukkan Ukht sebagai 'Ashobah (muqasamah) – kalkulator akan bagi sisa 2:1 dgn Jadd
    filtered.append(FurudhItem(
        heir=f.heir.__class__(id=ID_UKHT_ABAWAYN, name_id="Saudari Kandung", name_ar="أخت لأبوين"),
        quantity=quk,
        fraction="Ashobah", numerator=0, denominator=1,
        reason="Akdariyyah: Ukht jadi asabah ma‘a al-Jadd (muqasamah 2:1 pada sisa)."
    ))
    notes.append("Bagian fard ditetapkan (1/2, 1/6, 1/6). Ukht dialihkan ke muqasamah bersama Jadd (2:1) pada sisa.")
    return filtered, notes

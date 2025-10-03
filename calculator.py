# calculator.py

from __future__ import annotations
from typing import Dict, List, Tuple
from math import gcd

from sqlalchemy.orm import Session

import crud
import schemas
from app.rules.engine import determine_furudh
from app.math.ashl import compute_ashl

# --------------------------
# AUL yang sah (kitab)
# --------------------------
VALID_AUL = {
    6: {7, 8, 9, 10},
    12: {13, 15, 17},
    24: {27},
}

# --------------------------
# Helper umum
# --------------------------
def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b if a and b else a or b

def _relation(a: int, b: int) -> str:
    if a == b:
        return "mumatsalah"
    if a % b == 0 or b % a == 0:
        return "mudakholah"
    g = gcd(a, b)
    return "mubayanah" if g == 1 else "muwafaqoh"

def _is_group_two_thirds(item) -> bool:
    """
    True bila item adalah kelompok yang mendapat 2/3 sebagai BAGIAN GOLONGAN:
    - Anak Perempuan (>=2)
    - Cucu Perempuan (>=2, tanpa anak perempuan)
    - Saudari Kandung (>=2, syarat kitab)
    - Saudari Seayah (>=2, syarat kitab)
    """
    return (
        item.fraction == "2/3"
        and item.heir.name_id in {"Anak Perempuan", "Cucu Perempuan", "Saudari Kandung", "Saudari Seayah"}
        and item.quantity >= 2
    )

def _is_spouse(heir_id: int) -> bool:
    # 3 = Suami, 4 = Istri (sinkron database)
    return heir_id in {3, 4}

def _is_male_asabah_id(heir_id: int) -> bool:
    """
    Laki-laki ‘ashabah untuk pembobotan 2:1 (sinkron ID dengan engine/DB)
    """
    return heir_id in {
        1,   # Anak Laki-laki
        5,   # Cucu Laki-laki (dari anak laki-laki)
        2,   # Ayah
        6,   # Kakek
        7,   # Saudara Laki-laki Kandung
        8,   # Saudara Laki-laki Seayah
        10,  # Keponakan Laki-laki (sdr lk kandung)
        11,  # Keponakan Laki-laki (sdr lk seayah)
        12,  # Paman Kandung
        13,  # Paman Seayah
        14,  # Sepupu Laki-laki (paman kandung)
        15,  # Sepupu Laki-laki (paman seayah)
        24,  # Pria Pembebas Budak
    }
# === Helper: tampilkan ahli waris yang MAHJŪB (terhalang) ===
def _append_mahjub_shares(db, heirs_input, furudh_items, notes):
    """
    Kembalikan list HeirShare bernilai 0 untuk ahli waris yang dikirim di request
    tetapi tidak muncul di furudh_items (artinya mahjūb/terhalang).
    """
    shares_mahjub = []

    # id-id yang sudah mendapatkan bagian (furūdh/ashabah)
    already_listed_ids = {f.heir.id for f in furudh_items}

    # deteksi penyebab hijab yang paling umum untuk keterangan
    present_ids = {h.id for h in heirs_input}
    has_son_or_grandson = (1 in present_ids) or (5 in present_ids)     # Anak Lk / Cucu Lk (dr anak lk)
    has_father_or_grandfather = (2 in present_ids) or (6 in present_ids)

    # fungsi ambil metadata Heir dari DB bila perlu
    def _get_heir_meta(hid):
        # kalau sudah ada di furudh_items, ambil dari sana (lebih cepat)
        for f in furudh_items:
            if f.heir.id == hid:
                return f.heir
        # fallback: ambil dari DB
        heir_row = None
        if hasattr(crud, "get_heir_by_id"):
            heir_row = crud.get_heir_by_id(db, hid)
        else:
            rows = crud.get_heirs_by_ids(db, [hid])  # return list
            heir_row = rows[0] if rows else None
        if heir_row:
            return schemas.Heir(id=heir_row.id, name_id=heir_row.name_id, name_ar=heir_row.name_ar)
        # fallback minimal
        return schemas.Heir(id=hid, name_id=f"ID {hid}", name_ar="-")

    for h in heirs_input:
        if h.id not in already_listed_ids:
            heir_meta = _get_heir_meta(h.id)

            # alasan generik + sedikit konteks
            if has_son_or_grandson:
                reason = "Mahjūb (terhalang) oleh keturunan laki-laki."
            elif has_father_or_grandfather:
                reason = "Mahjūb (terhalang) oleh ayah/kakek."
            else:
                reason = "Mahjūb (terhalang) menurut kaidah hijāb."

            notes.append(f"{heir_meta.name_id} mahjūb (terhalang).")
            shares_mahjub.append(
                schemas.HeirShare(
                    heir=heir_meta,
                    quantity=h.quantity,
                    share_fraction="-",
                    saham=0,
                    reason=reason,
                    share_amount=0.0,
                )
            )
    return shares_mahjub


# --------------------------
# Inkisār umum (tashīḥ ×k)
# --------------------------
def _apply_inkisar(AM_current: int,
                   furudh_items: List[schemas.FurudhItem],
                   saham_map: Dict[int, int],
                   notes: List[str]) -> int:
    """
    Cek kelompok (quantity>1) yang sahamnya belum terbagi utuh → cari faktor tashīḥ ×k,
    lalu kalikan AM & seluruh saham. Menambahkan catatan perbandingan (adad ar-ru'us vs saham).
    Return AM baru (setelah dikali k).
    """
    groups: List[Tuple[schemas.FurudhItem, int, int]] = []

    for f in furudh_items:
        if f.fraction == "Ashobah" or f.quantity <= 1:
            continue
        # saham_map menyimpan TOTAL saham kelompok (untuk 2/3 = saham golongan; lainnya = per_orang × qty)
        saham_kelompok = saham_map.get(f.heir.id, 0)
        qty = f.quantity
        if qty > 0 and saham_kelompok % qty != 0:
            groups.append((f, saham_kelompok, qty))

    if not groups:
        return AM_current

    # faktor tashīḥ minimal gabungan
    k = 1
    for _, saham_kelompok, qty in groups:
        g = gcd(saham_kelompok, qty)
        m = qty // g
        k = _lcm(k, m)

    # catatan perbandingan setiap kelompok
    for f, saham_kelompok, qty in groups:
        rel = _relation(saham_kelompok, qty)
        notes.append(
            f"Inkisār {f.heir.name_id}: عدد الرؤوس = {qty}, saham golongan = {saham_kelompok} → {rel} "
            f"(gcd={gcd(saham_kelompok, qty)})"
        )

    if k > 1:
        AM_before = AM_current
        AM_current *= k
        # kalikan semua saham
        for hid in list(saham_map.keys()):
            saham_map[hid] *= k
        notes.append(f"Tashīḥ inkisār: ×{k}. Ashlul Mas’alah akhir: {AM_before} × {k} = {AM_current}")

    return AM_current

# --------------------------
# Distribusi Ashobah campur (2:1) dengan tashīḥ jika perlu
# --------------------------
def _distribute_ashobah_mixed(ashl_info,
                              ashobah_items: List[schemas.FurudhItem],
                              sisa: int,
                              saham_map: Dict[int, int],
                              notes: List[str]) -> int:
    """
    Bagi sisa ke ashabah campur 2:1. Jika sisa tidak habis dibagi total bobot, lakukan tashīḥ AM & saham.
    Return total saham tambahan yang dialokasikan.
    """
    if sisa <= 0 or not ashobah_items:
        return 0

    if len(ashobah_items) == 1:
        f = ashobah_items[0]
        saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + sisa
        notes.append(f"{f.heir.name_id} mendapat sisa {sisa} saham sebagai Ashobah")
        return sisa

    # Campur
    total_bobot = 0
    bobot_per_heir: Dict[int, Tuple[int, int, int]] = {}
    for f in ashobah_items:
        wpc = 2 if _is_male_asabah_id(f.heir.id) else 1  # weight per capita
        bobot = wpc * f.quantity
        bobot_per_heir[f.heir.id] = (wpc, f.quantity, bobot)
        total_bobot += bobot

    # Tashīḥ bila sisa tidak habis oleh total_bobot
    g = gcd(sisa, total_bobot)
    k = total_bobot // g
    if k > 1:
        AM_before = ashl_info.ashl_akhir
        # skala AM & saham yang sudah ada
        for hid in list(saham_map.keys()):
            saham_map[hid] *= k
        sisa *= k
        ashl_info.ashl_akhir *= k
        notes.append(
            f"Inkisār Ashobah: sisa = {sisa//k}, total bobot = {total_bobot} → tashīḥ ×{k}. "
            f"Ashlul Mas’alah akhir: {AM_before} × {k} = {ashl_info.ashl_akhir}"
        )

    # Alokasi proporsional
    tambahan = 0
    for f in ashobah_items:
        _, _, bobot = bobot_per_heir[f.heir.id]
        bagian = (sisa * bobot) // total_bobot
        saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + bagian
        tambahan += bagian

    # catatan bobot
    detail = []
    for f in ashobah_items:
        wpc, qty, bobot = bobot_per_heir[f.heir.id]
        jenis = "laki-laki" if wpc == 2 else "perempuan"
        detail.append(f"{f.heir.name_id} ({qty} {jenis}) → bobot {bobot}")
    notes.append(f"Ashobah campur (2:1): total bobot = {total_bobot}; " + "; ".join(detail))

    return tambahan

# --------------------------
# AUL guard
# --------------------------
def _maybe_apply_aul(AM_awal: int, total_saham: int, notes: List[str]) -> Tuple[str, int]:
    """
    Putuskan Aul sesuai daftar valid. Jika tidak valid, kembalikan Adil + catatan peringatan.
    """
    if total_saham > AM_awal:
    # Semua Aul valid secara syar'i
        notes.append(f"Terjadi Aul: total saham {total_saham} > AM awal {AM_awal}")
        if AM_awal in VALID_AUL and total_saham in VALID_AUL[AM_awal]:
            notes.append(f"Aul ini adalah kasus klasik yang umum")
        notes.append(f"Ashlul Mas'alah diganti: dari {AM_awal} menjadi AM akhir {total_saham}")
        return "Aul", total_saham

# --------------------------
# RADD 3 skenario
# --------------------------
def _apply_radd(AM_awal: int,
                total_saham_dasar: int,
                furudh_items: List[schemas.FurudhItem],
                saham_map: Dict[int, int],
                notes: List[str]) -> Tuple[str, int, Dict[int, int]]:
    """
    Terapkan Radd sesuai kitab:
      1) Tanpa زوج/زوجة → AM akhir = total_saham.
      2) Ada زوج/زوجة dan hanya 1 ahli waris lain → AM akhir = penyebut زوج/زوجة, pasangan fix, sisa ke yang satu itu.
      3) Ada زوج/زوجة dan ahli waris lain ≥2 → AM akhir = penyebut زوج/زوجة,
         lalu ‘kelompok radd’ menerima sisa proporsional saham_dasar (dengan tashih inkisar jika perlu).
    """
    # pasangan?
    spouses = [f for f in furudh_items if _is_spouse(f.heir.id)]
    others  = [f for f in furudh_items if not _is_spouse(f.heir.id) and f.fraction != "Ashobah"]  # radd berlaku untuk dzawi al-furudh (bukan ashabah)

    if not spouses:
        # Radd tanpa pasangan
        notes.append(f"Radd tanpa زوج/زوجة: total saham {total_saham_dasar} dijadikan Ashlul Mas’alah → {total_saham_dasar}.")
        return "Radd", total_saham_dasar, saham_map

    # Ada pasangan
    spouse = spouses[0]
    spouse_den = spouse.denominator if spouse.denominator > 0 else AM_awal
    # saham pasangan fix pada AM spouse_den:
    spouse_saham_fix = (spouse_den // spouse.denominator) * spouse.numerator if spouse.denominator > 0 else 0

    if len(others) == 1:
        # pasangan + 1 ahli waris lain
        other = others[0]
        AM_akhir = spouse_den
        sisa = AM_akhir - spouse_saham_fix
        # tetapkan pasangan
        saham_map[spouse.heir.id] = spouse_saham_fix
        # sisa untuk yang satu itu
        saham_map[other.heir.id] = sisa
        notes.append(
            f"Radd dengan زوج/زوجة & satu penerima: penyebut زوج/زوجة = {spouse_den} dijadikan AM. "
            f"Bagian {spouse.heir.name_id} = {spouse_saham_fix}; sisa {sisa} diberikan seluruhnya kepada {other.heir.name_id}."
        )
        return "Radd", AM_akhir, saham_map

    # pasangan + banyak ahli
    AM_akhir = spouse_den
    sisa = AM_akhir - spouse_saham_fix
    saham_map[spouse.heir.id] = spouse_saham_fix

    # Hitung bobot radd proporsional dari saham_dasar (pakai saham dasar non-zero)
    radd_targets = [f for f in others if saham_map.get(f.heir.id, 0) > 0]
    sum_dasar = sum(saham_map.get(f.heir.id, 0) for f in radd_targets)

    if sum_dasar == 0:
        # jika tidak ada dasar (semua 0), bagi rata per kepala
        kepala = sum(f.quantity for f in radd_targets)
        # cek inkisar: sisa % kepala
        g = gcd(sisa, kepala)
        k = kepala // g
        if k > 1:
            AM_before = AM_akhir
            AM_akhir *= k
            spouse_saham_fix *= k
            sisa *= k
            saham_map[spouse.heir.id] = spouse_saham_fix
            notes.append(
                f"Radd (pasangan + banyak, bagi rata): sisa tidak habis oleh jumlah kepala {kepala} → tashīḥ ×{k}. "
                f"AM akhir: {AM_before} × {k} = {AM_akhir}"
            )
        # bagi rata per kepala
        for f in radd_targets:
            dasar = saham_map.get(f.heir.id, 0)
            if _is_group_two_thirds(f):
                dasar = dasar / f.quantity  # per-orang
            sum_dasar += dasar * f.quantity
        notes.append(f"Radd (pasangan + banyak): dibagi rata per kepala (kepala={kepala}).")
        return "Radd", AM_akhir, saham_map

    # proporsional sesuai saham dasar
    # cek inkisar: sisa % sum_dasar
    g = gcd(sisa, sum_dasar)
    k = sum_dasar // g
    if k > 1:
        AM_before = AM_akhir
        AM_akhir *= k
        spouse_saham_fix *= k
        sisa *= k
        # skala seluruh saham existing (termasuk pasangan yg sudah ditetapkan)
        for hid in list(saham_map.keys()):
            saham_map[hid] *= k
        notes.append(
            f"Radd (pasangan + banyak, proporsional): sisa tidak habis oleh jumlah dasar {sum_dasar} → tashīḥ ×{k}. "
            f"AM akhir: {AM_before} × {k} = {AM_akhir}"
        )

    for f in radd_targets:
        dasar = saham_map.get(f.heir.id, 0)
        bagian = (sisa * dasar) // sum_dasar
        saham_map[f.heir.id] = bagian

    notes.append(
        f"Radd (pasangan + banyak): sisa {sisa} dibagi proporsional dengan dasar {sum_dasar}."
    )
    return "Radd", AM_akhir, saham_map

# ============================================================
#                    FUNGSI UTAMA
# ============================================================
def calculate_inheritance(db: Session, calculation_input: schemas.CalculationInput) -> schemas.CalculationResult:
    heirs = calculation_input.heirs
    tirkah = calculation_input.tirkah

    notes: List[str] = []
    shares: List[schemas.HeirShare] = []

    # 1) Tentukan furudh
    notes.append("Menentukan furudh ahli waris sesuai ketentuan syar’i")
    furudh_items = determine_furudh(db, heirs)
    present_ids = {h.id for h in heirs}
    already_listed_ids = {f.heir.id for f in furudh_items}

    # 2) Ambil semua penyebut furudh untuk hitung Ashl
    denominators = [
        f.denominator for f in furudh_items
        if f.fraction != "Ashobah" and f.denominator > 0
    ]
    if not denominators:
        ashobah_items = [f for f in furudh_items if f.fraction == "Ashobah"]
        if ashobah_items:
            total_bobot = 0
            for f in ashobah_items:
                wpc = 2 if _is_male_asabah_id(f.heir.id) else 1
                total_bobot += wpc * f.quantity
            AM_awal = total_bobot
            ashl_info = schemas.AshlInfo(
                ashl_awal=AM_awal,
                ashl_akhir=AM_awal,
                comparisons=[],
                total_saham=AM_awal,  # TAMBAHKAN INI
                status="Adil"          # TAMBAHKAN INI
            )
            notes.append(f"Semua ahli waris adalah Ashobah → Ashlul Mas'alah = total bobot = {AM_awal}")
        else:
            ashl_info = schemas.AshlInfo(
                ashl_awal=1, 
                ashl_akhir=1, 
                comparisons=[],
                total_saham=0,  # TAMBAHKAN INI
                status="Adil"   # TAMBAHKAN INI
            )
    else:
        ashl_info = compute_ashl(denominators)
        AM_awal = ashl_info.ashl_awal
        ashl_info.ashl_akhir = AM_awal
        # Pastikan ashl_info dari compute_ashl juga punya field ini
        if not hasattr(ashl_info, 'total_saham'):
            ashl_info.total_saham = 0  # placeholder
        if not hasattr(ashl_info, 'status'):
            ashl_info.status = "Adil"  # placeholder
        notes.append(f"Menentukan Ashlul Mas'alah: {AM_awal}")

    # Catatan perbandingan penyebut (opsional: kalau compute_ashl mengembalikan)
    if getattr(ashl_info, "comparisons", None):
        for c in ashl_info.comparisons:
            notes.append(f"Penyebut {c.a} & {c.b} = {c.relation}")

    # 3) Hitung saham dasar non-Ashobah
    saham_map: Dict[int, int] = {}
    total_saham_dasar = 0

    for f in furudh_items:
        if f.fraction != "Ashobah":
            if _is_group_two_thirds(f):
                # BAGIAN GOLONGAN → tidak dikali quantity
                saham_golongan = (AM_awal // f.denominator) * f.numerator
                saham_per_orang = saham_golongan / f.quantity  # bisa pecahan
                saham_map[f.heir.id] = saham_golongan
                total_saham_dasar += saham_golongan
                notes.append(f"{f.heir.name_id}: {saham_golongan} saham karena 2/3 dari {AM_awal} (bagian golongan)")
            else:
                saham_per_unit = (AM_awal // f.denominator) * f.numerator
                saham_total_kel = saham_per_unit * f.quantity
                saham_map[f.heir.id] = saham_total_kel
                total_saham_dasar += saham_total_kel
                if f.quantity == 1:
                    notes.append(f"{f.heir.name_id}: {saham_per_unit} saham karena {f.fraction} dari {AM_awal}")
                else:
                    notes.append(f"{f.heir.name_id}: {saham_total_kel} saham karena {f.fraction} dari {AM_awal} (dibagi {f.quantity} orang)")
        else:
            saham_map[f.heir.id] = 0  # placeholder untuk Ashobah

    # 4) Hitung sisa dan distribusi Ashobah
    sisa = AM_awal - total_saham_dasar
    ashobah_items = [f for f in furudh_items if f.fraction == "Ashobah"]

    if ashobah_items and sisa > 0:
        tambahan = _distribute_ashobah_mixed(ashl_info, ashobah_items, sisa, saham_map, notes)
        total_saham_dasar += tambahan

    # 5) Status (Adil / Aul / Radd) — lalu inkisār umum
    if total_saham_dasar == AM_awal:
        status = "Adil"
        AM_akhir = AM_awal
        notes.append("Tidak terjadi perubahan, total saham = AM awal → masalah Adil")
    elif total_saham_dasar > AM_awal:
        status, AM_akhir = _maybe_apply_aul(AM_awal, total_saham_dasar, notes)
    else:
        # Radd
        status, AM_akhir, saham_map = _apply_radd(AM_awal, total_saham_dasar, furudh_items, saham_map, notes)

    # ==== Inkisār (tashīḥ bila perlu) ====
    AM_akhir = _apply_inkisar(AM_akhir, furudh_items, saham_map, notes)
    ashl_info.ashl_akhir = AM_akhir

    # total saham final setelah semua penyesuaian
    total_saham_final = sum(saham_map.values())

    # 6) Hitung nominal akhir + catatan rumus
    for f in furudh_items:
        saham_final = saham_map.get(f.heir.id, 0)
        uang_total = (saham_final / AM_akhir) * tirkah if AM_akhir else 0.0

        # Catatan informatif ala kitab
        if f.quantity == 1:
            notes.append(
                f"{f.heir.name_id} = {saham_final} × {tirkah:,.0f} ÷ {AM_akhir} = Rp {uang_total:,.0f}"
            )
        else:
            per_orang = uang_total / f.quantity if f.quantity else 0.0
            notes.append(
                f"{f.heir.name_id} ({f.quantity} orang) = {saham_final} × {tirkah:,.0f} ÷ {AM_akhir} = Rp {uang_total:,.0f} → masing-masing Rp {per_orang:,.0f}"
            )

        shares.append(
            schemas.HeirShare(
                heir=f.heir,
                quantity=f.quantity,
                share_fraction=f.fraction,
                saham=saham_final,
                reason=f.reason,
                share_amount=round(uang_total, 2),
            )
        )
    shares.extend(_append_mahjub_shares(db, heirs, furudh_items, notes))

    # 7) Return
    return schemas.CalculationResult(
        tirkah=tirkah,
        ashlul_masalah_awal=AM_awal,
        ashlul_masalah_akhir=AM_akhir,
        total_saham=total_saham_final,
        status=status,
        notes=notes,
        shares=shares,
    )

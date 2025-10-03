# calculator.py

from __future__ import annotations
from typing import List, Dict
from fractions import Fraction
from math import gcd

from sqlalchemy.orm import Session

import crud
import schemas
from app.rules.engine import determine_furudh
from app.math.ashl import compute_ashl
from app.special.router import apply_special_cases


# =========================
# Util kecil
# =========================
MALE_ASABAH_IDS = {1, 5, 2, 6, 7, 8, 10, 11, 12, 13, 14, 15}
FEMALE_ASABAH_IDS = {16, 17, 21, 22}

def _lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b) if a and b else 0

def _is_male_asabah_id(hid: int) -> bool:
    return hid in MALE_ASABAH_IDS

def _append_mahjub_shares(db: Session, heirs_input: List[schemas.Heir], furudh_items: List[schemas.FurudhItem], notes: List[str]) -> List[schemas.HeirShare]:
    """Tambahkan ke output: ahli waris yang hadir di request tapi mahjūb (tidak muncul di furudh_items)."""
    shares_mahjub: List[schemas.HeirShare] = []
    already_listed_ids = {f.heir.id for f in furudh_items}

    present_ids = {h.id for h in heirs_input}
    has_son_or_grandson = (1 in present_ids) or (5 in present_ids)
    has_father_or_grandfather = (2 in present_ids) or (6 in present_ids)

    def _get_heir_meta(hid: int) -> schemas.Heir:
        for f in furudh_items:
            if f.heir.id == hid:
                return f.heir
        meta = None
        if hasattr(crud, "get_heir_by_id"):
            meta = crud.get_heir_by_id(db, hid)
        else:
            rows = crud.get_heirs_by_ids(db, [hid])
            meta = rows[0] if rows else None
        if meta:
            return schemas.Heir(id=meta.id, name_id=meta.name_id, name_ar=meta.name_ar)
        return schemas.Heir(id=hid, name_id=f"ID {hid}", name_ar="-")

    for h in heirs_input:
        if h.id not in already_listed_ids:
            heir_meta = _get_heir_meta(h.id)
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


# =========================
# Distribusi Ashobah Campur 2:1 (umum)
# =========================
def _distribute_ashobah_mixed(ashobah_items: List[schemas.FurudhItem], sisa: int,
                              saham_map: Dict[int, int], notes: List[str]) -> None:
    """
    Bagi sisa untuk kelompok Ashobah campur (2:1). Lakukan tashīḥ jika perlu.
    """
    male_heads = sum(2 * f.quantity for f in ashobah_items if f.heir.id in MALE_ASABAH_IDS)
    female_heads = sum(1 * f.quantity for f in ashobah_items if f.heir.id in FEMALE_ASABAH_IDS)
    total_heads = male_heads + female_heads
    if total_heads <= 0 or sisa <= 0:
        return

    # Tashīḥ apabila sisa tidak habis oleh total_heads
    g = gcd(sisa, total_heads)
    k = total_heads // g  # faktor tashīḥ
    if k > 1:
        notes.append(f"Inkisār Ashobah: sisa = {sisa}, total bobot = {total_heads} → tashīḥ ×{k}.")
        # Caller harus mengalikan AM juga; di sini kita hanya bagi proporsional.
    # Distribusi proporsional (integer setelah tashīḥ)
    for f in ashobah_items:
        w = 2 if f.heir.id in MALE_ASABAH_IDS else 1
        bagian = (sisa * (w * f.quantity)) // total_heads
        saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + bagian
        if f.quantity > 1:
            notes.append(f"{f.heir.name_id} ({f.quantity} orang) mendapat {bagian} saham dari sisa (Ashobah 2:1).")
        else:
            notes.append(f"{f.heir.name_id} mendapat {bagian} saham dari sisa (Ashobah 2:1).")


# =========================
# AUL Valid (opsional – bila kamu pakai tabel valid)
# =========================
VALID_AUL = {
    6: [7, 8, 9, 10],
    12: [13, 15, 17],
    24: [27],
}
def _handle_aul(AM_awal: int, total_saham: int, notes: List[str]) -> int:
    if AM_awal in VALID_AUL and total_saham in VALID_AUL[AM_awal]:
        notes.append(f"Terjadi Aul: total saham {total_saham} > AM awal {AM_awal}. AM akhir = {total_saham}.")
        return total_saham
    return AM_awal


# =========================
# Fungsi Utama
# =========================
def calculate_inheritance(db: Session, calculation_input: schemas.CalculationInput) -> schemas.CalculationResult:
    heirs = calculation_input.heirs
    tirkah = calculation_input.tirkah

    notes: List[str] = []
    shares: List[schemas.HeirShare] = []

    # --- DEFAULT calc_mode
    calc_mode = {"mode": "normal"}

    # 1) Tentukan furudh
    notes.append("Menentukan furudh ahli waris sesuai ketentuan syar’i")
    furudh_items = determine_furudh(db, heirs)

    # 1b) Kasus-kasus khusus (Akdariyyah, al-‘Add, Jadd-Ikhwah)
    furudh_items, special_notes, calc_mode = apply_special_cases(db, heirs, furudh_items)
    notes.extend(special_notes)

    # 2) Ambil penyebut furudh
    denominators = [f.denominator for f in furudh_items if f.fraction != "Ashobah" and f.denominator > 0]
    ashl_info = compute_ashl(denominators)

    # ============================================================
    # CABANG: Tidak ada furudh tetap (denominators kosong)
    # ============================================================
    if not denominators:
        mode = calc_mode.get("mode", "normal")

        # ---------- MODE KHUSUS: Jadd ma‘al-Ikhwah ----------
        if mode == "jadd_ikhwah":
            notes.append("Kasus Jadd ma‘al-Ikhwah: membandingkan 3 opsi (muqāsamah, 1/3 sisa, 1/6 total).")

            # Kepala untuk muqāsamah: Jadd = 2, Ikhwah: lk=2, pr=1
            head_jadd = 2  # Jadd dihitung laki-laki
            male_sibs = sum(f.quantity for f in furudh_items if f.fraction == "Ashobah" and f.heir.id in {7, 8})
            female_sibs = sum(f.quantity for f in furudh_items if f.fraction == "Ashobah" and f.heir.id in {21, 22})
            head_sibs = 2 * male_sibs + 1 * female_sibs

            if head_sibs == 0:
                # tidak ada saudara → jadd ashabah penuh
                AM = head_jadd
                ashl_info = schemas.AshlInfo(ashl_awal=AM, ashl_akhir=AM, comparisons=[], total_saham=AM, status="Adil")
                saham_map: Dict[int, int] = {6: head_jadd}
                notes.append(f"Tidak ada saudara; Jadd menjadi Ashobah penuh. AM = {AM}.")
            else:
                # Bandingkan 3 opsi dengan porsi dari TOTAL (karena tidak ada fard)
                frac_muq = Fraction(head_jadd, head_jadd + head_sibs)  # porsi Jadd bila muqāsamah
                frac_1_3 = Fraction(1, 3)
                frac_1_6 = Fraction(1, 6)
                best = max([("muqasamah", frac_muq), ("one_third_resid", frac_1_3), ("one_sixth_total", frac_1_6)],
                           key=lambda x: x[1])

                saham_map = {}
                if best[0] == "muqasamah":
                    # AM = jumlah kepala (2:1)
                    AM = head_jadd + head_sibs
                    ashl_info = schemas.AshlInfo(ashl_awal=AM, ashl_akhir=AM, comparisons=[], total_saham=AM, status="Adil")
                    # Jadd
                    saham_map[6] = head_jadd
                    # Saudara (bobot 2:1)
                    for f in furudh_items:
                        if f.heir.id in {7, 8}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + 2 * f.quantity
                        if f.heir.id in {21, 22}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + 1 * f.quantity
                    notes.append(f"Memilih muqāsamah: Jadd {frac_muq} (> 1/3, > 1/6). AM = {AM} (jumlah kepala).")

                elif best[0] == "one_third_resid":
                    # Jadd = 1/3 total; saudara = 2/3 total proporsional 2:1
                    AM = _lcm(3, head_sibs) or 3 * head_sibs
                    jadd_shares = AM // 3
                    sib_total = AM - jadd_shares
                    per_head = sib_total // head_sibs

                    saham_map[6] = jadd_shares
                    for f in furudh_items:
                        if f.heir.id in {7, 8}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + (2 * f.quantity) * per_head
                        if f.heir.id in {21, 22}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + (1 * f.quantity) * per_head

                    ashl_info = schemas.AshlInfo(ashl_awal=AM, ashl_akhir=AM, comparisons=[], total_saham=AM, status="Adil")
                    notes.append(f"Memilih 1/3 sisa: AM ditashīḥ menjadi {AM} agar bulat.")

                else:  # "one_sixth_total"
                    AM = _lcm(6, head_sibs) or 6 * head_sibs
                    jadd_shares = AM // 6
                    sib_total = AM - jadd_shares
                    per_head = sib_total // head_sibs

                    saham_map[6] = jadd_shares
                    for f in furudh_items:
                        if f.heir.id in {7, 8}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + (2 * f.quantity) * per_head
                        if f.heir.id in {21, 22}:
                            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + (1 * f.quantity) * per_head

                    ashl_info = schemas.AshlInfo(ashl_awal=AM, ashl_akhir=AM, comparisons=[], total_saham=AM, status="Adil")
                    notes.append(f"Memilih 1/6 total: AM ditashīḥ menjadi {AM} agar bulat.")

            # ---- Bangun output final dari saham_map + AM ----
            total_saham = sum(saham_map.values())
            for f in furudh_items:
                if f.heir.id in saham_map:
                    saham = saham_map[f.heir.id]
                    amount = (saham / ashl_info.ashl_akhir) * tirkah
                    if f.quantity == 1:
                        notes.append(f"{f.heir.name_id} = {saham} × {tirkah:,.0f} ÷ {ashl_info.ashl_akhir} = Rp {amount:,.0f}")
                    else:
                        per_orang = amount / f.quantity
                        notes.append(f"{f.heir.name_id} ({f.quantity} orang) = {saham} × {tirkah:,.0f} ÷ {ashl_info.ashl_akhir} = Rp {amount:,.0f} → masing-masing Rp {per_orang:,.0f}")
                    shares.append(schemas.HeirShare(
                        heir=f.heir, quantity=f.quantity, share_fraction="Ashobah",
                        saham=saham, reason=f.reason, share_amount=round(amount, 2)
                    ))

            # tampilkan mahjūb (mis. ukht seayah yang akhirnya 0 karena hijāb)
            shares.extend(_append_mahjub_shares(db, heirs, furudh_items, notes))

            return schemas.CalculationResult(
                tirkah=tirkah,
                ashlul_masalah_awal=ashl_info.ashl_awal,
                ashlul_masalah_akhir=ashl_info.ashl_akhir,
                total_saham=total_saham,
                status="Adil",
                notes=notes,
                shares=shares
            )

        # ---------- MODE NORMAL: Semua Ashobah ----------
        all_ashabah = all(f.fraction == "Ashobah" for f in furudh_items)
        if all_ashabah:
            # bobot: kalau CAMPUR (ada perempuan) → lk=2, pr=1; kalau SEMUA laki-laki → bobot=1 per orang
            any_female = any(f.heir.id in FEMALE_ASABAH_IDS for f in furudh_items)
            saham_map: Dict[int, int] = {}
            total_bobot = 0
            for f in furudh_items:
                if any_female:
                    wpc = 2 if _is_male_asabah_id(f.heir.id) else 1
                else:
                    wpc = 1  # semua laki-laki → 1 per orang
                saham = wpc * f.quantity
                saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + saham
                total_bobot += saham

            AM = total_bobot
            ashl_info = schemas.AshlInfo(ashl_awal=AM, ashl_akhir=AM, comparisons=[], total_saham=AM, status="Adil")
            notes.append(f"Semua ahli waris adalah Ashobah → Ashlul Mas'alah = total bobot = {AM}")

            for f in furudh_items:
                saham = saham_map[f.heir.id]
                amount = (saham / AM) * tirkah
                if f.quantity == 1:
                    notes.append(f"{f.heir.name_id} = {saham} × {tirkah:,.0f} ÷ {AM} = Rp {amount:,.0f}")
                else:
                    per_orang = amount / f.quantity
                    notes.append(f"{f.heir.name_id} ({f.quantity} orang) = {saham} × {tirkah:,.0f} ÷ {AM} = Rp {amount:,.0f} → masing-masing Rp {per_orang:,.0f}")
                shares.append(schemas.HeirShare(
                    heir=f.heir, quantity=f.quantity, share_fraction="Ashobah",
                    saham=saham, reason=f.reason, share_amount=round(amount, 2)
                ))

            shares.extend(_append_mahjub_shares(db, heirs, furudh_items, notes))

            return schemas.CalculationResult(
                tirkah=tirkah,
                ashlul_masalah_awal=AM,
                ashlul_masalah_akhir=AM,
                total_saham=AM,
                status="Adil",
                notes=notes,
                shares=shares
            )

        # (kalau tidak masuk dua cabang di atas, jatuh ke alur umum di bawah)

    # ============================================================
    # CABANG UMUM: Ada furudh tetap → hitung AM, saham furudh, sisa, dst.
    # ============================================================
    AM_awal = ashl_info.ashl_awal
    notes.append(f"Menentukan Ashlul Mas’alah: {AM_awal}")

    # Tambahkan perbandingan antar penyebut (kalau ada)
    for c in ashl_info.comparisons:
        notes.append(f"Penyebut {c.a} & {c.b} = {c.relation}")

    # 3) Hitung saham furudh (non-Ashobah)
    saham_map: Dict[int, int] = {}
    total_saham_furudh = 0
    ashobah_items: List[schemas.FurudhItem] = []

    for f in furudh_items:
        if f.fraction != "Ashobah":
            saham_per_orang = (AM_awal // f.denominator) * f.numerator
            saham_total = saham_per_orang * f.quantity
            saham_map[f.heir.id] = saham_map.get(f.heir.id, 0) + saham_total
            total_saham_furudh += saham_total
            if f.quantity == 1:
                notes.append(f"{f.heir.name_id}: {saham_per_orang} saham karena {f.fraction} dari {AM_awal}")
            else:
                notes.append(f"{f.heir.name_id}: {saham_total} saham karena {f.fraction} (kelompok) dari {AM_awal}")
        else:
            ashobah_items.append(f)

    # 4) Hitung sisa untuk Ashobah (kalau ada)
    sisa = AM_awal - total_saham_furudh
    AM_akhir = AM_awal

    if ashobah_items and sisa > 0:
        if len(ashobah_items) == 1:
            # 1 Ashobah → ambil semua sisa
            sole = ashobah_items[0]
            saham_map[sole.heir.id] = saham_map.get(sole.heir.id, 0) + sisa
            notes.append(f"{sole.heir.name_id} mendapat sisa {sisa} saham sebagai Ashobah")
        else:
            # Ashobah campur 2:1
            # Jika sisa tidak habis terhadap bobot, lakukan tashīḥ (mengubah AM)
            male_heads = sum(2 * f.quantity for f in ashobah_items if f.heir.id in MALE_ASABAH_IDS)
            female_heads = sum(1 * f.quantity for f in ashobah_items if f.heir.id in FEMALE_ASABAH_IDS)
            total_heads = male_heads + female_heads
            if total_heads > 0 and sisa % total_heads != 0:
                k = total_heads // gcd(sisa, total_heads)
                notes.append(f"Inkisār Ashobah: sisa = {sisa}, total bobot = {total_heads} → tashīḥ ×{k}. AM akhir: {AM_akhir} × {k} = {AM_akhir * k}")
                # skala saham furudh yang sudah ada
                for hid in list(saham_map.keys()):
                    saham_map[hid] *= k
                sisa *= k
                AM_akhir *= k
            # distribusi
            _distribute_ashobah_mixed(ashobah_items, sisa, saham_map, notes)

    # 5) Tentukan status (Adil/Aul/Radd)
    total_saham_final = sum(saham_map.values())
    status = "Adil"
    if total_saham_final > AM_akhir:
        # Aul hanya kalau ada di tabel valid
        new_AM = _handle_aul(AM_akhir, total_saham_final, notes)
        if new_AM != AM_akhir:
            AM_akhir = new_AM
            status = "Aul"
        else:
            # jika tidak valid, anggap adil (sesuai permintaan sebelumnya)
            notes.append(f"⚠️ Total saham {total_saham_final} tidak sesuai daftar Aul untuk AM {AM_akhir} → dianggap Adil (AM tetap).")
            status = "Adil"
    elif total_saham_final < AM_akhir:
        # Radd sederhana: AM akhir = total_saham_final, kecuali ada pasangan + pola khusus (sudah kamu buat di modul radd)
        status = "Radd"
        AM_akhir = total_saham_final
        notes.append(f"Terjadi Radd: total saham {total_saham_final} < AM awal {ashl_info.ashl_awal}. AM akhir: {AM_akhir}")

    # 6) Hitung nominal akhir + catatan rumus
    for f in furudh_items:
        saham_final = saham_map.get(f.heir.id, 0)
        amount = (saham_final / AM_akhir) * tirkah if AM_akhir else 0.0
        if f.quantity == 1:
            notes.append(f"{f.heir.name_id} = {saham_final} × {tirkah:,.0f} ÷ {AM_akhir} = Rp {amount:,.0f}")
        else:
            per_orang = (amount / f.quantity) if f.quantity else 0.0
            notes.append(f"{f.heir.name_id} ({f.quantity} orang) = {saham_final} × {tirkah:,.0f} ÷ {AM_akhir} = Rp {amount:,.0f} → masing-masing Rp {per_orang:,.0f}")
        shares.append(
            schemas.HeirShare(
                heir=f.heir,
                quantity=f.quantity,
                share_fraction=f.fraction,
                saham=saham_final,
                reason=f.reason,
                share_amount=round(amount, 2)
            )
        )

    # 7) Tambahkan mahjūb (supaya transparan)
    shares.extend(_append_mahjub_shares(db, heirs, furudh_items, notes))

    # 8) Return
    return schemas.CalculationResult(
        tirkah=tirkah,
        ashlul_masalah_awal=ashl_info.ashl_awal,
        ashlul_masalah_akhir=AM_akhir,
        total_saham=sum(saham_map.values()),
        status=status,
        notes=notes,
        shares=shares
    )

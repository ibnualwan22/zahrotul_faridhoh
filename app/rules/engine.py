# app/rules/engine.py

from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from schemas import FurudhItem, Heir

# =========================
# Util kuantitas & eksistensi
# =========================
def _q(heirs_input: List[Heir], target_id: int) -> int:
    for h in heirs_input:
        if h.id == target_id:
            return h.quantity
    return 0

def _exists(heirs_input: List[Heir], target_id: int) -> bool:
    return _q(heirs_input, target_id) > 0


# =========================
# Pemetaan ID (sinkron DB)
# =========================
ID = {
    "IBN": 1,                    # Anak Laki-laki
    "AB": 2,                     # Ayah
    "ZAWJ": 3,                   # Suami
    "ZAWJAH": 4,                 # Istri
    "IBN_IBN": 5,                # Cucu Laki-laki (dari anak laki-laki)
    "JADD": 6,                   # Kakek
    "AKH_ABAWAYN": 7,            # Saudara Laki-laki Kandung
    "AKH_AB": 8,                 # Saudara Laki-laki Seayah
    "AKH_UMM": 9,                # Saudara Laki-laki Seibu
    "IBN_AKH_ABAWAYN": 10,       # Keponakan Laki-laki (dari sdr lk kandung)
    "IBN_AKH_AB": 11,            # Keponakan Laki-laki (dari sdr lk seayah)
    "AMM_ABAWAYN": 12,           # Paman Kandung
    "AMM_AB": 13,                # Paman Seayah
    "IBN_AMM_ABAWAYN": 14,       # Sepupu Laki-laki (dari paman kandung)
    "IBN_AMM_AB": 15,            # Sepupu Laki-laki (dari paman seayah)
    "BINT": 16,                  # Anak Perempuan
    "BINT_IBN": 17,              # Cucu Perempuan (dari anak laki-laki)
    "UMM": 18,                   # Ibu
    "JADDAH_MIN_ALUMM": 19,      # Nenek dari Ibu
    "JADDAH_MIN_ALAB": 20,       # Nenek dari Ayah
    "UKHT_ABAWAYN": 21,          # Saudari Kandung
    "UKHT_AB": 22,               # Saudari Seayah
    "UKHT_UMM": 23,              # Saudari Seibu
    "MUTIQ": 24,                 # Pria Pembebas Budak
    "MUTIQAH": 25,               # Wanita Pembebas Budak
}

# =========================
# Helper buat FurudhItem
# =========================
def _fi(id_, name_id, name_ar, quantity, fraction, num, den, reason) -> FurudhItem:
    return FurudhItem(
        heir=Heir(id=id_, name_id=name_id, name_ar=name_ar),
        quantity=quantity,
        fraction=fraction,
        numerator=num,
        denominator=den,
        reason=reason,
    )

def _asabah(id_, name_id, name_ar, quantity, reason="Ashobah") -> FurudhItem:
    return FurudhItem(
        heir=Heir(id=id_, name_id=name_id, name_ar=name_ar),
        quantity=quantity,
        fraction="Ashobah",
        numerator=0,
        denominator=1,
        reason=reason,
    )

# =========================
# Predikat penghalang (hājib)
# =========================
def _has_any_children(heirs_input: List[Heir]) -> bool:
    return any([
        _exists(heirs_input, ID["IBN"]),
        _exists(heirs_input, ID["BINT"]),
        _exists(heirs_input, ID["IBN_IBN"]),
        _exists(heirs_input, ID["BINT_IBN"]),
    ])

def _blocked_ikhwah(heirs_input: List[Heir]) -> bool:
    """Ikhwah gugur karena ada anak laki-laki/cucu laki-laki/ayah/kakek."""
    return any([
        _exists(heirs_input, ID["IBN"]),
        _exists(heirs_input, ID["IBN_IBN"]),
        _exists(heirs_input, ID["AB"]),
        _exists(heirs_input, ID["JADD"]),
    ])

def _has_male_agnate(heirs_input: List[Heir]) -> bool:
    """Ada ‘ashabah laki-laki (tingkat atas) yg membuat ukht tidak dapat furūḍ."""
    return any([
        _exists(heirs_input, ID["IBN"]),
        _exists(heirs_input, ID["IBN_IBN"]),
        _exists(heirs_input, ID["AB"]),
        _exists(heirs_input, ID["JADD"]),
        _exists(heirs_input, ID["AKH_ABAWAYN"]),
        _exists(heirs_input, ID["AKH_AB"]),
        _exists(heirs_input, ID["IBN_AKH_ABAWAYN"]),
        _exists(heirs_input, ID["IBN_AKH_AB"]),
        _exists(heirs_input, ID["AMM_ABAWAYN"]),
        _exists(heirs_input, ID["AMM_AB"]),
        _exists(heirs_input, ID["IBN_AMM_ABAWAYN"]),
        _exists(heirs_input, ID["IBN_AMM_AB"]),
    ])

# =========================
# Mesin penentu furūḍ
# =========================
def determine_furudh(db: Session, heirs_input: List[Heir]) -> List[FurudhItem]:
    """
    Menghasilkan daftar FurudhItem (furūḍ & ‘ashabah) sesuai ringkasan Zahrotul Faridhah.
    Catatan:
      - Furūḍ jama’i (2/3) TIDAK mengalikan penyebut dg jumlah orang (hindari bug inkisār).
      - Inkisār, Aul, Radd ditangani di calculator.py.
    """
    items: List[FurudhItem] = []

    q = lambda k: _q(heirs_input, k)
    has_child_any = _has_any_children(heirs_input)
    blocked_ikhwah = _blocked_ikhwah(heirs_input)
    has_father = _exists(heirs_input, ID["AB"])
    has_gf = _exists(heirs_input, ID["JADD"])
    has_father_or_gf = has_father or has_gf

    # -----------------------
    # 1) Suami / Istri
    # -----------------------
    if q(ID["ZAWJ"]) > 0:
        if has_child_any:
            items.append(_fi(ID["ZAWJ"], "Suami", "زوج", q(ID["ZAWJ"]), "1/4", 1, 4,
                             "Suami mendapat 1/4 karena pewaris punya anak/cucu"))
        else:
            items.append(_fi(ID["ZAWJ"], "Suami", "زوج", q(ID["ZAWJ"]), "1/2", 1, 2,
                             "Suami mendapat 1/2 karena pewaris tidak punya anak/cucu"))

    if q(ID["ZAWJAH"]) > 0:
        if has_child_any:
            items.append(_fi(ID["ZAWJAH"], "Istri", "زوجة", q(ID["ZAWJAH"]), "1/8", 1, 8,
                             "Istri mendapat 1/8 karena pewaris punya anak/cucu"))
        else:
            items.append(_fi(ID["ZAWJAH"], "Istri", "زوجة", q(ID["ZAWJAH"]), "1/4", 1, 4,
                             "Istri mendapat 1/4 karena pewaris tidak punya anak/cucu"))

    # -----------------------
    # 2) Ibu
    # -----------------------
    siblings_any = (
        q(ID["AKH_ABAWAYN"]) + q(ID["AKH_AB"]) + q(ID["AKH_UMM"]) +
        q(ID["UKHT_ABAWAYN"]) + q(ID["UKHT_AB"]) + q(ID["UKHT_UMM"])
    )
    if q(ID["UMM"]) > 0:
        if has_child_any or siblings_any >= 2:
            items.append(_fi(ID["UMM"], "Ibu", "أم", q(ID["UMM"]), "1/6", 1, 6,
                             "Ibu mendapat 1/6 karena ada keturunan atau ≥2 saudara"))
        else:
            items.append(_fi(ID["UMM"], "Ibu", "أم", q(ID["UMM"]), "1/3", 1, 3,
                             "Ibu mendapat 1/3 karena tanpa keturunan & <2 saudara"))

    # -----------------------
    # 3) Ayah / Kakek
    # -----------------------
    if q(ID["AB"]) > 0:
        if has_child_any:
            items.append(_fi(ID["AB"], "Ayah", "أب", q(ID["AB"]), "1/6", 1, 6,
                             "Ayah mendapat 1/6 karena ada keturunan; sisanya sebagai Ashobah."))
        else:
            items.append(_asabah(ID["AB"], "Ayah", "أب", q(ID["AB"]),
                                 "Ayah menjadi Ashobah karena tanpa keturunan."))
    elif q(ID["JADD"]) > 0:
        # Aturan jadd ma‘al ikhwah detail → ditangani di kalkulator karena perlu.
        if has_child_any:
            items.append(_fi(ID["JADD"], "Kakek", "جد", q(ID["JADD"]), "1/6", 1, 6,
                             "Kakek mendapat 1/6 karena ada keturunan; sisanya sebagai Ashobah."))
        else:
            items.append(_asabah(ID["JADD"], "Kakek", "جد", q(ID["JADD"]),
                                 "Kakek menjadi Ashobah karena tanpa keturunan."))

    # -----------------------
    # 4) Nenek (terhalang oleh Ibu)
    # -----------------------
    if q(ID["UMM"]) == 0:
        if q(ID["JADDAH_MIN_ALUMM"]) > 0:
            items.append(_fi(ID["JADDAH_MIN_ALUMM"], "Nenek dari Ibu", "جدة من الأم",
                             q(ID["JADDAH_MIN_ALUMM"]), "1/6", 1, 6,
                             "Nenek (pihak ibu) 1/6 karena Ibu tiada dan tanpa penghalang."))
        if q(ID["JADDAH_MIN_ALAB"]) > 0 and not has_father:
            items.append(_fi(ID["JADDAH_MIN_ALAB"], "Nenek dari Ayah", "جدة من الأب",
                             q(ID["JADDAH_MIN_ALAB"]), "1/6", 1, 6,
                             "Nenek (pihak ayah) 1/6 karena Ibu/Ayah tiada dan tanpa penghalang."))

    # -----------------------
    # 5) Anak & Cucu (dari anak laki-laki)
    # -----------------------
    if q(ID["IBN"]) > 0:
        # Anak laki-laki → Ashobah
        items.append(_asabah(ID["IBN"], "Anak Laki-laki", "ابن", q(ID["IBN"]),
                             "Anak laki-laki menjadi Ashobah (mengambil sisa)."))
        # Anak perempuan bersama anak laki-laki → asabah bil-ghair (2:1)
        if q(ID["BINT"]) > 0:
            items.append(_asabah(ID["BINT"], "Anak Perempuan", "بنت", q(ID["BINT"]),
                                 "Anak perempuan bersama anak laki-laki: Ashobah bil-ghair (2:1)."))
        # Cucu (lk/pr) dari anak lk tertutup oleh anak lk
    else:
        # Tidak ada anak laki-laki
        if q(ID["BINT"]) == 1:
            items.append(_fi(ID["BINT"], "Anak Perempuan", "بنت", 1, "1/2", 1, 2,
                             "Anak perempuan tunggal 1/2 karena tanpa anak laki-laki."))
        elif q(ID["BINT"]) >= 2:
            n = q(ID["BINT"])
            items.append(_fi(ID["BINT"], "Anak Perempuan", "بنت", n, "2/3", 2, 3,
                             "≥2 anak perempuan mendapat 2/3 bersama, dibagi rata."))

        # Cucu dari anak laki-laki (karena tidak ada anak)
        if q(ID["IBN_IBN"]) > 0:
            items.append(_asabah(ID["IBN_IBN"], "Cucu Laki-laki", "ابن ابن", q(ID["IBN_IBN"]),
                                 "Cucu laki-laki menjadi Ashobah karena tidak ada anak."))
        if q(ID["BINT_IBN"]) > 0 and q(ID["IBN_IBN"]) == 0:
            if q(ID["BINT"]) == 0:
                if q(ID["BINT_IBN"]) == 1:
                    items.append(_fi(ID["BINT_IBN"], "Cucu Perempuan", "بنت ابن", 1, "1/2", 1, 2,
                                     "Cucu perempuan tunggal 1/2 karena tanpa anak/cucu lk."))
                else:
                    n = q(ID["BINT_IBN"])
                    items.append(_fi(ID["BINT_IBN"], "Cucu Perempuan", "بنت ابن", n, "2/3", 2, 3,
                                     "≥2 cucu perempuan 2/3 bersama karena tanpa anak/cucu lk."))
            else:
                # Tamām al-ṯuluthayn (menyempurnakan 2/3)
                items.append(_fi(ID["BINT_IBN"], "Cucu Perempuan", "بنت ابن", q(ID["BINT_IBN"]),
                                 "1/6", 1, 6,
                                 "Cucu perempuan mendapat 1/6 untuk menyempurnakan 2/3 bersama anak perempuan."))

    # -----------------------
    # 6) Saudara seibu (li-umm) – lintas gender, rata bagi
    #     Syarat: tanpa keturunan & tanpa ayah/kakek
    # -----------------------
    total_li_umm = q(ID["AKH_UMM"]) + q(ID["UKHT_UMM"])
    if total_li_umm > 0 and (not has_child_any) and (not has_father_or_gf):
        if total_li_umm == 1:
            if q(ID["AKH_UMM"]) == 1:
                items.append(_fi(ID["AKH_UMM"], "Saudara Laki-laki Seibu", "أخ لأم", 1, "1/6", 1, 6,
                                 "Saudara seibu (1 orang) mendapat 1/6 karena tanpa keturunan & ayah/kakek."))
            else:
                items.append(_fi(ID["UKHT_UMM"], "Saudari Seibu", "أخت لأم", 1, "1/6", 1, 6,
                                 "Saudara seibu (1 orang) mendapat 1/6 karena tanpa keturunan & ayah/kakek."))
        else:
            # 1/3 bersama → per-orang 1/(3×total), ini memudahkan pembagian rata,
            # dan tidak akan bentrok dengan kasus “saudara se-bapak 5” karena itu kelompok berbeda (asabah)
            den = 3 * total_li_umm
            if q(ID["AKH_UMM"]) > 0:
                items.append(_fi(ID["AKH_UMM"], "Saudara Laki-laki Seibu", "أخ لأم",
                                 q(ID["AKH_UMM"]), f"1/{den}", 1, den,
                                 "Saudara seibu (≥2) mendapat 1/3 bersama, dibagi rata lintas gender."))
            if q(ID["UKHT_UMM"]) > 0:
                items.append(_fi(ID["UKHT_UMM"], "Saudari Seibu", "أخت لأم",
                                 q(ID["UKHT_UMM"]), f"1/{den}", 1, den,
                                 "Saudara seibu (≥2) mendapat 1/3 bersama, dibagi rata lintas gender."))

    # -----------------------
    # 7) Saudari kandung / seayah (furūḍ atau ta‘sīb)
    #     Gugur karena ada anak lk / cucu lk / ayah / kakek
    # -----------------------
    if not blocked_ikhwah:
    # =====================================================
    # 7a) SAUDARI KANDUNG (UKHT_ABAWAYN)
    #     - Dapat furudh (1/2 atau 2/3) bila TIDAK ada male agnate
    #     - Menjadi 'asabah ma'a al-ghair bila ada anak/cucu perempuan
    #     - Bila ada saudara lk kandung, saudari ikut 'asabah (2:1)
    # =====================================================
        if q(ID["UKHT_ABAWAYN"]) > 0 and not _has_male_agnate(heirs_input):
            # Furudh (tanpa anak/ayah/kakek & tanpa male agnate)
            if q(ID["UKHT_ABAWAYN"]) == 1 and q(ID["BINT"]) == 0 and q(ID["BINT_IBN"]) == 0:
                items.append(_fi(
                    ID["UKHT_ABAWAYN"], "Saudari Kandung", "أخت لأبوين", 1,
                    "1/2", 1, 2,
                    "Saudari kandung tunggal 1/2 bila tanpa keturunan & ayah/kakek."
                ))
            elif q(ID["UKHT_ABAWAYN"]) >= 2 and q(ID["BINT"]) == 0 and q(ID["BINT_IBN"]) == 0:
                n = q(ID["UKHT_ABAWAYN"])
                items.append(_fi(
                    ID["UKHT_ABAWAYN"], "Saudari Kandung", "أخت لأبوين", n,
                    "2/3", 2, 3,
                    "≥2 saudari kandung 2/3 bersama bila tanpa keturunan & ayah/kakek."
                ))
            # Ta'sib ma'a al-ghair (ada anak/cucu perempuan)
            if q(ID["BINT"]) > 0 or q(ID["BINT_IBN"]) > 0:
                items.append(_asabah(
                    ID["UKHT_ABAWAYN"], "Saudari Kandung", "أخت لأبوين", q(ID["UKHT_ABAWAYN"]),
                    "Saudari kandung bersama anak/cucu perempuan: Ashobah ma‘a al-ghair."
                ))

        # =====================================================
        # 7b) SAUDARA LAKI-LAKI KANDUNG (AKH_ABAWAYN) → 'ASABAH
        #     Syarat: tanpa anak lk/cucu lk & tanpa ayah/kakek
        #     PATCH: jika ada UKHT_ABAWAYN juga, mereka ikut 'asabah (2:1)
        # =====================================================
        if q(ID["AKH_ABAWAYN"]) > 0 and (q(ID["IBN"]) == 0 and q(ID["IBN_IBN"]) == 0 and not has_father_or_gf):
            items.append(_asabah(
                ID["AKH_ABAWAYN"], "Saudara Laki-laki Kandung", "أخ لأبوين", q(ID["AKH_ABAWAYN"]),
                "Saudara laki-laki kandung menjadi Ashobah bila tanpa keturunan & ayah/kakek."
            ))
            # >>> PATCH: saudari kandung ikut asabah bersama saudara lk kandung (2:1)
            if q(ID["UKHT_ABAWAYN"]) > 0:
                items.append(_asabah(
                    ID["UKHT_ABAWAYN"], "Saudari Kandung", "أخت لأبوين", q(ID["UKHT_ABAWAYN"]),
                    "Saudari kandung bersama saudara laki-laki kandung: Ashobah ma‘a al-ākh (2:1)."
                ))

        # =====================================================
        # 7c) SAUDARI SEAYAH (UKHT_AB) 
        #     - Dapat furudh bila TIDAK ada male agnate & TIDAK ada saudari kandung
        #     - Menjadi 'asabah ma'a al-ghair bila ada anak/cucu perempuan
        # =====================================================
        if q(ID["UKHT_AB"]) > 0 and not _has_male_agnate(heirs_input) and q(ID["UKHT_ABAWAYN"]) == 0:
            if q(ID["UKHT_AB"]) == 1 and q(ID["BINT"]) == 0 and q(ID["BINT_IBN"]) == 0:
                items.append(_fi(
                    ID["UKHT_AB"], "Saudari Seayah", "أخت لأب", 1,
                    "1/2", 1, 2,
                    "Saudari seayah tunggal 1/2 bila tanpa keturunan & ayah/kakek serta tanpa saudari kandung."
                ))
            elif q(ID["UKHT_AB"]) >= 2 and q(ID["BINT"]) == 0 and q(ID["BINT_IBN"]) == 0:
                n = q(ID["UKHT_AB"])
                items.append(_fi(
                    ID["UKHT_AB"], "Saudari Seayah", "أخت لأب", n,
                    "2/3", 2, 3,
                    "≥2 saudari seayah 2/3 bersama bila tanpa keturunan & ayah/kakek serta tanpa saudari kandung."
                ))
            if q(ID["BINT"]) > 0 or q(ID["BINT_IBN"]) > 0:
                items.append(_asabah(
                    ID["UKHT_AB"], "Saudari Seayah", "أخت لأب", q(ID["UKHT_AB"]),
                    "Saudari seayah bersama anak/cucu perempuan: Ashobah ma‘a al-ghair."
                ))

        # =====================================================
        # 7d) SAUDARA LAKI-LAKI SEAYAH (AKH_AB) → 'ASABAH
        #     Syarat: tanpa anak lk/cucu lk & tanpa ayah/kakek
        #     PATCH: jika ada UKHT_AB juga, mereka ikut 'asabah (2:1)
        # =====================================================
        if q(ID["AKH_AB"]) > 0 and (q(ID["IBN"]) == 0 and q(ID["IBN_IBN"]) == 0 and not has_father_or_gf):
            items.append(_asabah(
                ID["AKH_AB"], "Saudara Laki-laki Seayah", "أخ لأب", q(ID["AKH_AB"]),
                "Saudara laki-laki seayah menjadi Ashobah bila tanpa keturunan & ayah/kakek."
            ))
            # >>> PATCH: saudari seayah ikut asabah bersama saudara lk seayah (2:1)
            if q(ID["UKHT_AB"]) > 0:
                items.append(_asabah(
                    ID["UKHT_AB"], "Saudari Seayah", "أخت لأب", q(ID["UKHT_AB"]),
                    "Saudari seayah bersama saudara laki-laki seayah: Ashobah ma‘a al-ākh (2:1)."
                ))


    # -----------------------
    # 8) ‘Ashabah bertingkat (keponakan → paman → sepupu)
    #     hanya karena tidak ada agnate di atas
    # -----------------------
    if not _has_male_agnate(heirs_input):
        if q(ID["IBN_AKH_ABAWAYN"]) > 0:
            items.append(_asabah(ID["IBN_AKH_ABAWAYN"], "Keponakan Laki-laki (dari Sdr Lk Kandung)", "ابن أخ لأبوين",
                                 q(ID["IBN_AKH_ABAWAYN"]),
                                 "Keponakan (dari sdr lk kandung) menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))
        elif q(ID["IBN_AKH_AB"]) > 0:
            items.append(_asabah(ID["IBN_AKH_AB"], "Keponakan Laki-laki (dari Sdr Lk Seayah)", "ابن أخ لأب",
                                 q(ID["IBN_AKH_AB"]),
                                 "Keponakan (dari sdr lk seayah) menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))
        elif q(ID["AMM_ABAWAYN"]) > 0:
            items.append(_asabah(ID["AMM_ABAWAYN"], "Paman Kandung", "عم لأبوين", q(ID["AMM_ABAWAYN"]),
                                 "Paman kandung menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))
        elif q(ID["AMM_AB"]) > 0:
            items.append(_asabah(ID["AMM_AB"], "Paman Seayah", "عم لأب", q(ID["AMM_AB"]),
                                 "Paman seayah menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))
        elif q(ID["IBN_AMM_ABAWAYN"]) > 0:
            items.append(_asabah(ID["IBN_AMM_ABAWAYN"], "Sepupu Laki-laki (dari Paman Kandung)", "ابن عم لأبوين",
                                 q(ID["IBN_AMM_ABAWAYN"]),
                                 "Sepupu (dari paman kandung) menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))
        elif q(ID["IBN_AMM_AB"]) > 0:
            items.append(_asabah(ID["IBN_AMM_AB"], "Sepupu Laki-laki (dari Paman Seayah)", "ابن عم لأب",
                                 q(ID["IBN_AMM_AB"]),
                                 "Sepupu (dari paman seayah) menjadi Ashobah karena tidak ada ‘ashabah di atasnya."))

    # -----------------------
    # 9) Wala’ (muta‘tiq/mu‘tiqah) → last resort
    # -----------------------
    if not items:
        if q(ID["MUTIQ"]) > 0:
            items.append(_asabah(ID["MUTIQ"], "Pria Pembebas Budak", "معتق", q(ID["MUTIQ"]),
                                 "Wala’ (pria pembebas budak) mewarisi karena tidak ada dzawi al-furudh & ‘ashobah nasab."))
        elif q(ID["MUTIQAH"]) > 0:
            items.append(_asabah(ID["MUTIQAH"], "Wanita Pembebas Budak", "معتقة", q(ID["MUTIQAH"]),
                                 "Wala’ (wanita pembebas budak) mewarisi karena tidak ada dzawi al-furudh & ‘ashobah nasab."))

    return items

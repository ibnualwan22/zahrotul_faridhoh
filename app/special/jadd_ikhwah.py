# app/special/jadd_ikhwah.py
from typing import List, Tuple, Dict
from schemas import Heir, FurudhItem

ID = { "JADD": 6, "AKH_ABAWAYN": 7, "UKHT_ABAWAYN": 21, "AKH_AB": 8, "UKHT_AB": 22 }

def _q(heirs: List[Heir], i: int) -> int:
    return next((h.quantity for h in heirs if h.id == i), 0)

def is_jadd_ikhwah(heirs: List[Heir]) -> bool:
    has_jadd = _q(heirs, ID["JADD"]) > 0
    has_ikhwah = (_q(heirs, ID["AKH_ABAWAYN"]) + _q(heirs, ID["UKHT_ABAWAYN"]) +
                  _q(heirs, ID["AKH_AB"])      + _q(heirs, ID["UKHT_AB"])) > 0
    no_father = _q(heirs, 2) == 0
    no_kids   = all(_q(heirs, i) == 0 for i in [1,16,5,17])
    return has_jadd and has_ikhwah and no_father and no_kids

def compute_choice_for_jadd(sisa: int, tirkah_am: int, headcount_male: int, headcount_female: int) -> Tuple[str, Dict]:
    """
    sisa = sisa saham/AM (bukan rupiah) yang akan dibagi di tahap saham.
    tirkah_am = AM akhir yang akan dipakai pada nominal.
    headcount laki & perempuan untuk muqasamah.
    Return: (mode, detail) -> mode in {"muqasamah","one_third_residuum","one_sixth_total"}
    detail berisi angka saham pilihan untuk jadd.
    """
    # ini skeleton; implement angka saham nyata di calculator setelah AM fixed.
    # Di sini cukup kembalikan "mode" agar kalkulator mau jalankan pembagian sesuai mode.
    # Kamu bisa isi perhitungan final di kalkulator tempat sisa-saham dibagi.
    if sisa <= 0:
        return "one_sixth_total", {"reason": "Tidak ada sisa; minimal 1/6 total"}
    # default: pilih muqasamah (nanti kalkulator bandingkan rupiah mana terbesar dan tambahkan notes)
    return "muqasamah", {"reason": "Pilihan sementara; kalkulator akan membandingkan 3 opsi dan memilih terbesar."}

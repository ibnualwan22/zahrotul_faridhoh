# app/special/al_add.py
from typing import List, Tuple
from schemas import Heir, FurudhItem

ID = {
    "JADD": 6, "AKH_ABAWAYN": 7, "UKHT_ABAWAYN": 21, "AKH_AB": 8, "UKHT_AB": 22
}

def _q(heirs: List[Heir], i: int) -> int:
    return next((h.quantity for h in heirs if h.id == i), 0)

def is_al_add(heirs: List[Heir]) -> bool:
    has_jadd = _q(heirs, ID["JADD"]) > 0
    has_kandung = _q(heirs, ID["AKH_ABAWAYN"]) + _q(heirs, ID["UKHT_ABAWAYN"]) > 0
    has_seayah = _q(heirs, ID["AKH_AB"]) + _q(heirs, ID["UKHT_AB"]) > 0
    no_father = _q(heirs, 2) == 0
    no_son = _q(heirs, 1) == 0 and _q(heirs, 5) == 0
    return has_jadd and has_kandung and has_seayah and no_father and no_son

def apply_al_add(furudh: List[FurudhItem], heirs: List[Heir]) -> Tuple[List[FurudhItem], List[str]]:
    """
    Kita tidak mengubah fard langsung. Kita hanya memberi 'flag' lewat catatan
    agar kalkulator (tahap muqasamah/inkisar) memasukkan saudara seayah
    sebagai 'peserta perbandingan' untuk mengecilkan jadd (sesuai ringkasan kitab).
    Implementasi praktis: tambahkan note & biarkan engine ashobah/muqasamah
    menggunakan semua saudara (kandung + seayah) dalam bobot 2:1 bila masuk sisa.
    """
    notes = []
    notes.append("Masalah al-‘Add: saudara seayah disertakan dalam perbandingan untuk mengecilkan bagian Jadd.")
    return furudh, notes

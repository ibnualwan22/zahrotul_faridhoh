# app/special/router.py
from typing import List, Tuple
from schemas import Heir, FurudhItem

from .akdariyyah import is_akdariyyah, apply_akdariyyah
from .al_add import is_al_add, apply_al_add
from .jadd_ikhwah import is_jadd_ikhwah

def apply_special_cases(db, heirs: List[Heir], furudh_items: List[FurudhItem]):
    notes: List[str] = []
    calc_mode = {"mode": "normal"}   # bisa ganti: {"mode": "jadd_ikhwah"}

    # 1) Akdariyyah (paling spesifik → cek duluan)
    if is_akdariyyah(heirs):
        furudh_items, n = apply_akdariyyah(furudh_items, heirs)
        notes.extend(n)
        return furudh_items, notes, calc_mode

    # 2) al-‘Add (efeknya ke cara kita menghitung muqasamah/inkisar – cukup catatan)
    if is_al_add(heirs):
        _, n = apply_al_add(furudh_items, heirs)
        notes.extend(n)

    # 3) Jadd ma'al-Ikhwah → beritahu kalkulator pakai mode khusus
    if is_jadd_ikhwah(heirs):
        calc_mode["mode"] = "jadd_ikhwah"

    return furudh_items, notes, calc_mode

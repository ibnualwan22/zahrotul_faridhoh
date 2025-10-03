# app/math/inkisar.py

from typing import List, Dict, Tuple
from math import gcd

from schemas import HeirShare, ComparisonItem

def _relation(a: int, b: int) -> str:
    """
    Menentukan hubungan perbandingan dua bilangan sesuai istilah kitab:
    - muwafaqoh   : gcd(a,b) > 1 dan a tidak membagi b dan b tidak membagi a
    - mubayanah   : gcd(a,b) == 1
    - mudakholah  : salah satunya membagi yang lain (a|b atau b|a), tapi tidak sama
    - mumatsalah  : a == b
    """
    if a == b:
        return "mumatsalah"
    if a % b == 0 or b % a == 0:
        return "mudakholah"
    g = gcd(a, b)
    if g == 1:
        return "mubayanah"
    return "muwafaqoh"


def _single_group_factor(ruus: int, saham_kelompok: int) -> Tuple[int, str, int]:
    """
    Untuk 1 kelompok inkisar:
    - Kembalikan (faktor_pengali, relation, bagian_muwafaqoh)
      * faktor_pengali: berapa yang harus dikali ke Asl & saham agar saham_kelompok habis ke ruus.
      * relation: istilah hubungan.
      * bagian_muwafaqoh: jika muwafaqoh → ruus/gcd, selain itu 0 (untuk catatan lanjutan).
    Aturan sesuai kitab:
      - mubayanah: faktor = ruus
      - muwafaqoh: faktor = ruus / gcd(ruus, saham_kelompok)
      - mudakholah: jika saham | ruus → faktor = ruus / saham
                    jika ruus | saham → (sebenarnya sudah bisa habis → faktor=1)
      - mumatsalah: faktor = 1
    """
    rel = _relation(ruus, saham_kelompok)
    if rel == "mubayanah":
        return ruus, rel, 0
    if rel == "mumatsalah":
        return 1, rel, 0
    if rel == "mudakholah":
        if ruus % saham_kelompok == 0:
            return ruus // saham_kelompok, rel, 0
        else:
            # saham_kelompok % ruus == 0 -> sudah habis, tak perlu faktor
            return 1, rel, 0
    # muwafaqoh
    g = gcd(ruus, saham_kelompok)
    return ruus // g, "muwafaqoh", ruus // g


def compute_inkisar_multiplier(
    groups: List[Tuple[str, int, int]]
) -> Tuple[int, List[ComparisonItem], List[str]]:
    """
    Hitung faktor tashih inkisar untuk 1 atau banyak kelompok.
    Input:
      groups = list of (nama_kelompok, ruus, saham_kelompok)
        - ruus = jumlah orang pada kelompok tsb (عدد الرؤوس)
        - saham_kelompok = total saham untuk kelompok tsb (sebelum inkisar)

    Output:
      (multiplier, comparisons, notes)
        - multiplier: bilangan pengali untuk Asl dan seluruh saham agar tiap kelompok bisa dibagi rata
        - comparisons: daftar ComparisonItem (a=ruus, b=saham_kelompok, relation=…)
        - notes: catatan langkah seperti di kitab
    Aturan gabungan:
      * Untuk tiap kelompok tentukan faktor f_k menurut _single_group_factor
      * Jika beberapa kelompok: 
          - kalikan semua faktor (cara ringkas kitab: kalikan semua bilangan yang “tidak bisa dibagi”
            dan jika ada muwāfaqah, ambil hasilnya dulu (ruus/gcd) baru kalikan dengan bilangan lain)
    """
    notes: List[str] = []
    comps: List[ComparisonItem] = []
    factors: List[int] = []
    muwafaqoh_parts: List[int] = []  # hanya untuk dokumentasi

    for nama, ruus, saham_k in groups:
        rel = _relation(ruus, saham_k)
        comps.append(ComparisonItem(a=ruus, b=saham_k, relation=rel))
        notes.append(f"Kelompok {nama}: عدد الرؤوس {ruus} : saham {saham_k} → {rel}")

        f, rel2, part = _single_group_factor(ruus, saham_k)
        factors.append(f)
        if rel2 == "muwafaqoh" and part > 1:
            muwafaqoh_parts.append(part)

    # multiplier akhir: kalikan semua faktor > 1
    multiplier = 1
    for f in factors:
        if f > 1:
            multiplier *= f

    # catatan gaya kitab (bila ada muwafaqoh)
    if muwafaqoh_parts:
        notes.append(
            f"Karena ada muwāfaqoh, ambil hasil pembagian dahulu ({' × '.join(map(str, muwafaqoh_parts))}) "
            "lalu kalikan dengan bilangan lain yang diperlukan."
        )

    if multiplier == 1:
        notes.append("Inkisar selesai tanpa tashīḥ (semua kelompok sudah terbagi rata).")
    else:
        notes.append(f"Tashīḥ inkisār: Asl dan seluruh saham dikalikan {multiplier}.")

    return multiplier, comps, notes

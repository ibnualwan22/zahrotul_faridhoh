# app/math/ashl.py

from typing import List
import math
from fractions import Fraction

from schemas import ComparisonItem, AshlInfo

def bandingkan(a: int, b: int) -> ComparisonItem:
    """
    Bandingkan dua penyebut furudh untuk menentukan:
    - Mumatsalah (sama)
    - Mudakholah (salah satu masuk ke lainnya)
    - Muwafaqoh (ada faktor persekutuan)
    - Mubayanah (berbeda total)
    """
    if a == b:
        relation = "Mumatsalah"
    elif a % b == 0 or b % a == 0:
        relation = "Mudakholah"
    elif math.gcd(a, b) > 1:
        relation = "Muwafaqoh"
    else:
        relation = "Mubayanah"

    return ComparisonItem(a=a, b=b, relation=relation, lcm=math.lcm(a, b))


def compute_ashl(denominators: List[int]) -> AshlInfo:
    """
    Menentukan Aslul Mas’alah dari daftar penyebut furudh.
    Langkah:
    1. Ambil semua penyebut
    2. Bandingkan dua-dua untuk tentukan jenis hubungan
    3. Cari KPK (lcm) sebagai Aslul Mas’alah
    4. Siapkan info AshlInfo
    """

    if not denominators:
        # Default: kalau tidak ada furudh, AM = 1
        return AshlInfo(
            ashl_awal=1,
            ashl_akhir=1,
            total_saham=0,
            status="Kosong",
            comparisons=[]
        )

    # --- Tentukan perbandingan antar penyebut ---
    comparisons: List[ComparisonItem] = []
    for i in range(len(denominators)):
        for j in range(i + 1, len(denominators)):
            comparisons.append(bandingkan(denominators[i], denominators[j]))

    # --- Hitung Aslul Mas’alah (KPK semua penyebut) ---
    ashl_awal = denominators[0]
    for d in denominators[1:]:
        ashl_awal = math.lcm(ashl_awal, d)

    # Awalnya AM akhir = AM awal (bisa berubah kalau aul/radd/inkisar)
    ashl_akhir = ashl_awal

    return AshlInfo(
        ashl_awal=ashl_awal,
        ashl_akhir=ashl_akhir,
        total_saham=0,   # akan diisi di calculator
        status="Adil",   # default, bisa berubah di calculator
        comparisons=comparisons
    )

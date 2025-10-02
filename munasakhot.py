# Di dalam file: munasakhot.py

import math
from sqlalchemy.orm import Session # <-- PERBAIKAN ADA DI SINI
from schemas import MunasakhotInput, CalculationInput, MunasakhotResult, FinalShare
from calculator import calculate_inheritance
from database import SessionLocal

def get_relation_name(a, b):
    if a is None or b is None: return ""
    a, b = int(a), int(b)
    if a == b: return "Mumatsalah"
    if a % b == 0 or b % a == 0: return "Mudakholah"
    if math.gcd(a, b) > 1: return "Muwafaqoh"
    return "Mubayanah"

def solve_munasakhot(db: Session, munasakhot_input: MunasakhotInput):
    # --- TAHAP 1: Hitung Masalah Pertama (`Mas'alah Ula`) ---
    result_ula = calculate_inheritance(db, munasakhot_input.masalah_ula)
    
    # --- TAHAP 2: Dapatkan Data Kunci dari Masalah Pertama ---
    ashlul_masalah_ula = result_ula.ashlul_masalah_akhir
    mayit_tsani_share = next((s for s in result_ula.shares if s.heir.id == munasakhot_input.mayit_tsani_id), None)
    
    if not mayit_tsani_share or mayit_tsani_share.saham == 0:
        # Untuk sementara, kembalikan error jika mayit kedua tidak dapat bagian
        # Di frontend, ini bisa ditampilkan sebagai pesan yang lebih ramah
        raise ValueError("Ahli waris yang meninggal kedua tidak ditemukan atau tidak mendapat bagian di masalah pertama.")

    saham_mayit_tsani = mayit_tsani_share.saham
    
    # --- TAHAP 3: Hitung Masalah Kedua (`Mas'alah Tsaniyah`) ---
    input_tsaniyah = CalculationInput(
        heirs=munasakhot_input.masalah_tsaniyah_heirs,
        tirkah=mayit_tsani_share.share_amount # Gunakan bagian mayit kedua sebagai tirkah sementara
    )
    result_tsaniyah = calculate_inheritance(db, input_tsaniyah)
    ashlul_masalah_tsaniyah = result_tsaniyah.ashlul_masalah_akhir

    # --- TAHAP 4: Bandingkan dan Tentukan Pengali ---
    relation = get_relation_name(saham_mayit_tsani, ashlul_masalah_tsaniyah)
    
    multiplier_ula = 1
    multiplier_tsaniyah = 1

    if relation in ["Muwafaqoh", "Mudakholah"]:
        common_divisor = math.gcd(int(saham_mayit_tsani), int(ashlul_masalah_tsaniyah))
        multiplier_ula = ashlul_masalah_tsaniyah // common_divisor
        multiplier_tsaniyah = int(saham_mayit_tsani) // common_divisor
    elif relation == "Mubayanah":
        multiplier_ula = ashlul_masalah_tsaniyah
        multiplier_tsaniyah = int(saham_mayit_tsani)
    # Jika Mumatsalah, multiplier tetap 1

    # --- TAHAP 5: Hitung Jami'ah dan Saham Final ---
    jamiiah = ashlul_masalah_ula * multiplier_ula
    
    final_shares_map = {}

    # Proses ahli waris dari masalah pertama (yang masih hidup)
    for share in result_ula.shares:
        if share.heir.id != munasakhot_input.mayit_tsani_id:
            final_saham = share.saham * multiplier_ula
            if final_saham > 0:
                final_shares_map[share.heir.id] = {
                    "heir": share.heir,
                    "final_saham": final_saham
                }

    # Proses ahli waris dari masalah kedua
    for share in result_tsaniyah.shares:
        final_saham = share.saham * multiplier_tsaniyah
        if final_saham > 0:
            if share.heir.id in final_shares_map:
                final_shares_map[share.heir.id]["final_saham"] += final_saham
            else:
                final_shares_map[share.heir.id] = {
                    "heir": share.heir,
                    "final_saham": final_saham
                }
    
    final_shares_list = []
    for key, value in final_shares_map.items():
        share_amount = (munasakhot_input.masalah_ula.tirkah / jamiiah) * value["final_saham"]
        final_shares_list.append(
            FinalShare(
                heir=value["heir"],
                saham=value["final_saham"],
                share_amount=share_amount
            )
        )

    return MunasakhotResult(
        detail_masalah_ula=result_ula,
        detail_masalah_tsaniyah=result_tsaniyah,
        perbandingan=f"{int(saham_mayit_tsani)} vs {ashlul_masalah_tsaniyah} ({relation})",
        jamiiah=jamiiah,
        final_shares=final_shares_list
    )
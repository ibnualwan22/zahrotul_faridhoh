"""
Modul Perhitungan Warisan Islam (Faraid) - Lengkap
Mendukung semua kasus: Standar, Gharrawain, Musytarakah, Akdariyah, Jadd wal Ikhwah, dan al-'Add
"""

from sqlalchemy.orm import Session
import crud
import schemas
import models
import jadd_wal_ikhwah
from fractions import Fraction
import math
from typing import List, Dict, Set, Tuple, Any


# ========== KONSTANTA ==========
ASHOBAH_NASAB_ORDER = [
    "Anak Laki-laki", "Cucu Laki-laki", "Ayah", "Kakek",
    "Saudara Laki-laki Kandung", "Saudara Laki-laki Seayah",
    "Keponakan Laki-laki (dari Sdr Lk Kandung)", "Keponakan Laki-laki (dari Sdr Lk Seayah)",
    "Paman Kandung", "Paman Seayah",
    "Sepupu Laki-laki (dari Paman Kandung)", "Sepupu Laki-laki (dari Paman Seayah)"
]

ASHOBAH_SABAB_NAMES = ["Pria Pembebas Budak", "Wanita Pembebas Budak"]

DESCENDANT_NAMES = ["Anak Laki-laki", "Anak Perempuan", "Cucu Laki-laki", "Cucu Perempuan"]
MALE_DESCENDANT_NAMES = ["Anak Laki-laki", "Cucu Laki-laki"]
FEMALE_DESCENDANT_NAMES = ["Anak Perempuan", "Cucu Perempuan"]

SIBLING_NAMES = [
    "Saudara Laki-laki Kandung", "Saudara Laki-laki Seayah", "Saudara Laki-laki Seibu",
    "Saudari Kandung", "Saudari Seayah", "Saudari Seibu"
]

IKHWAH_NAMES = [
    "Saudara Laki-laki Kandung", "Saudari Kandung",
    "Saudara Laki-laki Seayah", "Saudari Seayah"
]


# ========== FUNGSI HELPER ==========
def lcm(a: int, b: int) -> int:
    """Menghitung Least Common Multiple (KPK)."""
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def is_male_heir(name: str) -> bool:
    """Cek apakah ahli waris adalah laki-laki."""
    male_prefixes = ("Anak Laki-laki", "Cucu Laki-laki", "Saudara Laki-laki", 
                     "Keponakan", "Paman", "Sepupu")
    return name.startswith(male_prefixes) or name in ["Ayah", "Kakek", "Suami"]


# ========== FUNGSI UTAMA ==========
def calculate_inheritance(db: Session, calculation_input: schemas.CalculationInput):
    """
    Menghitung pembagian warisan berdasarkan hukum Faraid.
    
    Tahapan:
    1. Inisialisasi dan Hajb (penghalang)
    2. Deteksi kasus istimewa (Akdariyah, Gharrawain, Musytarakah, al-'Add)
    3. Penentuan bagian dan saham
    4. Finalisasi: 'Aul, Radd, Inkisar
    """
    input_heirs = calculation_input.heirs
    tirkah = calculation_input.tirkah
    
    # Validasi input
    if tirkah <= 0:
        raise ValueError("Tirkah harus lebih besar dari 0")
    
    heir_ids = [h.id for h in input_heirs]
    selected_heirs_db = crud.get_heirs_by_ids(db, heir_ids=heir_ids)
    
    # Inisialisasi struktur data ahli waris
    selected_heirs = []
    for heir_input in input_heirs:
        db_data = next((h for h in selected_heirs_db if h.id == heir_input.id), None)
        if db_data:
            selected_heirs.append({
                "data": db_data,
                "quantity": heir_input.quantity,
                "share_fraction_str": "0",
                "reason": "",
                "is_ashobah": False,
                "is_ashobah_bil_ghair": False,
                "is_ashobah_maal_ghair": False,
                "saham": 0.0
            })

    # ========== TAHAP 1: HAJB (PENGHALANG) ==========
    blocked_heirs, blocking_heirs_details = apply_hajb_rules(selected_heirs, input_heirs)

    # ========== TAHAP 2: DETEKSI KASUS ISTIMEWA ==========
    notes = []
    heir_names = {h['data'].name_id for h in selected_heirs}
    
    is_akdariyah = check_akdariyah(selected_heirs, heir_names)
    is_gharrawain = check_gharrawain(selected_heirs, heir_names)
    is_musytarakah = check_musytarakah(selected_heirs, heir_names)

    # ========== TAHAP 3: PENANGANAN BERDASARKAN KASUS ==========
    
    # KASUS AKDARIYAH (prioritas tertinggi)
    if is_akdariyah:
        ashlul_masalah_akhir = handle_akdariyah(selected_heirs, notes)
        status = f"Masalah Akdariyah ('Aul & Tashih menjadi {ashlul_masalah_akhir})"
        
        final_shares = generate_final_shares(selected_heirs, tirkah, ashlul_masalah_akhir)
        total_saham_final = sum(h.get('saham', 0) for h in selected_heirs)
        
        return schemas.CalculationResult(
            tirkah=tirkah,
            ashlul_masalah_awal=6,
            ashlul_masalah_akhir=ashlul_masalah_akhir,
            total_saham=int(total_saham_final),
            status=status,
            notes=notes,
            shares=final_shares
        )
    
    # KASUS GHARRAWAIN
    elif is_gharrawain:
        ashlul_masalah_awal = handle_gharrawain(selected_heirs, notes)
    
    # KASUS MUSYTARAKAH
    elif is_musytarakah:
        ashlul_masalah_awal = handle_musytarakah(selected_heirs, notes)
    
    # KASUS STANDAR (termasuk Jadd wal Ikhwah dan al-'Add)
    else:
        ashlul_masalah_awal = handle_standard_case(selected_heirs, blocked_heirs, notes)

    # ========== TAHAP 4: FINALISASI ('AUL, RADD, INKISAR) ==========
    ashlul_masalah_akhir, status = apply_aul_radd_inkisar(
        selected_heirs, ashlul_masalah_awal, is_gharrawain, notes
    )

    # Generate hasil akhir
    final_shares = generate_final_shares(selected_heirs, tirkah, ashlul_masalah_akhir)
    total_saham_final = sum(h.get('saham', 0) for h in selected_heirs)
    
    return schemas.CalculationResult(
        tirkah=tirkah,
        ashlul_masalah_awal=int(ashlul_masalah_awal),
        ashlul_masalah_akhir=int(ashlul_masalah_akhir),
        total_saham=int(round(total_saham_final)),
        status=status,
        notes=notes,
        shares=final_shares
    )


# ========== TAHAP 1: HAJB ==========
def apply_hajb_rules(selected_heirs: List[Dict], input_heirs: List) -> Tuple[Set[str], Dict[str, str]]:
    """Menerapkan aturan hajb (penghalang) untuk semua ahli waris."""
    blocked_heirs = set()
    blocking_heirs_details = {}
    heir_names = {h['data'].name_id for h in selected_heirs}

    # Cek Mawani' al-Irts (penghalang karena sifat)
    for i, heir_input in enumerate(input_heirs):
        if heir_input.penghalang:
            heir_to_block = selected_heirs[i]
            heir_name = heir_to_block['data'].name_id
            blocked_heirs.add(heir_name)
            blocking_heirs_details[heir_name] = f"sifat ({heir_input.penghalang})"
    
    # Penghalang berdasarkan kehadiran ahli waris lain
    apply_ashobah_nasab_blocking(selected_heirs, blocked_heirs, blocking_heirs_details)
    apply_parent_blocking(selected_heirs, blocked_heirs, blocking_heirs_details)
    apply_descendant_blocking(selected_heirs, blocked_heirs, blocking_heirs_details)
    apply_sibling_blocking(selected_heirs, blocked_heirs, blocking_heirs_details)
    
    return blocked_heirs, blocking_heirs_details


def apply_ashobah_nasab_blocking(selected_heirs, blocked_heirs, blocking_heirs_details):
    """Blokir ashobah nasab yang lebih lemah."""
    
    # Cari ashobah nasab terkuat (KECUALI Ayah dan Kakek)
    strongest_ashobah_nasab_name = None
    for name in ASHOBAH_NASAB_ORDER:
        # Skip Ayah dan Kakek - mereka punya aturan khusus
        if name in ["Ayah", "Kakek"]:
            continue
            
        # Cek apakah ahli waris ini ada
        if any(h['data'].name_id == name for h in selected_heirs):
            strongest_ashobah_nasab_name = name
            break
    
    if strongest_ashobah_nasab_name:
        # Blokir semua ashobah yang lebih lemah
        start_blocking = False
        for heir_name in ASHOBAH_NASAB_ORDER:
            # PENTING: Jangan pernah blokir Ayah atau Kakek
            if heir_name in ["Ayah", "Kakek"]:
                continue
                
            if heir_name == strongest_ashobah_nasab_name:
                start_blocking = True
                continue
                
            if start_blocking:
                blocked_heirs.add(heir_name)
                blocking_heirs_details[heir_name] = strongest_ashobah_nasab_name
        
        # Blokir ashobah bi sabab (pembebas budak)
        blocked_heirs.update(ASHOBAH_SABAB_NAMES)
        blocking_heirs_details.update({
            name: strongest_ashobah_nasab_name 
            for name in ASHOBAH_SABAB_NAMES
        })


def apply_parent_blocking(selected_heirs, blocked_heirs, blocking_heirs_details):
    """Blokir ahli waris yang terhalang oleh orang tua."""
    father = next((h for h in selected_heirs if h['data'].name_id == "Ayah"), None)
    mother = next((h for h in selected_heirs if h['data'].name_id == "Ibu"), None)
    
    if father:
        blocked_heirs.add("Kakek")
        blocking_heirs_details["Kakek"] = "Ayah"
        blocked_heirs.add("Nenek dari Ayah")
        blocking_heirs_details["Nenek dari Ayah"] = "Ayah"
        blocked_heirs.update(SIBLING_NAMES)
        for h in SIBLING_NAMES:
            blocking_heirs_details[h] = "Ayah"
    
    if mother:
        blocked_heirs.update(["Nenek dari Ibu", "Nenek dari Ayah"])
        blocking_heirs_details.update({
            "Nenek dari Ibu": "Ibu",
            "Nenek dari Ayah": "Ibu"
        })


def apply_descendant_blocking(selected_heirs, blocked_heirs, blocking_heirs_details):
    """Blokir ahli waris yang terhalang oleh keturunan."""
    son = next((h for h in selected_heirs if h['data'].name_id == "Anak Laki-laki"), None)
    
    if son:
        blocked_heirs.update(["Cucu Laki-laki", "Cucu Perempuan"])
        blocking_heirs_details.update({
            "Cucu Laki-laki": "Anak Laki-laki",
            "Cucu Perempuan": "Anak Laki-laki"
        })
    
    descendant_or_male_ascendant = any(
        h['data'].name_id in DESCENDANT_NAMES + ["Ayah", "Kakek"] 
        for h in selected_heirs
    )
    if descendant_or_male_ascendant:
        blocked_heirs.update(["Saudara Laki-laki Seibu", "Saudari Seibu"])
        blocking_heirs_details.update({
            "Saudara Laki-laki Seibu": "Keturunan/Ayah/Kakek",
            "Saudari Seibu": "Keturunan/Ayah/Kakek"
        })


def apply_sibling_blocking(selected_heirs, blocked_heirs, blocking_heirs_details):
    """Blokir saudari seayah jika ada 2 saudari kandung tanpa saudara laki-laki seayah."""
    sisters_kandung_count = sum(
        h['quantity'] for h in selected_heirs 
        if h['data'].name_id == "Saudari Kandung"
    )
    
    if sisters_kandung_count >= 2:
        brother_seayah = next((
            h for h in selected_heirs 
            if h['data'].name_id == "Saudara Laki-laki Seayah"
        ), None)
        if not brother_seayah:
            blocked_heirs.add("Saudari Seayah")
            blocking_heirs_details["Saudari Seayah"] = "2 Saudari Kandung"


# ========== TAHAP 2: DETEKSI KASUS ISTIMEWA ==========
def check_akdariyah(selected_heirs: List[Dict], heir_names: Set[str]) -> bool:
    """
    Cek apakah kasus Akdariyah.
    
    Syarat SANGAT KETAT:
    1. Suami + Ibu (BUKAN Nenek) + Kakek + 1 Saudari (Kandung/Seayah)
    2. HANYA 4 ahli waris ini
    3. Tidak ada ahli waris lain
    """
    active_heirs = [h for h in selected_heirs if h.get('share_fraction_str', '') != "Mahjub"]
    
    if len(active_heirs) != 4:
        return False
    
    if not ("Suami" in heir_names and "Ibu" in heir_names and "Kakek" in heir_names):
        return False
    
    if "Nenek dari Ibu" in heir_names or "Nenek dari Ayah" in heir_names:
        return False
    
    has_saudari_kandung = "Saudari Kandung" in heir_names
    has_saudari_seayah = "Saudari Seayah" in heir_names
    
    if has_saudari_kandung and has_saudari_seayah:
        return False
    
    if not (has_saudari_kandung or has_saudari_seayah):
        return False
    
    saudari = next(
        (h for h in selected_heirs 
         if h['data'].name_id in ["Saudari Kandung", "Saudari Seayah"]),
        None
    )
    
    if not saudari or saudari['quantity'] != 1:
        return False
    
    if "Saudara Laki-laki Kandung" in heir_names or "Saudara Laki-laki Seayah" in heir_names:
        return False
    
    allowed_heirs = {"Suami", "Ibu", "Kakek", "Saudari Kandung", "Saudari Seayah"}
    for name in heir_names:
        if name not in allowed_heirs:
            return False
    
    return True


def check_gharrawain(selected_heirs: List[Dict], heir_names: Set[str]) -> bool:
    """Cek apakah kasus Gharrawain."""
    return (
        len(selected_heirs) == 3 
        and "Ayah" in heir_names 
        and "Ibu" in heir_names 
        and ("Suami" in heir_names or "Istri" in heir_names)
    )


def check_musytarakah(selected_heirs: List[Dict], heir_names: Set[str]) -> bool:
    """Cek apakah kasus Musytarakah."""
    seibu_count = sum(
        h['quantity'] for h in selected_heirs 
        if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"]
    )
    return (
        "Suami" in heir_names 
        and ("Ibu" in heir_names or "Nenek dari Ibu" in heir_names)
        and seibu_count >= 2 
        and "Saudara Laki-laki Kandung" in heir_names
    )


def check_masalah_al_add(selected_heirs: List[Dict], heir_names: Set[str], 
                         blocked_heirs: Set[str]) -> bool:
    """
    Cek apakah kasus Mas'alah al-'Add.
    
    Syarat:
    - Ada Kakek (tidak terblokir)
    - Ada Saudari Kandung (tidak terblokir)
    - Ada Saudara/Saudari Seayah (tidak terblokir)
    - Tidak ada Saudara Laki-laki Kandung
    - Tidak ada Ayah
    """
    if "Ayah" in heir_names:
        return False
    
    has_kakek = "Kakek" in heir_names and "Kakek" not in blocked_heirs
    has_saudari_kandung = "Saudari Kandung" in heir_names and "Saudari Kandung" not in blocked_heirs
    has_seayah_siblings = any(
        name in heir_names and name not in blocked_heirs
        for name in ["Saudara Laki-laki Seayah", "Saudari Seayah"]
    )
    has_brother_kandung = "Saudara Laki-laki Kandung" in heir_names and "Saudara Laki-laki Kandung" not in blocked_heirs
    
    return has_kakek and has_saudari_kandung and has_seayah_siblings and not has_brother_kandung


# ========== TAHAP 3: PENANGANAN KASUS ISTIMEWA ==========
def handle_akdariyah(selected_heirs: List[Dict], notes: List[str]) -> int:
    """Menangani kasus Akdariyah dengan perhitungan lengkap."""
    notes.append("Terdeteksi: Kasus Mas'alah al-Akdariyah.")
    
    suami = next(h for h in selected_heirs if h['data'].name_id == "Suami")
    ibu = next(h for h in selected_heirs if h['data'].name_id == "Ibu")
    kakek = next(h for h in selected_heirs if h['data'].name_id == "Kakek")
    saudari = next(
        h for h in selected_heirs 
        if h['data'].name_id in ["Saudari Kandung", "Saudari Seayah"]
    )
    
    ashlul_masalah_awal = 6
    notes.append(f"Ashlul Mas'alah awal: {ashlul_masalah_awal}")
    
    suami_awal = 3
    ibu_awal = 2
    kakek_awal = 1
    saudari_awal = 3
    
    notes.append(
        f"Bagian awal: Suami={suami_awal}, Ibu={ibu_awal}, "
        f"Kakek={kakek_awal}, Saudari={saudari_awal}"
    )
    
    total_awal = suami_awal + ibu_awal + kakek_awal + saudari_awal
    notes.append(f"Total = {total_awal} ('Aul dari {ashlul_masalah_awal} ke {total_awal})")
    
    combined = kakek_awal + saudari_awal
    notes.append(f"Musyarakah: Gabungkan Kakek + Saudari = {combined}")
    
    kakek_final = combined * 2 / 3
    saudari_final = combined * 1 / 3
    notes.append(f"Bagi 2:1 → Kakek = {kakek_final:.2f}, Saudari = {saudari_final:.2f}")
    
    tashih_multiplier = 3
    ashlul_masalah_akhir = total_awal * tashih_multiplier
    notes.append(f"Tashih: {total_awal} × {tashih_multiplier} = {ashlul_masalah_akhir}")
    
    suami['saham'] = suami_awal * tashih_multiplier
    ibu['saham'] = ibu_awal * tashih_multiplier
    kakek['saham'] = int(kakek_final * tashih_multiplier)
    saudari['saham'] = int(saudari_final * tashih_multiplier)
    
    suami['share_fraction_str'] = "1/2"
    ibu['share_fraction_str'] = "1/3"
    kakek['share_fraction_str'] = "1/6 (musyarakah)"
    saudari['share_fraction_str'] = "1/2 (musyarakah)"
    
    kakek['reason'] = "Musyarakah dalam kasus Akdariyah (2:1)."
    saudari['reason'] = "Musyarakah dalam kasus Akdariyah (2:1)."
    
    return ashlul_masalah_akhir


def handle_gharrawain(selected_heirs: List[Dict], notes: List[str]) -> int:
    """Menangani kasus Gharrawain."""
    notes.append("Terdeteksi: Kasus Mas'alah Gharrawain.")
    
    spouse = next(h for h in selected_heirs if h['data'].name_id in ["Suami", "Istri"])
    mother = next(h for h in selected_heirs if h['data'].name_id == "Ibu")
    father = next(h for h in selected_heirs if h['data'].name_id == "Ayah")
    
    if spouse['data'].name_id == "Suami":
        ashlul_masalah_awal = 6
        spouse['saham'] = 3
        mother['saham'] = 1
        father['saham'] = 2
        spouse['share_fraction_str'] = "1/2"
    else:
        ashlul_masalah_awal = 4
        spouse['saham'] = 1
        mother['saham'] = 1
        father['saham'] = 2
        spouse['share_fraction_str'] = "1/4"
    
    mother['share_fraction_str'] = "1/3 Sisa"
    father['share_fraction_str'] = "Sisa"
    
    notes.append(f"Ashlul Mas'alah: {ashlul_masalah_awal}")
    
    return ashlul_masalah_awal


def handle_musytarakah(selected_heirs: List[Dict], notes: List[str]) -> int:
    """Menangani kasus Musytarakah."""
    notes.append("Terdeteksi: Kasus Mas'alah Musytarakah.")
    ashlul_masalah_awal = 6
    
    suami = next(h for h in selected_heirs if h['data'].name_id == "Suami")
    ibu_atau_nenek = next(
        h for h in selected_heirs 
        if h['data'].name_id in ["Ibu", "Nenek dari Ibu", "Nenek dari Ayah"]
    )
    musytarakah_heirs = [
        h for h in selected_heirs 
        if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu", 
                                  "Saudara Laki-laki Kandung"]
    ]
    
    suami['share_fraction_str'] = "1/2"
    suami['saham_awal'] = 3
    
    ibu_atau_nenek['share_fraction_str'] = "1/6"
    ibu_atau_nenek['saham_awal'] = 1
    
    musytarakah_saham_awal = 2
    musytarakah_heads = sum(h['quantity'] for h in musytarakah_heirs)
    
    tashih_multiplier = (
        musytarakah_heads // math.gcd(musytarakah_saham_awal, musytarakah_heads)
        if musytarakah_saham_awal % musytarakah_heads != 0 
        else 1
    )
    
    if tashih_multiplier > 1:
        notes.append(f"Tashih: {ashlul_masalah_awal} × {tashih_multiplier} = {ashlul_masalah_awal * tashih_multiplier}")
    
    ashlul_masalah_awal *= tashih_multiplier
    suami['saham'] = suami['saham_awal'] * tashih_multiplier
    ibu_atau_nenek['saham'] = ibu_atau_nenek['saham_awal'] * tashih_multiplier
    
    saham_per_kepala_saudara = (musytarakah_saham_awal * tashih_multiplier) / musytarakah_heads
    for heir in musytarakah_heirs:
        heir['saham'] = saham_per_kepala_saudara * heir['quantity']
        heir['share_fraction_str'] = "1/3 (berbagi)"
        heir['reason'] = "Ikut serta (musytarakah)."
    
    return ashlul_masalah_awal


def handle_standard_case(selected_heirs: List[Dict], blocked_heirs: Set[str], 
                        notes: List[str]) -> int:
    """Menangani kasus standar (termasuk Jadd wal Ikhwah dan al-'Add)."""
    
    # 1. Tentukan fardh untuk semua ahli waris
    assign_standard_shares(selected_heirs, blocked_heirs)
    
    # 2. Hitung Ashlul Masalah Awal
    denominators = sorted(list(set([
        Fraction(h['share_fraction_str'].split()[0]).denominator 
        for h in selected_heirs 
        if '/' in h['share_fraction_str']
    ])))
    
    ashlul_masalah_awal = 1
    if denominators:
        notes.append(f"Penyebut yang ada: {', '.join(map(str, denominators))}.")
        ashlul_masalah_awal = math.lcm(*denominators)
    notes.append(f"Ashlul Mas'alah awal ditentukan: {ashlul_masalah_awal}.")
    
    # 3. Identifikasi Jadd dan Ikhwah
    heir_names = {h['data'].name_id for h in selected_heirs}
    
    jadd = next((
        h for h in selected_heirs 
        if h['data'].name_id == "Kakek" and h['data'].name_id not in blocked_heirs
    ), None)
    
    ikhwah = [
        h for h in selected_heirs 
        if h['data'].name_id in IKHWAH_NAMES 
        and h['data'].name_id not in blocked_heirs
    ]
    
    # 4. Cek kasus khusus
    if check_masalah_al_add(selected_heirs, heir_names, blocked_heirs):
        # Kasus Mas'alah al-'Add
        ashlul_masalah_awal = handle_masalah_al_add(
            selected_heirs, blocked_heirs, ashlul_masalah_awal, notes
        )
    elif jadd and ikhwah:
        # Kasus Jadd wal Ikhwah biasa
        ashlul_masalah_awal = handle_jadd_wal_ikhwah(
            selected_heirs, jadd, ikhwah, ashlul_masalah_awal, notes
        )
    else:
        # Perhitungan saham standar
        calculate_standard_shares(selected_heirs, ashlul_masalah_awal)
    
    return ashlul_masalah_awal


def handle_masalah_al_add(selected_heirs: List[Dict], blocked_heirs: Set[str],
                          ashlul_masalah_awal: int, notes: List[str]) -> int:
    """Menangani kasus Mas'alah al-'Add."""
    notes.append("Terdeteksi: Mas'alah al-'Add (Saudari Kandung membantu Saudara Seayah).")
    
    kakek = next((h for h in selected_heirs if h['data'].name_id == "Kakek"), None)
    saudari_kandung = next((h for h in selected_heirs if h['data'].name_id == "Saudari Kandung"), None)
    seayah_siblings = [
        h for h in selected_heirs 
        if h['data'].name_id in ["Saudara Laki-laki Seayah", "Saudari Seayah"]
        and h['data'].name_id not in blocked_heirs
    ]
    
    other_dzawil_furudh = [
        h for h in selected_heirs 
        if h not in [kakek, saudari_kandung] + seayah_siblings
        and '/' in h.get('share_fraction_str', '')
        and h['data'].name_id not in blocked_heirs
    ]
    
    # Hitung saham dzawil furudh
    for h in other_dzawil_furudh:
        frac_str = h['share_fraction_str'].split()[0]
        h['saham'] = int(Fraction(frac_str) * ashlul_masalah_awal)
    
    total_dzawil_furudh = sum(h.get('saham', 0) for h in other_dzawil_furudh)
    remaining_saham = ashlul_masalah_awal - total_dzawil_furudh
    
    # Hitung fardh Saudari Kandung
    saudari_kandung_qty = saudari_kandung['quantity']
    if saudari_kandung_qty == 1:
        saudari_kandung_fardh = Fraction(1, 2) * ashlul_masalah_awal
        saudari_kandung['share_fraction_str'] = "1/2"
    else:
        saudari_kandung_fardh = Fraction(2, 3) * ashlul_masalah_awal
        saudari_kandung['share_fraction_str'] = "2/3"
    
    # Muqasamah (Saudari Kandung ikut)
    muqasamah_heads = 2 + (1 * saudari_kandung_qty)
    for h in seayah_siblings:
        if h['data'].name_id == "Saudara Laki-laki Seayah":
            muqasamah_heads += 2 * h['quantity']
        else:
            muqasamah_heads += 1 * h['quantity']
    
    saham_per_head = remaining_saham / muqasamah_heads
    kakek_muqasamah = saham_per_head * 2
    
    # Pilih opsi terbaik untuk Kakek
    kakek_option_suds = ashlul_masalah_awal / 6
    kakek_option_tsuluts_baqi = remaining_saham / 3 if other_dzawil_furudh else ashlul_masalah_awal / 3
    
    best_option = max(kakek_muqasamah, kakek_option_suds, kakek_option_tsuluts_baqi)
    kakek['saham'] = best_option
    kakek['reason'] = "Al-'Add: Muqasamah" if best_option == kakek_muqasamah else "Al-'Add: 1/6"
    
    # Sisa untuk Saudari Kandung dan Saudara Seayah
    sisa_after_kakek = remaining_saham - best_option
    saudari_kandung['saham'] = min(saudari_kandung_fardh, sisa_after_kakek)
    saudari_kandung['reason'] = f"Al-'Add: Ikut muqasamah, ambil fardh {saudari_kandung['share_fraction_str']}"
    
    sisa_for_seayah = sisa_after_kakek - saudari_kandung['saham']
    
    seayah_heads = sum(
        (2 if h['data'].name_id == "Saudara Laki-laki Seayah" else 1) * h['quantity']
        for h in seayah_siblings
    )
    
    if seayah_heads > 0 and sisa_for_seayah > 0:
        saham_per_head_seayah = sisa_for_seayah / seayah_heads
        for h in seayah_siblings:
            head_count = 2 if h['data'].name_id == "Saudara Laki-laki Seayah" else 1
            h['saham'] = saham_per_head_seayah * head_count * h['quantity']
            h['share_fraction_str'] = "Sisa (al-'Add)"
            h['reason'] = "Al-'Add: Ashobah setelah Kakek dan Saudari Kandung"
    
    # Tashih jika perlu
    all_saham = [kakek['saham'], saudari_kandung['saham']] + [h['saham'] for h in seayah_siblings] + [h['saham'] for h in other_dzawil_furudh]
    
    denominators = []
    for s in all_saham:
        if isinstance(s, float) and not s.is_integer():
            frac = Fraction(s).limit_denominator(1000)
            denominators.append(frac.denominator)
    
    if denominators:
        tashih_multiplier = denominators[0]
        for d in denominators[1:]:
            tashih_multiplier = math.lcm(tashih_multiplier, d)
        
        if tashih_multiplier > 1:
            notes.append(f"Tashih al-'Add: {ashlul_masalah_awal} × {tashih_multiplier} = {ashlul_masalah_awal * tashih_multiplier}")
            ashlul_masalah_awal *= tashih_multiplier
            
            for h in selected_heirs:
                if h.get('saham', 0) > 0:
                    h['saham'] *= tashih_multiplier
    
    return ashlul_masalah_awal


def handle_jadd_wal_ikhwah(selected_heirs: List[Dict], jadd: Dict, ikhwah: List[Dict],
                           ashlul_masalah_awal: int, notes: List[str]) -> int:
    """Menangani kasus Jadd wal Ikhwah."""
    notes.append("Terdeteksi: Kasus Jadd wal Ikhwah.")
    
    other_dzawil_furudh = [
        h for h in selected_heirs 
        if h not in ikhwah and h != jadd and '/' in h.get('share_fraction_str', '')
    ]
    
    for h in other_dzawil_furudh:
        h['saham'] = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
    
    jadd_result = jadd_wal_ikhwah.calculate_jadd_share(
        jadd, ikhwah, other_dzawil_furudh, ashlul_masalah_awal
    )
    
    if jadd_result['tashih_multiplier'] > 1:
        notes.append(
            f"Tashih pada Jadd wal Ikhwah: {ashlul_masalah_awal} x "
            f"{jadd_result['tashih_multiplier']} = "
            f"{ashlul_masalah_awal * jadd_result['tashih_multiplier']}"
        )
        ashlul_masalah_awal *= jadd_result['tashih_multiplier']
        
        for h in other_dzawil_furudh:
            h['saham'] *= jadd_result['tashih_multiplier']
    
    jadd['saham'] = jadd_result['jadd_saham']
    jadd['reason'] = f"Bagian terbaik adalah {jadd_result['chosen_option']}."
    
    for h in ikhwah:
        h['saham'] = jadd_result['ikhwah_shares'].get(h['data'].id, 0)
        h['share_fraction_str'] = "Sisa (bersama Kakek)"
    
    return ashlul_masalah_awal


def assign_standard_shares(selected_heirs: List[Dict], blocked_heirs: Set[str]):
    """Menentukan fardh untuk setiap ahli waris dalam kasus standar."""
    descendant_names_present = [
        h['data'].name_id for h in selected_heirs 
        if h['data'].name_id in DESCENDANT_NAMES 
        and h['data'].name_id not in blocked_heirs
    ]
    female_descendants_present = [
        h for h in selected_heirs 
        if h['data'].name_id in FEMALE_DESCENDANT_NAMES 
        and h['data'].name_id not in blocked_heirs
    ]
    male_descendant_names_present = [
        h['data'].name_id for h in selected_heirs 
        if h['data'].name_id in MALE_DESCENDANT_NAMES 
        and h['data'].name_id not in blocked_heirs
    ]
    sibling_count = sum(
        h['quantity'] for h in selected_heirs 
        if h['data'].name_id in SIBLING_NAMES 
        and h['data'].name_id not in blocked_heirs
    )
    
    son = next((h for h in selected_heirs if h['data'].name_id == "Anak Laki-laki"), None)
    grandson = next((h for h in selected_heirs if h['data'].name_id == "Cucu Laki-laki"), None)
    brother_kandung = next((h for h in selected_heirs if h['data'].name_id == "Saudara Laki-laki Kandung"), None)
    
    for heir in selected_heirs:
        name = heir['data'].name_id
        quantity = heir['quantity']
        
        if name in blocked_heirs:
            heir['share_fraction_str'] = "Mahjub"
            heir['reason'] = "Terhalang oleh kehadiran ahli waris lain."
            continue
        
        if name == "Suami":
            heir['share_fraction_str'] = "1/4" if descendant_names_present else "1/2"
        
        elif name == "Istri":
            heir['share_fraction_str'] = "1/8" if descendant_names_present else "1/4"
        
        elif name == "Ayah":
            if male_descendant_names_present:
                heir['share_fraction_str'] = "1/6"
            elif descendant_names_present:
                heir['share_fraction_str'] = "1/6"
                heir['is_ashobah'] = True
            else:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah'] = True
        
        elif name == "Ibu":
            if descendant_names_present or sibling_count > 1:
                heir['share_fraction_str'] = "1/6"
            else:
                heir['share_fraction_str'] = "1/3"
        
        elif name == "Anak Perempuan":
            if son:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_bil_ghair'] = True
            elif quantity == 1:
                heir['share_fraction_str'] = "1/2"
            else:
                heir['share_fraction_str'] = "2/3"
        
        elif name == "Cucu Perempuan":
            daughter_count_val = sum(
                h['quantity'] for h in selected_heirs 
                if h['data'].name_id == "Anak Perempuan"
            )
            if grandson:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_bil_ghair'] = True
            elif daughter_count_val == 1:
                heir['share_fraction_str'] = "1/6"
            elif daughter_count_val == 0 and quantity == 1:
                heir['share_fraction_str'] = "1/2"
            elif daughter_count_val == 0 and quantity > 1:
                heir['share_fraction_str'] = "2/3"
            else:
                heir['share_fraction_str'] = "Mahjub"
        
        elif name == "Kakek":
            if male_descendant_names_present:
                heir['share_fraction_str'] = "1/6"
            elif descendant_names_present:
                heir['share_fraction_str'] = "1/6"
                heir['is_ashobah'] = True
            else:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah'] = True
        
        elif name in ["Nenek dari Ibu", "Nenek dari Ayah"]:
            heir['share_fraction_str'] = "1/6"
        
        elif name in ["Saudara Laki-laki Seibu", "Saudari Seibu"]:
            siblings_seibu_count = sum(
                h['quantity'] for h in selected_heirs 
                if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"]
            )
            heir['share_fraction_str'] = "1/6" if siblings_seibu_count == 1 else "1/3 (berbagi)"
        
        elif name == "Saudari Kandung":
            if female_descendants_present:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_maal_ghair'] = True
            elif brother_kandung:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_bil_ghair'] = True
            elif quantity == 1:
                heir['share_fraction_str'] = "1/2"
            else:
                heir['share_fraction_str'] = "2/3"
        
        elif name == "Saudari Seayah":
            sister_kandung = next((
                h for h in selected_heirs 
                if h['data'].name_id == "Saudari Kandung"
            ), None)
            brother_seayah = next((
                h for h in selected_heirs 
                if h['data'].name_id == "Saudara Laki-laki Seayah"
            ), None)
            
            if female_descendants_present:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_maal_ghair'] = True
            elif brother_seayah:
                heir['share_fraction_str'] = "Sisa"
                heir['is_ashobah_bil_ghair'] = True
            elif sister_kandung and sister_kandung['quantity'] == 1:
                heir['share_fraction_str'] = "1/6"
            elif quantity == 1:
                heir['share_fraction_str'] = "1/2"
            else:
                heir['share_fraction_str'] = "2/3"
        
        elif name in ASHOBAH_NASAB_ORDER or name in ASHOBAH_SABAB_NAMES:
            heir['share_fraction_str'] = "Sisa"
            heir['is_ashobah'] = True


def calculate_standard_shares(selected_heirs: List[Dict], ashlul_masalah_awal: int):
    """Menghitung saham standar dan distribusi sisa ke ashobah."""
    total_fardh_saham = 0
    
    for h in selected_heirs:
        if '/' in h['share_fraction_str']:
            saham_val = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
            if h['data'].name_id not in ["Saudara Laki-laki Seibu", "Saudari Seibu"]:
                h['saham'] = saham_val
                total_fardh_saham += saham_val
    
    # Hitung saham saudara seibu (berbagi merata)
    seibu_heirs = [
        h for h in selected_heirs 
        if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"] 
        and '/' in h['share_fraction_str']
    ]
    
    if seibu_heirs:
        seibu_total_saham = int(Fraction(seibu_heirs[0]['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
        total_fardh_saham += seibu_total_saham
        seibu_total_quantity = sum(h['quantity'] for h in seibu_heirs)
        
        if seibu_total_quantity > 0:
            for h in seibu_heirs:
                h['saham'] = (seibu_total_saham / seibu_total_quantity) * h['quantity']
    
    # Distribusi sisa ke ashobah
    remaining_saham = ashlul_masalah_awal - total_fardh_saham
    ashobah_heirs = [
        h for h in selected_heirs 
        if h.get('is_ashobah') or h.get('is_ashobah_bil_ghair') or h.get('is_ashobah_maal_ghair')
    ]
    
    if remaining_saham > 0 and ashobah_heirs:
        ashobah_heads = sum(
            (2 if is_male_heir(h['data'].name_id) else 1) * h['quantity'] 
            for h in ashobah_heirs
        )
        
        if ashobah_heads > 0:
            for h in ashobah_heirs:
                head_count = 2 if is_male_heir(h['data'].name_id) else 1
                h['saham'] = h.get('saham', 0) + (remaining_saham * head_count * h['quantity']) / ashobah_heads


# ========== TAHAP 4: FINALISASI ==========
def apply_radd_with_spouse(selected_heirs: List[Dict], ashlul_masalah_awal: int) -> int:
    """Menerapkan Radd ketika ada suami/istri."""
    spouse = next((h for h in selected_heirs if h['data'].name_id in ["Suami", "Istri"]), None)
    
    # PERBAIKAN: Filter hanya ahli waris yang TIDAK Mahjub
    radd_heirs = [
        h for h in selected_heirs 
        if h != spouse 
        and h.get('share_fraction_str', '') != 'Mahjub'  # ← TAMBAHKAN INI
        and '/' in h.get('share_fraction_str', '')  # ← DAN INI untuk keamanan
    ]
    
    # Jika tidak ada ahli waris untuk Radd, kembalikan AM awal
    if not radd_heirs:
        return ashlul_masalah_awal
    
    ashlul_masalah_spouse = Fraction(spouse['share_fraction_str'].split()[0]).denominator
    spouse['saham'] = 1
    remaining_saham_from_spouse_problem = ashlul_masalah_spouse - 1
    
    radd_denominators = sorted(list(set([
        Fraction(h['share_fraction_str'].split()[0]).denominator 
        for h in radd_heirs
    ])))
    ashlul_masalah_radd = math.lcm(*radd_denominators) if radd_denominators else 1
    
    total_saham_radd_group = sum(
        int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_radd) 
        for h in radd_heirs
    )
    
    # Hindari division by zero
    if total_saham_radd_group == 0:
        return ashlul_masalah_awal
    
    common_divisor = math.gcd(remaining_saham_from_spouse_problem, total_saham_radd_group)
    multiplier_spouse_problem = total_saham_radd_group // common_divisor
    multiplier_radd_problem = remaining_saham_from_spouse_problem // common_divisor
    
    ashlul_masalah_akhir = ashlul_masalah_spouse * multiplier_spouse_problem
    
    spouse['saham'] *= multiplier_spouse_problem
    for heir in radd_heirs:
        heir['saham'] = int(
            Fraction(heir['share_fraction_str'].split()[0]) * ashlul_masalah_radd
        ) * multiplier_radd_problem
    
    return ashlul_masalah_akhir


def apply_aul_radd_inkisar(selected_heirs: List[Dict], ashlul_masalah_awal: int,
                           is_gharrawain: bool, notes: List[str]) -> Tuple[int, str]:
    """Menerapkan 'Aul, Radd, dan Inkisar untuk finalisasi."""
    
    # Hitung total saham HANYA dari ahli waris yang TIDAK Mahjub
    total_saham_final = sum(
        h.get('saham', 0) for h in selected_heirs 
        if h.get('share_fraction_str', '') != 'Mahjub'
    )
    
    ashlul_masalah_akhir = ashlul_masalah_awal
    status = "Masalah 'Adilah (Pas)"
    
    if not is_gharrawain:
        # === KASUS 'AUL (NAIK) ===
        if round(total_saham_final) > ashlul_masalah_awal:
            ashlul_masalah_akhir = int(round(total_saham_final))
            status = f"Masalah 'Aul (naik dari {ashlul_masalah_awal} menjadi {ashlul_masalah_akhir})"
        
        # === KASUS RADD (TURUN) ===
        elif round(total_saham_final) < ashlul_masalah_awal:
            # Cek apakah ada ashobah (selain yang Mahjub)
            has_ashobah = any(
                h.get('is_ashobah') 
                for h in selected_heirs 
                if h.get('share_fraction_str', '') != 'Mahjub'
            )
            
            if not has_ashobah:
                # Cek apakah ada suami/istri
                has_spouse = any(
                    h['data'].name_id in ["Suami", "Istri"] 
                    for h in selected_heirs
                    if h.get('share_fraction_str', '') != 'Mahjub'
                )
                
                if not has_spouse:
                    # Radd tanpa suami/istri: turunkan AM
                    ashlul_masalah_akhir = int(round(total_saham_final))
                    status = f"Masalah Radd (turun dari {ashlul_masalah_awal} menjadi {ashlul_masalah_akhir})"
                else:
                    # Radd dengan suami/istri: perhitungan khusus
                    ashlul_masalah_akhir = apply_radd_with_spouse(selected_heirs, ashlul_masalah_awal)
                    status = f"Masalah Radd (dengan Suami/Istri), AM Gabungan: {ashlul_masalah_akhir}"
    
    notes.append(status)
    
    # === INKISAR (TASHIH) ===
    ashlul_masalah_akhir = apply_inkisar(selected_heirs, ashlul_masalah_akhir, notes)
    
    return ashlul_masalah_akhir, status


def apply_radd_with_spouse(selected_heirs: List[Dict], ashlul_masalah_awal: int) -> int:
    """Menerapkan Radd ketika ada suami/istri."""
    
    # Ambil suami/istri
    spouse = next((
        h for h in selected_heirs 
        if h['data'].name_id in ["Suami", "Istri"]
        and h.get('share_fraction_str', '') != 'Mahjub'
    ), None)
    
    if not spouse:
        return ashlul_masalah_awal
    
    # Ambil ahli waris Radd (yang bukan suami/istri dan tidak Mahjub)
    radd_heirs = [
        h for h in selected_heirs 
        if h != spouse 
        and h.get('share_fraction_str', '') != 'Mahjub'
        and '/' in h.get('share_fraction_str', '')
    ]
    
    # Jika tidak ada ahli waris Radd, kembalikan AM awal
    if not radd_heirs:
        return ashlul_masalah_awal
    
    # Hitung AM untuk masalah suami/istri
    spouse_fraction = spouse['share_fraction_str'].split()[0]
    ashlul_masalah_spouse = Fraction(spouse_fraction).denominator
    spouse['saham'] = 1
    remaining_saham_from_spouse_problem = ashlul_masalah_spouse - 1
    
    # Hitung AM untuk masalah Radd
    radd_denominators = []
    for h in radd_heirs:
        frac_str = h['share_fraction_str'].split()[0]
        denominator = Fraction(frac_str).denominator
        radd_denominators.append(denominator)
    
    radd_denominators = sorted(list(set(radd_denominators)))
    ashlul_masalah_radd = math.lcm(*radd_denominators) if radd_denominators else 1
    
    # Hitung total saham grup Radd
    total_saham_radd_group = sum(
        int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_radd) 
        for h in radd_heirs
    )
    
    # Hindari division by zero
    if total_saham_radd_group == 0:
        return ashlul_masalah_awal
    
    # Hitung pengali untuk menggabungkan dua masalah
    common_divisor = math.gcd(remaining_saham_from_spouse_problem, total_saham_radd_group)
    multiplier_spouse_problem = total_saham_radd_group // common_divisor
    multiplier_radd_problem = remaining_saham_from_spouse_problem // common_divisor
    
    # Hitung AM akhir
    ashlul_masalah_akhir = ashlul_masalah_spouse * multiplier_spouse_problem
    
    # Update saham suami/istri
    spouse['saham'] *= multiplier_spouse_problem
    
    # Update saham ahli waris Radd
    for heir in radd_heirs:
        frac_str = heir['share_fraction_str'].split()[0]
        heir['saham'] = int(
            Fraction(frac_str) * ashlul_masalah_radd
        ) * multiplier_radd_problem
    
    return ashlul_masalah_akhir


def apply_inkisar(selected_heirs: List[Dict], ashlul_masalah_akhir: int, 
                  notes: List[str]) -> int:
    """Menerapkan Inkisar (Tashihul Mas'alah) jika diperlukan."""
    from decimal import Decimal
    
    # Cari kelompok yang perlu Inkisar (saham tidak habis dibagi jumlah)
    inkisar_groups = []
    for h in selected_heirs:
        # Skip yang Mahjub
        if h.get('share_fraction_str', '') == 'Mahjub':
            continue
            
        saham_val = h.get('saham', 0)
        if saham_val > 0:
            saham_decimal = Decimal(str(saham_val))
            quantity_decimal = Decimal(str(h['quantity']))
            
            # Jika saham tidak habis dibagi quantity, butuh Inkisar
            if saham_decimal % quantity_decimal != 0:
                inkisar_groups.append(h)
    
    if not inkisar_groups:
        return ashlul_masalah_akhir
    
    # Hitung pengali untuk setiap kelompok
    multipliers = []
    for h in inkisar_groups:
        saham_val = h['saham']
        
        if saham_val == int(saham_val):
            # Saham adalah integer
            saham_int = int(saham_val)
            gcd_val = math.gcd(saham_int, h['quantity'])
            multipliers.append(h['quantity'] // gcd_val)
        else:
            # Saham adalah pecahan
            frac = Fraction(saham_val).limit_denominator(1000)
            multipliers.append(frac.denominator)
    
    # Hitung KPK dari semua pengali
    if multipliers:
        final_multiplier = multipliers[0]
        for m in multipliers[1:]:
            final_multiplier = math.lcm(final_multiplier, m)
        
        if final_multiplier > 1:
            notes.append(
                f"Terjadi Inkisar. Dilakukan Tashihul Mas'alah: "
                f"{ashlul_masalah_akhir} x {final_multiplier} = "
                f"{ashlul_masalah_akhir * final_multiplier}"
            )
            
            # Kalikan AM dengan pengali
            ashlul_masalah_akhir *= final_multiplier
            
            # Kalikan semua saham dengan pengali
            for heir in selected_heirs:
                if heir.get('saham', 0) > 0 and heir.get('share_fraction_str', '') != 'Mahjub':
                    heir['saham'] *= final_multiplier
    
    return ashlul_masalah_akhir


def generate_final_shares(selected_heirs: List[Dict], tirkah: float, 
                          ashlul_masalah_akhir: int) -> List[schemas.HeirShare]:
    """Menghasilkan hasil akhir pembagian warisan."""
    final_shares = []
    
    for heir in selected_heirs:
        final_saham = heir.get('saham', 0)
        
        if abs(final_saham - round(final_saham)) < 0.0001:
            final_saham = round(final_saham)
        
        share_amount = (
            (tirkah / ashlul_masalah_akhir) * final_saham 
            if ashlul_masalah_akhir > 0 
            else 0
        )
        
        final_shares.append(schemas.HeirShare(
            heir=heir['data'],
            quantity=heir['quantity'],
            share_fraction=heir['share_fraction_str'],
            saham=final_saham,
            reason=heir['reason'],
            share_amount=share_amount
        ))
    
    return final_shares
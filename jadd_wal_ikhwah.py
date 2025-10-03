"""
Modul untuk menangani kasus Jadd wal Ikhwah (Kakek bersama Saudara-saudara)
dalam perhitungan warisan Islam (Faraid).

Aturan Jadd wal Ikhwah:
1. Kakek mengambil bagian terbaik dari 3-4 opsi:
   - Muqosamah: Berbagi dengan saudara seperti saudara laki-laki kandung
   - Suds: 1/6 dari total harta (jika ada dzawil furudh lain)
   - Tsuluts: 1/3 dari total harta (jika tidak ada dzawil furudh lain)
   - Tsuluts al-Baqi: 1/3 dari sisa (jika ada dzawil furudh lain)
2. Kakek minimal mendapat 1/6 (Suds) jika ada dzawil furudh lain
3. Saudara seibu tidak termasuk dalam perhitungan ini (sudah diblokir)
"""

from fractions import Fraction
import math
from typing import Dict, List, Any


# Konstanta
IKHWAH_NAMES = [
    "Saudara Laki-laki Kandung", 
    "Saudari Kandung", 
    "Saudara Laki-laki Seayah", 
    "Saudari Seayah"
]

MALE_SIBLING_NAMES = [
    "Saudara Laki-laki Kandung", 
    "Saudara Laki-laki Seayah"
]

FEMALE_SIBLING_NAMES = [
    "Saudari Kandung", 
    "Saudari Seayah"
]


def lcm(a: int, b: int) -> int:
    """
    Menghitung Least Common Multiple (KPK) dari dua karenangan.
    
    Args:
        a: karenangan pertama
        b: karenangan kedua
    
    Returns:
        KPK dari a dan b
    """
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def calculate_jadd_share(
    jadd: Dict[str, Any], 
    ikhwah: List[Dict[str, Any]], 
    other_dzawil_furudh: List[Dict[str, Any]], 
    ashlul_masalah: int
) -> Dict[str, Any]:
    """
    Menghitung bagian Kakek dan Saudara-saudara dalam kasus Jadd wal Ikhwah.
    
    Args:
        jadd: Dictionary berisi data kakek
        ikhwah: List dictionary berisi data saudara-saudara
        other_dzawil_furudh: List dictionary ahli waris dzawil furudh lainnya
        ashlul_masalah: Ashlul Mas'alah awal
    
    Returns:
        Dictionary berisi:
        - tashih_multiplier: Pengganda untuk tashih
        - chosen_option: Opsi terbaik yang dipilih
        - jadd_saham: Saham kakek
        - ikhwah_shares: Dictionary saham untuk setiap saudara
    """
    
    # Validasi input
    if not jadd or not ikhwah:
        return {
            "tashih_multiplier": 1,
            "chosen_option": "Tidak ada Jadd atau Ikhwah",
            "jadd_saham": 0,
            "ikhwah_shares": {}
        }
    
    if ashlul_masalah <= 0:
        raise ValueError("Ashlul Masalah harus lebih besar dari 0")
    
    # Hitung saham dzawil furudh lainnya
    saham_dzawil_furudh = sum(h.get('saham', 0) for h in other_dzawil_furudh)
    remaining_saham = ashlul_masalah - saham_dzawil_furudh
    
    # Validasi sisa saham
    if remaining_saham <= 0:
        return {
            "tashih_multiplier": 1,
            "chosen_option": "Tidak ada sisa untuk Jadd dan Ikhwah",
            "jadd_saham": 0,
            "ikhwah_shares": {h['data'].id: 0 for h in ikhwah}
        }
    
    # ========== TAHAP 1: HITUNG SEMUA OPSI ==========
    options = {}
    
    # Opsi 1: Muqosamah (Berbagi dengan saudara)
    # Kakek dihitung sebagai 2 kepala (seperti saudara laki-laki)
    muqosamah_heads = calculate_muqosamah_heads(jadd, ikhwah)
    if muqosamah_heads > 0:
        options["Muqosamah"] = (remaining_saham * 2) / muqosamah_heads
    
    # Opsi lainnya tergantung ada tidaknya dzawil furudh lain
    if other_dzawil_furudh:
        # Ada dzawil furudh lain
        options["Suds"] = ashlul_masalah / 6  # 1/6 dari total
        options["Tsuluts al-Baqi"] = remaining_saham / 3  # 1/3 dari sisa
    else:
        # Tidak ada dzawil furudh lain
        options["Tsuluts"] = ashlul_masalah / 3  # 1/3 dari total
    
    # ========== TAHAP 2: PILIH OPSI TERBAIK ==========
    best_option_name = max(options, key=options.get)
    jadd_final_saham = options[best_option_name]
    
    # Aturan minimum: Kakek minimal dapat 1/6 jika ada dzawil furudh lain
    if other_dzawil_furudh and jadd_final_saham < (ashlul_masalah / 6):
        jadd_final_saham = ashlul_masalah / 6
        best_option_name = "Suds (minimum)"
    
    # ========== TAHAP 3: HITUNG SAHAM IKHWAH ==========
    saham_for_ikhwah = remaining_saham - jadd_final_saham
    
    # Validasi saham ikhwah tidak negatif
    if saham_for_ikhwah < 0:
        saham_for_ikhwah = 0
    
    # ========== TAHAP 4: TASHIH INTERNAL (jika ada pecahan) ==========
    tashih_multiplier = calculate_tashih_multiplier(
        jadd_final_saham, 
        saham_for_ikhwah
    )
    
    # Terapkan tashih
    jadd_saham_int = round(jadd_final_saham * tashih_multiplier)
    saham_for_ikhwah_int = round(saham_for_ikhwah * tashih_multiplier)
    
    # ========== TAHAP 5: DISTRIBUSI KE IKHWAH ==========
    ikhwah_shares = distribute_ikhwah_shares(
        ikhwah, 
        saham_for_ikhwah_int, 
        tashih_multiplier
    )
    
    # Jika terjadi inkisar tambahan saat distribusi ke ikhwah
    if ikhwah_shares.get('additional_multiplier', 1) > 1:
        additional_multiplier = ikhwah_shares['additional_multiplier']
        tashih_multiplier *= additional_multiplier
        jadd_saham_int *= additional_multiplier
        # Update saham ikhwah sudah dilakukan di dalam fungsi
    
    return {
        "tashih_multiplier": tashih_multiplier,
        "chosen_option": best_option_name,
        "jadd_saham": jadd_saham_int,
        "ikhwah_shares": ikhwah_shares.get('shares', {}),
        "options_calculated": options  # Untuk debugging
    }


def calculate_muqosamah_heads(
    jadd: Dict[str, Any], 
    ikhwah: List[Dict[str, Any]]
) -> int:
    """
    Menghitung jumlah 'kepala' untuk opsi Muqosamah.
    - Kakek = 2 kepala
    - Saudara laki-laki = 2 kepala
    - Saudari perempuan = 1 kepala
    
    Args:
        jadd: Dictionary berisi data kakek
        ikhwah: List dictionary berisi data saudara-saudara
    
    Returns:
        Total jumlah kepala
    """
    # Kakek dihitung sebagai 2 kepala
    total_heads = 2
    
    # Hitung kepala dari saudara-saudara
    for heir in ikhwah:
        name = heir['data'].name_id
        quantity = heir['quantity']
        
        if name in MALE_SIBLING_NAMES:
            # Saudara laki-laki = 2 kepala per orang
            total_heads += 2 * quantity
        elif name in FEMALE_SIBLING_NAMES:
            # Saudari perempuan = 1 kepala per orang
            total_heads += 1 * quantity
    
    return total_heads


def calculate_tashih_multiplier(
    jadd_saham: float, 
    ikhwah_saham: float
) -> int:
    """
    Menghitung tashih multiplier untuk menghilangkan pecahan.
    
    Args:
        jadd_saham: Saham kakek (bisa float)
        ikhwah_saham: Saham saudara-saudara (bisa float)
    
    Returns:
        Multiplier untuk tashih
    """
    denominators = []
    
    # Cek apakah jadd_saham adalah pecahan
    if isinstance(jadd_saham, float) and not jadd_saham.is_integer():
        frac = Fraction(jadd_saham).limit_denominator(1000)
        denominators.append(frac.denominator)
    
    # Cek apakah ikhwah_saham adalah pecahan
    if isinstance(ikhwah_saham, float) and not ikhwah_saham.is_integer():
        frac = Fraction(ikhwah_saham).limit_denominator(1000)
        denominators.append(frac.denominator)
    
    # Jika tidak ada pecahan, tidak perlu tashih
    if not denominators:
        return 1
    
    # Hitung LCM dari semua denominator
    tashih_multiplier = denominators[0]
    for d in denominators[1:]:
        tashih_multiplier = lcm(tashih_multiplier, d)
    
    return tashih_multiplier


def distribute_ikhwah_shares(
    ikhwah: List[Dict[str, Any]], 
    saham_for_ikhwah: int,
    current_multiplier: int
) -> Dict[str, Any]:
    """
    Mendistribusikan saham ke saudara-saudara dengan prinsip 2:1 (laki:perempuan).
    
    Args:
        ikhwah: List dictionary berisi data saudara-saudara
        saham_for_ikhwah: Total saham untuk saudara-saudara
        current_multiplier: Multiplier yang sudah diterapkan sebelumnya
    
    Returns:
        Dictionary berisi shares dan additional_multiplier jika perlu
    """
    ikhwah_shares = {}
    
    # Hitung total kepala saudara
    ikhwah_heads = 0
    for heir in ikhwah:
        name = heir['data'].name_id
        quantity = heir['quantity']
        
        if name in MALE_SIBLING_NAMES:
            ikhwah_heads += 2 * quantity
        elif name in FEMALE_SIBLING_NAMES:
            ikhwah_heads += 1 * quantity
    
    # Validasi
    if ikhwah_heads == 0:
        return {
            "shares": {},
            "additional_multiplier": 1
        }
    
    if saham_for_ikhwah <= 0:
        return {
            "shares": {h['data'].id: 0 for h in ikhwah},
            "additional_multiplier": 1
        }
    
    # ========== CEK APAKAH PERLU INKISAR TAMBAHAN ==========
    additional_multiplier = 1
    
    # Jika saham tidak habis dibagi dengan jumlah kepala
    if saham_for_ikhwah % ikhwah_heads != 0:
        gcd_val = math.gcd(saham_for_ikhwah, ikhwah_heads)
        additional_multiplier = ikhwah_heads // gcd_val
        saham_for_ikhwah *= additional_multiplier
    
    # ========== DISTRIBUSI SAHAM ==========
    saham_per_head = saham_for_ikhwah / ikhwah_heads
    
    for heir in ikhwah:
        name = heir['data'].name_id
        quantity = heir['quantity']
        
        if name in MALE_SIBLING_NAMES:
            # Saudara laki-laki mendapat 2x per kepala
            head_count = 2
        elif name in FEMALE_SIBLING_NAMES:
            # Saudari perempuan mendapat 1x per kepala
            head_count = 1
        else:
            head_count = 0
        
        # Hitung saham untuk ahli waris ini
        heir_saham = saham_per_head * head_count * quantity
        ikhwah_shares[heir['data'].id] = int(round(heir_saham))
    
    return {
        "shares": ikhwah_shares,
        "additional_multiplier": additional_multiplier
    }


def get_detailed_explanation(
    jadd: Dict[str, Any],
    ikhwah: List[Dict[str, Any]],
    result: Dict[str, Any],
    ashlul_masalah: int
) -> str:
    """
    Menghasilkan penjelasan detail tentang perhitungan Jadd wal Ikhwah.
    
    Args:
        jadd: Dictionary berisi data kakek
        ikhwah: List dictionary berisi data saudara-saudara
        result: Hasil dari calculate_jadd_share
        ashlul_masalah: Ashlul Mas'alah
    
    Returns:
        String penjelasan detail
    """
    explanation = []
    
    explanation.append("=== PERHITUNGAN JADD WAL IKHWAH ===\n")
    
    # Info ahli waris
    explanation.append(f"Kakek: 1 orang")
    explanation.append(f"Saudara-saudara:")
    for heir in ikhwah:
        explanation.append(f"  - {heir['data'].name_id}: {heir['quantity']} orang")
    
    explanation.append(f"\nAshlul Mas'alah Awal: {ashlul_masalah}")
    
    # Opsi yang dihitung
    if 'options_calculated' in result:
        explanation.append("\nOpsi yang dihitung:")
        for option_name, option_value in result['options_calculated'].items():
            explanation.append(f"  - {option_name}: {option_value:.4f} saham")
    
    # Opsi terpilih
    explanation.append(f"\nOpsi Terbaik: {result['chosen_option']}")
    explanation.append(f"Saham Kakek: {result['jadd_saham']}")
    
    # Saham saudara
    explanation.append("\nSaham Saudara-saudara:")
    for heir in ikhwah:
        heir_id = heir['data'].id
        heir_saham = result['ikhwah_shares'].get(heir_id, 0)
        explanation.append(f"  - {heir['data'].name_id}: {heir_saham} saham")
    
    # Tashih
    if result['tashih_multiplier'] > 1:
        explanation.append(f"\nTashih Multiplier: {result['tashih_multiplier']}")
        explanation.append(
            f"Ashlul Mas'alah setelah Tashih: "
            f"{ashlul_masalah * result['tashih_multiplier']}"
        )
    
    return "\n".join(explanation)


# ========== FUNGSI VALIDASI DAN HELPER ==========

def validate_jadd_wal_ikhwah_case(
    selected_heirs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Memvalidasi apakah kasus adalah Jadd wal Ikhwah yang valid.
    
    Args:
        selected_heirs: List semua ahli waris
    
    Returns:
        Dictionary berisi:
        - is_valid: Boolean
        - jadd: Data kakek (jika ada)
        - ikhwah: List data saudara (jika ada)
        - reason: Alasan jika tidak valid
    """
    jadd = None
    ikhwah = []
    
    for heir in selected_heirs:
        name = heir['data'].name_id
        
        if name == "Kakek":
            jadd = heir
        elif name in IKHWAH_NAMES:
            ikhwah.append(heir)
    
    # Validasi
    if not jadd:
        return {
            "is_valid": False,
            "reason": "Tidak ada Kakek"
        }
    
    if not ikhwah:
        return {
            "is_valid": False,
            "reason": "Tidak ada saudara"
        }
    
    # Cek apakah ada Ayah (yang akan memblokir kakek dan saudara)
    has_father = any(
        h['data'].name_id == "Ayah" 
        for h in selected_heirs
    )
    
    if has_father:
        return {
            "is_valid": False,
            "reason": "Ada Ayah (Kakek dan Saudara ter-mahjub)"
        }
    
    return {
        "is_valid": True,
        "jadd": jadd,
        "ikhwah": ikhwah,
        "reason": "Valid"
    }


def get_ikhwah_type(heir_name: str) -> str:
    """
    Mendapatkan tipe saudara (Kandung/Seayah, Laki-laki/Perempuan).
    
    Args:
        heir_name: Nama ahli waris
    
    Returns:
        String tipe saudara
    """
    if heir_name == "Saudara Laki-laki Kandung":
        return "Laki-laki Kandung"
    elif heir_name == "Saudari Kandung":
        return "Perempuan Kandung"
    elif heir_name == "Saudara Laki-laki Seayah":
        return "Laki-laki Seayah"
    elif heir_name == "Saudari Seayah":
        return "Perempuan Seayah"
    else:
        return "Unknown"


# ========== TESTING HELPER ==========

def test_calculate_jadd_share():
    """
    Fungsi untuk testing perhitungan Jadd wal Ikhwah.
    """
    # Mock data untuk testing
    class MockHeir:
        def __init__(self, id, name_id):
            self.id = id
            self.name_id = name_id
    
    # Test Case 1: Kakek + 2 Saudara Laki-laki Kandung
    print("Test Case 1: Kakek + 2 Saudara Laki-laki Kandung")
    print("-" * 50)
    
    jadd = {
        'data': MockHeir(1, "Kakek"),
        'quantity': 1
    }
    
    ikhwah = [
        {
            'data': MockHeir(2, "Saudara Laki-laki Kandung"),
            'quantity': 2
        }
    ]
    
    other_dzawil_furudh = []
    ashlul_masalah = 6
    
    result = calculate_jadd_share(jadd, ikhwah, other_dzawil_furudh, ashlul_masalah)
    
    print(f"Opsi Terpilih: {result['chosen_option']}")
    print(f"Saham Kakek: {result['jadd_saham']}")
    print(f"Saham Saudara: {result['ikhwah_shares']}")
    print(f"Tashih Multiplier: {result['tashih_multiplier']}")
    print(f"Opsi yang dihitung: {result.get('options_calculated', {})}")
    print()
    
    # Test Case 2: Kakek + 1 Saudari Kandung + Istri
    print("Test Case 2: Kakek + 1 Saudari Kandung + Istri")
    print("-" * 50)
    
    jadd = {
        'data': MockHeir(1, "Kakek"),
        'quantity': 1
    }
    
    ikhwah = [
        {
            'data': MockHeir(3, "Saudari Kandung"),
            'quantity': 1
        }
    ]
    
    other_dzawil_furudh = [
        {
            'data': MockHeir(4, "Istri"),
            'quantity': 1,
            'saham': 1.5  # 1/4 dari 6
        }
    ]
    
    ashlul_masalah = 6
    
    result = calculate_jadd_share(jadd, ikhwah, other_dzawil_furudh, ashlul_masalah)
    
    print(f"Opsi Terpilih: {result['chosen_option']}")
    print(f"Saham Kakek: {result['jadd_saham']}")
    print(f"Saham Saudara: {result['ikhwah_shares']}")
    print(f"Tashih Multiplier: {result['tashih_multiplier']}")
    print(f"Opsi yang dihitung: {result.get('options_calculated', {})}")


if __name__ == "__main__":
    # Jalankan test jika file dijalankan langsung
    test_calculate_jadd_share()
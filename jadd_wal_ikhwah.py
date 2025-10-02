# Di dalam file: jadd_wal_ikhwah.py

from fractions import Fraction

IKHWAH_NAMES = ["Saudara Laki-laki Kandung", "Saudari Kandung", "Saudara Laki-laki Seayah", "Saudari Seayah"]
MALE_SIBLING_NAMES = ["Saudara Laki-laki Kandung", "Saudara Laki-laki Seayah"]

def calculate_jadd_share(jadd, ikhwah, other_dzawil_furudh, ashlul_masalah):
    """
    Fungsi utama untuk menghitung bagian terbaik bagi Kakek saat bersama saudara.
    """
    
    # --- TAHAP 1: Hitung Sisa Saham ---
    saham_dzawil_furudh = sum(h.get('saham', 0) for h in other_dzawil_furudh)
    remaining_saham = ashlul_masalah - saham_dzawil_furudh

    if remaining_saham <= 0:
        # Jika tidak ada sisa, Kakek hanya bisa dapat 1/6 jika dia Ashabul Furudh
        jadd_saham = int(Fraction(1, 6) * ashlul_masalah) if ashlul_masalah > total_fardh_saham else 0
        return { "chosen_option": "Suds (dari Fardh)", "jadd_saham": jadd_saham, "ikhwah_shares": {} }

    # --- TAHAP 2: Hitung Semua Opsi untuk Kakek ---
    options = {}
    
    # Opsi 1: Muqosamah (Berbagi Sisa)
    muqosamah_heads = 2 # Kakek dihitung 2 kepala (seperti saudara laki-laki)
    for heir in ikhwah:
        is_male = heir['data'].name_id in MALE_SIBLING_NAMES
        head_count = 2 if is_male else 1
        muqosamah_heads += head_count * heir['quantity']
    
    if muqosamah_heads > 0:
        options["Muqosamah"] = (remaining_saham * 2) / muqosamah_heads

    # Cek skenario A (tanpa dzawil furudh lain) atau B (dengan dzawil furudh lain)
    if other_dzawil_furudh:
        options["Suds"] = ashlul_masalah * Fraction(1, 6)
        options["Tsuluts al-Baqi"] = remaining_saham * Fraction(1, 3)
    else:
        options["Tsuluts"] = ashlul_masalah * Fraction(1, 3)

    # --- TAHAP 3: Pilih Opsi Terbaik ---
    best_option_name = max(options, key=options.get)
    jadd_final_saham = options[best_option_name]

    # Pastikan bagian kakek tidak kurang dari 1/6 jika ada dzawil furudh
    if other_dzawil_furudh:
        suds_saham = ashlul_masalah * Fraction(1, 6)
        if jadd_final_saham < suds_saham:
            jadd_final_saham = suds_saham
            best_option_name = "Suds (minimum)"

    # --- TAHAP 4: Bagikan Sisa ke Ikhwah ---
    saham_for_ikhwah = remaining_saham - jadd_final_saham
    ikhwah_shares = {}
    
    ikhwah_heads = sum((2 if h['data'].name_id in MALE_SIBLING_NAMES else 1) * h['quantity'] for h in ikhwah)

    if saham_for_ikhwah > 0 and ikhwah_heads > 0:
        for heir in ikhwah:
            is_male = heir['data'].name_id in MALE_SIBLING_NAMES
            head_count = 2 if is_male else 1
            heir['saham'] = (saham_for_ikhwah * head_count) / ikhwah_heads * heir['quantity']
            ikhwah_shares[heir['data'].id] = heir['saham']

    return {
        "chosen_option": best_option_name,
        "jadd_saham": jadd_final_saham,
        "ikhwah_shares": ikhwah_shares
    }
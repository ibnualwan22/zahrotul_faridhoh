# Di dalam file: test_calculator.py

import pytest
from calculator import calculate_inheritance
from schemas import CalculationInput, HeirInput
from database import SessionLocal

# --- Fungsi Pembantu Universal untuk Tes ---
def run_test(heirs_input, expected_am_akhir=None, expected_saham=None, expected_fractions=None):
    """Fungsi pembantu untuk menjalankan tes dan memeriksa hasil yang beragam."""
    db = SessionLocal()
    # Tirkah tidak relevan untuk tes logika, cukup pakai angka dummy
    input_data = CalculationInput(heirs=heirs_input, tirkah=1000)
    result = calculate_inheritance(db, input_data)
    db.close()

    if expected_am_akhir:
        assert result.ashlul_masalah_akhir == expected_am_akhir, f"Ashlul Masalah Akhir salah. Harusnya {expected_am_akhir}, tapi hasilnya {result.ashlul_masalah_akhir}"
    
    if expected_saham:
        for heir_name, sahm in expected_saham.items():
            share_obj = next((s for s in result.shares if s.heir.name_id == heir_name), None)
            assert share_obj is not None, f"Ahli waris '{heir_name}' tidak ditemukan di hasil."
            assert share_obj.saham == sahm, f"Saham untuk '{heir_name}' salah. Harusnya {sahm}, tapi hasilnya {share_obj.saham}"
    
    if expected_fractions:
        for heir_name, fraction in expected_fractions.items():
            share_obj = next((s for s in result.shares if s.heir.name_id == heir_name), None)
            assert share_obj is not None, f"Ahli waris '{heir_name}' tidak ditemukan di hasil."
            assert share_obj.share_fraction == fraction, f"Bagian untuk '{heir_name}' salah. Harusnya {fraction}, tapi hasilnya {share_obj.share_fraction}"

# --- Kumpulan Skenario Uji Coba ---

# === TES DASAR FURUDH ===
def test_suami_tanpa_keturunan():
    run_test(heirs_input=[HeirInput(id=3), HeirInput(id=18)], expected_fractions={"Suami": "1/2"})

def test_suami_dengan_keturunan():
    run_test(heirs_input=[HeirInput(id=3), HeirInput(id=16)], expected_fractions={"Suami": "1/4"})

def test_istri_tanpa_keturunan():
    run_test(heirs_input=[HeirInput(id=4), HeirInput(id=18)], expected_fractions={"Istri": "1/4"})

def test_istri_dengan_keturunan():
    run_test(heirs_input=[HeirInput(id=4), HeirInput(id=16)], expected_fractions={"Istri": "1/8"})

def test_ibu_sepertiga():
    run_test(heirs_input=[HeirInput(id=18), HeirInput(id=3)], expected_fractions={"Ibu": "1/3"})

def test_ibu_seperenam_karena_anak():
    run_test(heirs_input=[HeirInput(id=18), HeirInput(id=16)], expected_fractions={"Ibu": "1/6"})

def test_ibu_seperenam_karena_saudara():
    run_test(heirs_input=[HeirInput(id=18), HeirInput(id=7, quantity=2)], expected_fractions={"Ibu": "1/6"})

def test_anak_perempuan_satu():
    run_test(heirs_input=[HeirInput(id=16)], expected_fractions={"Anak Perempuan": "1/2"})

def test_anak_perempuan_banyak():
    run_test(heirs_input=[HeirInput(id=16, quantity=2)], expected_fractions={"Anak Perempuan": "2/3"})

def test_saudara_seibu_satu():
    run_test(heirs_input=[HeirInput(id=9)], expected_fractions={"Saudara Laki-laki Seibu": "1/6"})
    
def test_saudara_seibu_banyak():
    run_test(heirs_input=[HeirInput(id=9, quantity=2)], expected_fractions={"Saudara Laki-laki Seibu": "1/3 (berbagi)"})

# === TES HAJB (PENGHALANG) ===
def test_hajb_kakek_oleh_ayah():
    run_test(heirs_input=[HeirInput(id=6), HeirInput(id=2)], expected_fractions={"Kakek": "Mahjub"})

def test_hajb_nenek_oleh_ibu():
    run_test(heirs_input=[HeirInput(id=19), HeirInput(id=18)], expected_fractions={"Nenek dari Ibu": "Mahjub"})

def test_hajb_cucu_oleh_anak_laki():
    run_test(heirs_input=[HeirInput(id=5), HeirInput(id=1)], expected_fractions={"Cucu Laki-laki": "Mahjub"})

def test_hajb_saudara_oleh_ayah():
    run_test(heirs_input=[HeirInput(id=2), HeirInput(id=7)], expected_fractions={"Saudara Laki-laki Kandung": "Mahjub"})

# === TES ASHOBAH ===
def test_ashobah_bin_nafsi_anak_laki():
    run_test(heirs_input=[HeirInput(id=1)], expected_fractions={"Anak Laki-laki": "Sisa"})

def test_ashobah_bil_ghair_anak():
    run_test(heirs_input=[HeirInput(id=1), HeirInput(id=16)], expected_fractions={"Anak Perempuan": "Sisa"})

def test_ashobah_maal_ghair_saudari():
    run_test(heirs_input=[HeirInput(id=21), HeirInput(id=16)], expected_fractions={"Saudari Kandung": "Sisa"})

def test_ashobah_bis_sabab_mutiq():
    run_test(heirs_input=[HeirInput(id=4), HeirInput(id=24)], expected_fractions={"Pria Pembebas Budak": "Sisa"})

def test_ashobah_bis_sabab_mahjub():
    run_test(heirs_input=[HeirInput(id=4), HeirInput(id=12), HeirInput(id=24)], expected_fractions={"Pria Pembebas Budak": "Mahjub"})

# === TES TAKMILAH (PELENGKAP 1/6) ===
def test_takmilah_cucu_perempuan():
    run_test(heirs_input=[HeirInput(id=16), HeirInput(id=17)], expected_fractions={"Cucu Perempuan": "1/6"})

def test_takmilah_saudari_seayah():
    run_test(heirs_input=[HeirInput(id=21), HeirInput(id=22)], expected_fractions={"Saudari Seayah": "1/6"})

# === TES KASUS ISTIMEWA ===
def test_gharrawain_dengan_suami():
    run_test(heirs_input=[HeirInput(id=3), HeirInput(id=18), HeirInput(id=2)], expected_saham={"Suami": 3, "Ibu": 1, "Ayah": 2})

def test_musytarakah():
    run_test(
        heirs_input=[HeirInput(id=3), HeirInput(id=18), HeirInput(id=9, quantity=2), HeirInput(id=7)],
        expected_am_akhir=18,
        expected_saham={"Suami": 9, "Ibu": 3, "Saudara Laki-laki Seibu": 4, "Saudara Laki-laki Kandung": 2}
    )

# === TES INKISAR ===
def test_inkisar_satu_kelompok_muwafaqoh():
    run_test(
        heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=6)],
        expected_am_akhir=9,
        expected_saham={"Ibu": 3, "Paman Kandung": 6}
    )

def test_inkisar_satu_kelompok_mubayanah():
    run_test(
        heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=5)],
        expected_am_akhir=15,
        expected_saham={"Ibu": 5, "Paman Kandung": 10}
    )
# Di dalam file: test_calculator.py

def test_jadd_wal_ikhwah_kasus_kitab():
    """
    Tes Kasus Jadd wal Ikhwah: Suami, Ibu, Kakek, 2 Sdri Kandung.
    AM=6. Suami=3, Ibu=1. Sisa=2.
    Pilihan Kakek: Suds(1), Tsuluts Baqi(0.67), Muqosamah(1).
    Terbaik adalah Suds/Muqosamah (1 saham). Sisa 1 saham untuk 2 Sdri.
    Terjadi Inkisar. Pengali = 2. Tashih AM = 6x2=12.
    Saham: Suami=6, Ibu=2, Kakek=2, 2 Sdri=2 (@1).
    """
    run_test(
        heirs_input=[
            HeirInput(id=3), HeirInput(id=18),
            HeirInput(id=6), HeirInput(id=21, quantity=2)
        ],
        expected_am_akhir=12,
        expected_saham={"Suami": 6, "Ibu": 2, "Kakek": 2, "Saudari Kandung": 2}
    )
    
@pytest.fixture(scope="session")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

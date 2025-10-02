# Di dalam file: test_inkisar.py

import pytest
from calculator import calculate_inheritance
from schemas import CalculationInput, HeirInput
from database import SessionLocal

db = SessionLocal()

def run_inkisar_test(heirs_input, expected_am_akhir, expected_saham):
    """Fungsi pembantu khusus untuk tes inkisar."""
    input_data = CalculationInput(heirs=heirs_input, tirkah=100)
    result = calculate_inheritance(db, input_data)
    
    assert result.ashlul_masalah_akhir == expected_am_akhir
    for heir_name, sahm in expected_saham.items():
        share_obj = next(s for s in result.shares if s.heir.name_id == heir_name)
        assert share_obj.saham == sahm

# Kasus 1: 1 Kelompok, Hubungan Muwafaqoh
def test_inkisar_satu_kelompok_muwafaqoh():
    # Skenario: Ibu dan 6 Paman. Saham paman (2) tidak bisa dibagi 6.
    # FPB(2,6)=2. Pengali = 6/2=3. AM Baru = 3x3=9.
    run_inkisar_test(
        heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=6)],
        expected_am_akhir=9,
        expected_saham={"Ibu": 3, "Paman Kandung": 6}
    )

# Kasus 2: 1 Kelompok, Hubungan Mubayanah
def test_inkisar_satu_kelompok_mubayanah():
    # Skenario: Ibu dan 5 Paman. Saham paman (2) tidak bisa dibagi 5.
    # FPB(2,5)=1. Pengali = 5/1=5. AM Baru = 3x5=15.
    run_inkisar_test(
        heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=5)],
        expected_am_akhir=15,
        expected_saham={"Ibu": 5, "Paman Kandung": 10}
    )

# Kasus 3: >1 Kelompok, Hubungan Mumatsalah
def test_inkisar_multi_kelompok_mumatsalah():
    # Skenario: Istri, 6 Nenek, 3 Paman. AM=12. Nenek (saham 2), Paman (saham 7).
    # Nenek: saham 2, orang 6 -> Muwafaqoh, pengali 3.
    # Paman: saham 7, orang 3 -> Mubayanah, pengali 3.
    # Pengali (3) dan (3) -> Mumatsalah. Pengali Final = 3. AM Baru = 12x3=36.
    run_inkisar_test(
        heirs_input=[HeirInput(id=4), HeirInput(id=20, quantity=6), HeirInput(id=12, quantity=3)],
        expected_am_akhir=36,
        expected_saham={"Istri": 9, "Nenek dari Ayah": 6, "Paman Kandung": 21}
    )

# Kasus 4: >1 Kelompok, Hubungan Kompleks (Muwafaqoh, Mubayanah, Mudakholah)
def test_inkisar_multi_kelompok_kompleks():
    # Skenario: 4 Istri, 6 Nenek, 5 Anak Pr, 3 Paman. AM=24.
    # Istri: s3, o4 -> Mubayanah, p4.
    # Nenek: s4, o6 -> Muwafaqoh, p3.
    # Anak Pr: s16, o5 -> Mubayanah, p5.
    # Paman: s1, o3 -> Mubayanah, p3.
    # Pengali: 4, 3, 5, 3. KPK-nya adalah 60. AM Baru = 24x60=1440.
    run_inkisar_test(
        heirs_input=[
            HeirInput(id=4, quantity=4), HeirInput(id=20, quantity=6),
            HeirInput(id=16, quantity=5), HeirInput(id=12, quantity=3)
        ],
        expected_am_akhir=1440,
        expected_saham={"Istri": 180, "Nenek dari Ayah": 240, "Anak Perempuan": 960, "Paman Kandung": 60}
    )

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """Cleanup a testing session."""
    def close_db():
        db.close()
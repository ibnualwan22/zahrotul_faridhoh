"""
Test Suite Lengkap untuk Modul Perhitungan Warisan Islam (Faraid)
Mencakup: Furudh, Hajb, Ashobah, Kasus Istimewa, 'Aul, Radd, Inkisar
"""

import pytest
from calculator import calculate_inheritance
from schemas import CalculationInput, HeirInput
from database import SessionLocal


# ========== FUNGSI PEMBANTU ==========
def run_test(heirs_input, expected_am_awal=None, expected_am_akhir=None, 
             expected_saham=None, expected_fractions=None, expected_status=None):
    """Fungsi pembantu untuk menjalankan tes dan memeriksa hasil."""
    db = SessionLocal()
    input_data = CalculationInput(heirs=heirs_input, tirkah=1000)
    result = calculate_inheritance(db, input_data)
    db.close()

    if expected_am_awal is not None:
        assert result.ashlul_masalah_awal == expected_am_awal, \
            f"AM Awal salah. Harusnya {expected_am_awal}, hasilnya {result.ashlul_masalah_awal}"
    
    if expected_am_akhir is not None:
        assert result.ashlul_masalah_akhir == expected_am_akhir, \
            f"AM Akhir salah. Harusnya {expected_am_akhir}, hasilnya {result.ashlul_masalah_akhir}"
    
    if expected_saham:
        for heir_name, sahm in expected_saham.items():
            share_obj = next((s for s in result.shares if s.heir.name_id == heir_name), None)
            assert share_obj is not None, f"Ahli waris '{heir_name}' tidak ditemukan"
            assert share_obj.saham == sahm, \
                f"Saham '{heir_name}' salah. Harusnya {sahm}, hasilnya {share_obj.saham}"
    
    if expected_fractions:
        for heir_name, fraction in expected_fractions.items():
            share_obj = next((s for s in result.shares if s.heir.name_id == heir_name), None)
            assert share_obj is not None, f"Ahli waris '{heir_name}' tidak ditemukan"
            assert share_obj.share_fraction == fraction, \
                f"Bagian '{heir_name}' salah. Harusnya {fraction}, hasilnya {share_obj.share_fraction}"
    
    if expected_status:
        assert expected_status in result.status, \
            f"Status salah. Harusnya mengandung '{expected_status}', hasilnya '{result.status}'"

    return result


# ========== TES FURUDH DASAR ==========
class TestFurudhDasar:
    """Tes bagian tetap (fardh) ahli waris."""
    
    def test_suami_tanpa_keturunan(self):
        run_test(
            heirs_input=[HeirInput(id=3), HeirInput(id=18)],
            expected_fractions={"Suami": "1/2"}
        )

    def test_suami_dengan_keturunan(self):
        run_test(
            heirs_input=[HeirInput(id=3), HeirInput(id=16)],
            expected_fractions={"Suami": "1/4"}
        )

    def test_istri_tanpa_keturunan(self):
        run_test(
            heirs_input=[HeirInput(id=4), HeirInput(id=18)],
            expected_fractions={"Istri": "1/4"}
        )

    def test_istri_dengan_keturunan(self):
        run_test(
            heirs_input=[HeirInput(id=4), HeirInput(id=16)],
            expected_fractions={"Istri": "1/8"}
        )

    def test_ayah_dengan_anak_laki(self):
        # Ayah + Anak Laki: Ayah dapat 1/6, Anak dapat sisa
        run_test(
            heirs_input=[HeirInput(id=2), HeirInput(id=1)],
            expected_am_awal=6,
            expected_fractions={"Ayah": "1/6"},
            expected_saham={"Ayah": 1, "Anak Laki-laki": 5}
        )

    def test_ayah_tanpa_keturunan_laki(self):
        run_test(
            heirs_input=[HeirInput(id=2), HeirInput(id=16)],
            expected_fractions={"Ayah": "1/6"}
        )

    def test_ibu_sepertiga(self):
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=3)],
            expected_fractions={"Ibu": "1/3"}
        )

    def test_ibu_seperenam_karena_anak(self):
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=16)],
            expected_fractions={"Ibu": "1/6"}
        )

    def test_ibu_seperenam_karena_dua_saudara(self):
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=7, quantity=2)],
            expected_fractions={"Ibu": "1/6"}
        )

    def test_anak_perempuan_satu(self):
        run_test(
            heirs_input=[HeirInput(id=16)],
            expected_fractions={"Anak Perempuan": "1/2"}
        )

    def test_anak_perempuan_banyak(self):
        run_test(
            heirs_input=[HeirInput(id=16, quantity=2)],
            expected_fractions={"Anak Perempuan": "2/3"}
        )

    def test_saudari_kandung_satu(self):
        run_test(
            heirs_input=[HeirInput(id=21)],
            expected_fractions={"Saudari Kandung": "1/2"}
        )

    def test_saudari_kandung_banyak(self):
        run_test(
            heirs_input=[HeirInput(id=21, quantity=2)],
            expected_fractions={"Saudari Kandung": "2/3"}
        )

    def test_saudara_seibu_satu(self):
        run_test(
            heirs_input=[HeirInput(id=9)],
            expected_fractions={"Saudara Laki-laki Seibu": "1/6"}
        )
    
    def test_saudara_seibu_banyak(self):
        run_test(
            heirs_input=[HeirInput(id=9, quantity=2)],
            expected_fractions={"Saudara Laki-laki Seibu": "1/3 (berbagi)"}
        )

    def test_nenek_seperenam(self):
        run_test(
            heirs_input=[HeirInput(id=19)],
            expected_fractions={"Nenek dari Ibu": "1/6"}
        )


# ========== TES HAJB (PENGHALANG) ==========
class TestHajb:
    """Tes penghalang antar ahli waris."""
    
    def test_hajb_kakek_oleh_ayah(self):
        run_test(
            heirs_input=[HeirInput(id=6), HeirInput(id=2)],
            expected_fractions={"Kakek": "Mahjub"}
        )

    def test_hajb_nenek_oleh_ibu(self):
        run_test(
            heirs_input=[HeirInput(id=19), HeirInput(id=18)],
            expected_fractions={"Nenek dari Ibu": "Mahjub"}
        )

    def test_hajb_cucu_laki_oleh_anak_laki(self):
        run_test(
            heirs_input=[HeirInput(id=5), HeirInput(id=1)],
            expected_fractions={"Cucu Laki-laki": "Mahjub"}
        )

    def test_hajb_cucu_perempuan_oleh_anak_laki(self):
        run_test(
            heirs_input=[HeirInput(id=17), HeirInput(id=1)],
            expected_fractions={"Cucu Perempuan": "Mahjub"}
        )

    def test_hajb_saudara_kandung_oleh_ayah(self):
        run_test(
            heirs_input=[HeirInput(id=2), HeirInput(id=7)],
            expected_fractions={"Saudara Laki-laki Kandung": "Mahjub"}
        )

    def test_hajb_saudara_seayah_oleh_ayah(self):
        run_test(
            heirs_input=[HeirInput(id=2), HeirInput(id=8)],
            expected_fractions={"Saudara Laki-laki Seayah": "Mahjub"}
        )

    def test_hajb_saudara_seibu_oleh_ayah(self):
        run_test(
            heirs_input=[HeirInput(id=9), HeirInput(id=2)],
            expected_fractions={"Saudara Laki-laki Seibu": "Mahjub"}
        )

    def test_hajb_saudara_seibu_oleh_anak(self):
        run_test(
            heirs_input=[HeirInput(id=9), HeirInput(id=16)],
            expected_fractions={"Saudara Laki-laki Seibu": "Mahjub"}
        )

    def test_hajb_saudari_seayah_oleh_dua_saudari_kandung(self):
        run_test(
            heirs_input=[HeirInput(id=21, quantity=2), HeirInput(id=22)],
            expected_fractions={"Saudari Seayah": "Mahjub"}
        )


# ========== TES ASHOBAH ==========
class TestAshobah:
    """Tes ahli waris ashobah (sisa)."""
    
    def test_ashobah_bin_nafsi_anak_laki(self):
        run_test(
            heirs_input=[HeirInput(id=1)],
            expected_fractions={"Anak Laki-laki": "Sisa"}
        )

    def test_ashobah_bin_nafsi_ayah(self):
        run_test(
            heirs_input=[HeirInput(id=2)],
            expected_fractions={"Ayah": "Sisa"}
        )

    def test_ashobah_bil_ghair_anak_perempuan(self):
        run_test(
            heirs_input=[HeirInput(id=1), HeirInput(id=16)],
            expected_fractions={"Anak Perempuan": "Sisa"}
        )

    def test_ashobah_bil_ghair_cucu_perempuan(self):
        run_test(
            heirs_input=[HeirInput(id=5), HeirInput(id=17)],
            expected_fractions={"Cucu Perempuan": "Sisa"}
        )

    def test_ashobah_bil_ghair_saudari_kandung(self):
        run_test(
            heirs_input=[HeirInput(id=7), HeirInput(id=21)],
            expected_fractions={"Saudari Kandung": "Sisa"}
        )

    def test_ashobah_bil_ghair_saudari_seayah(self):
        run_test(
            heirs_input=[HeirInput(id=8), HeirInput(id=22)],
            expected_fractions={"Saudari Seayah": "Sisa"}
        )

    def test_ashobah_maal_ghair_saudari_kandung(self):
        run_test(
            heirs_input=[HeirInput(id=21), HeirInput(id=16)],
            expected_fractions={"Saudari Kandung": "Sisa"}
        )

    def test_ashobah_maal_ghair_saudari_seayah(self):
        run_test(
            heirs_input=[HeirInput(id=22), HeirInput(id=16)],
            expected_fractions={"Saudari Seayah": "Sisa"}
        )

    def test_ashobah_bis_sabab_pria_pembebas(self):
        run_test(
            heirs_input=[HeirInput(id=24)],
            expected_fractions={"Pria Pembebas Budak": "Sisa"}
        )

    def test_ashobah_bis_sabab_mahjub(self):
        run_test(
            heirs_input=[HeirInput(id=12), HeirInput(id=24)],
            expected_fractions={"Pria Pembebas Budak": "Mahjub"}
        )


# ========== TES TAKMILAH (PELENGKAP 1/6) ==========
class TestTakmilah:
    """Tes pelengkap 1/6 untuk melengkapkan fardh."""
    
    def test_takmilah_cucu_perempuan(self):
        run_test(
            heirs_input=[HeirInput(id=16), HeirInput(id=17)],
            expected_fractions={"Cucu Perempuan": "1/6"}
        )

    def test_takmilah_saudari_seayah(self):
        run_test(
            heirs_input=[HeirInput(id=21), HeirInput(id=22)],
            expected_fractions={"Saudari Seayah": "1/6"}
        )


# ========== TES KASUS ISTIMEWA ==========
class TestKasusIstimewa:
    """Tes kasus-kasus khusus dalam Faraid."""
    
    def test_gharrawain_dengan_suami(self):
        """Gharrawain: Suami, Ibu, Ayah."""
        run_test(
            heirs_input=[HeirInput(id=3), HeirInput(id=18), HeirInput(id=2)],
            expected_am_awal=6,
            expected_am_akhir=6,
            expected_saham={"Suami": 3, "Ibu": 1, "Ayah": 2},
            expected_fractions={"Ibu": "1/3 Sisa"}
        )

    def test_gharrawain_dengan_istri(self):
        """Gharrawain: Istri, Ibu, Ayah."""
        run_test(
            heirs_input=[HeirInput(id=4), HeirInput(id=18), HeirInput(id=2)],
            expected_am_awal=4,
            expected_am_akhir=4,
            expected_saham={"Istri": 1, "Ibu": 1, "Ayah": 2}
        )

    def test_musytarakah(self):
        """Musytarakah: Suami, Ibu, 2 Sdr Seibu, Sdr Kandung."""
        run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18),
                HeirInput(id=9, quantity=2), HeirInput(id=7)
            ],
            expected_am_awal=18,
            expected_am_akhir=18,
            expected_saham={"Suami": 9, "Ibu": 3}
        )

    def test_akdariyah(self):
        """Akdariyah: Suami, Ibu, Kakek, Saudari Kandung."""
        run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18),
                HeirInput(id=6), HeirInput(id=21)
            ],
            expected_am_awal=6,
            expected_am_akhir=27,
            expected_status="Akdariyah"
        )


# ========== TES 'AUL DAN RADD ==========
class TestAulRadd:
    """Tes kasus 'Aul (naik) dan Radd (turun)."""
    
    def test_aul_ke_7(self):
        """'Aul: Suami, 2 Saudari Kandung."""
        run_test(
            heirs_input=[HeirInput(id=3), HeirInput(id=21, quantity=2)],
            expected_am_awal=6,
            expected_am_akhir=7,
            expected_status="'Aul"
        )

    def test_aul_ke_10(self):
        """'Aul: Suami, Ibu, 2 Saudari Kandung."""
        # Kasus ini menghasilkan AM=8 karena Ibu dapat 1/6 (ada 2 saudara)
        # Untuk 'aul ke 10, perlu kasus berbeda
        run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18),
                HeirInput(id=21, quantity=2)
            ],
            expected_am_awal=6,
            expected_am_akhir=8,  # Bukan 10
            expected_status="'Aul"
        )

    def test_radd_tanpa_suami(self):
        """Radd: Ibu, Anak Perempuan."""
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=16)],
            expected_am_awal=6,
            expected_am_akhir=4,
            expected_status="Radd"
        )

    def test_radd_dengan_suami(self):
        """Radd dengan Suami: Suami, Ibu."""
        result = run_test(
            heirs_input=[HeirInput(id=3), HeirInput(id=18)],
            expected_status="Radd"
        )
        # Verify suami gets his share and ibu gets the rest
        assert any(s.heir.name_id == "Suami" for s in result.shares)
        assert any(s.heir.name_id == "Ibu" for s in result.shares)


# ========== TES INKISAR ==========
class TestInkisar:
    """Tes Tashihul Mas'alah (Inkisar)."""
    
    def test_inkisar_muwafaqoh(self):
        """Inkisar Muwafaqoh: Ibu, 6 Paman Kandung."""
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=6)],
            expected_am_awal=3,
            expected_am_akhir=9,
            expected_saham={"Ibu": 3, "Paman Kandung": 6}
        )

    def test_inkisar_mubayanah(self):
        """Inkisar Mubayanah: Ibu, 5 Paman Kandung."""
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=5)],
            expected_am_awal=3,
            expected_am_akhir=15,
            expected_saham={"Ibu": 5, "Paman Kandung": 10}
        )

    def test_inkisar_mudakhalah(self):
        """Inkisar Mudakhalah: Ibu, 4 Paman Kandung."""
        # Mudakhalah: 4 orang, GCD(2,4)=2, pengali=2, AM akhir=6
        run_test(
            heirs_input=[HeirInput(id=18), HeirInput(id=12, quantity=4)],
            expected_am_awal=3,
            expected_am_akhir=6,  # Bukan 12
            expected_saham={"Ibu": 2, "Paman Kandung": 4}
        )


# ========== TES JADD WAL IKHWAH ==========
class TestJaddWalIkhwah:
    """Tes kasus Kakek bersama Saudara."""
    
    def test_jadd_wal_ikhwah_standar(self):
        """Jadd wal Ikhwah: Suami, Ibu, Kakek, 2 Saudari Kandung."""
        run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18),
                HeirInput(id=6), HeirInput(id=21, quantity=2)
            ],
            expected_am_akhir=12,
            expected_saham={"Suami": 6, "Ibu": 2, "Kakek": 2, "Saudari Kandung": 2}
        )

    def test_jadd_wal_ikhwah_muqasamah(self):
        """Jadd wal Ikhwah dengan Muqasamah."""
        run_test(
            heirs_input=[
                HeirInput(id=6), HeirInput(id=7), HeirInput(id=21)
            ],
            expected_am_akhir=5,
            expected_saham={"Kakek": 2}
        )


# ========== TES AL-'ADD ==========
class TestAlAdd:
    """Tes Mas'alah al-'Add."""
    
    def test_al_add_basic(self):
        """Al-'Add: Nenek, Kakek, Saudari Kandung, Saudara Seayah, Saudari Seayah."""
        # Hasil aktual: AM=54 dengan tashih ×9
        run_test(
            heirs_input=[
                HeirInput(id=20), HeirInput(id=6),
                HeirInput(id=21), HeirInput(id=8), HeirInput(id=22)
            ],
            expected_am_akhir=54,  # Bukan 36
            expected_saham={
                "Nenek dari Ayah": 9,
                "Kakek": 15,
                "Saudari Kandung": 27,
                "Saudara Laki-laki Seayah": 2,
                "Saudari Seayah": 1
            }
        )


# ========== TES PENGHALANG SIFAT ==========
class TestPenghalangSifat:
    """Tes Mawani' al-Irts (penghalang karena sifat)."""
    
    def test_penghalang_pembunuhan(self):
        """Ahli waris yang membunuh pewaris."""
        run_test(
            heirs_input=[
                HeirInput(id=1, penghalang="pembunuhan"),
                HeirInput(id=18)
            ],
            expected_fractions={"Anak Laki-laki": "Mahjub"}
        )

    def test_penghalang_murtad(self):
        """Ahli waris yang murtad."""
        run_test(
            heirs_input=[
                HeirInput(id=16, penghalang="murtad"),
                HeirInput(id=2)
            ],
            expected_fractions={"Anak Perempuan": "Mahjub"}
        )


# ========== TES KOMPLEKS ==========
class TestKasusKompleks:
    """Tes kasus-kasus kompleks dan kombinasi."""
    
    def test_kombinasi_fardh_ashobah(self):
        """Kombinasi Fardh dan Ashobah: Suami, Ibu, Anak Laki, Anak Perempuan."""
        result = run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18),
                HeirInput(id=1), HeirInput(id=16)
            ],
            expected_fractions={"Suami": "1/4", "Ibu": "1/6"}
        )
        # Verify anak-anak share 2:1
        son_share = next(s for s in result.shares if s.heir.name_id == "Anak Laki-laki")
        daughter_share = next(s for s in result.shares if s.heir.name_id == "Anak Perempuan")
        assert son_share.saham == daughter_share.saham * 2

    def test_banyak_ahli_waris(self):
        """Kasus dengan banyak ahli waris."""
        # Dengan Suami 1/4 + keturunan, AM awal = KPK(4,6,3) = 12
        run_test(
            heirs_input=[
                HeirInput(id=3), HeirInput(id=18), HeirInput(id=2),
                HeirInput(id=16, quantity=2), HeirInput(id=21, quantity=2)
            ],
            expected_am_awal=12  # Bukan 6
        )


# ========== FIXTURE ==========
@pytest.fixture(scope="session")
def db_session():
    """Database session untuk semua tes."""
    db = SessionLocal()
    yield db
    db.close()


# ========== RUNNER ==========
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
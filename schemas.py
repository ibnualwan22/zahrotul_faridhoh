# Di dalam file: schemas.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict

# --- Skema Ahli Waris (Database) ---
class HeirBase(BaseModel):
    name_id: str   # Nama dalam bahasa Indonesia
    name_ar: str   # Nama dalam bahasa Arab

class HeirCreate(HeirBase):
    pass

class Heir(HeirBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Skema Input untuk Kalkulasi Dasar ---
class HeirInput(BaseModel):
    id: int
    quantity: int = 1
    penghalang: Optional[str] = None
    status: Optional[str] = None  # Tambahan: status (misal "mahjub", "ashabah", dsb.)

class CalculationInput(BaseModel):
    heirs: List[HeirInput]
    tirkah: float  # Harta bersih yang dibagi

# --- Skema Output untuk Setiap Ahli Waris ---
class HeirShare(BaseModel):
    heir: Heir
    quantity: int
    share_fraction: str        # Pecahan, misal "1/2"
    saham: float               # Saham mentah sebelum dikali tirkah
    reason: str                # Alasan (diambil dari tabel furudh)
    share_amount: float        # Bagian akhir dalam rupiah/harta
    model_config = ConfigDict(from_attributes=True)

class FurudhItem(BaseModel):
    heir: Heir
    fraction: str          # Pecahan misal "1/2"
    denominator: int       # Penyebut pecahan
    numerator: int         # Pembilang pecahan
    reason: str            # Alasan (dari tabel furudh PDF)
    quantity: int = 1      # jumlah ahli waris (default 1)


# --- Skema untuk Perbandingan Pecahan Furudh ---
class ComparisonItem(BaseModel):
    a: int                   # penyebut pecahan pertama
    b: int                   # penyebut pecahan kedua
    relation: str            # hasil perbandingan (mumatsalah, muwafaqoh, mudakholah, mubayanah)
    lcm: Optional[int] = None  # KPK jika diperlukan

# --- Skema untuk Aslul Mas'alah ---
class AshlInfo(BaseModel):
    ashl_awal: int                  # AM sebelum aul/radd
    ashl_akhir: int                 # AM setelah aul/radd
    comparisons: List[ComparisonItem]  # daftar hasil perbandingan penyebut
    total_saham: int                # jumlah saham
    status: str                     # "adil", "aul", "radd", "inkisar"

# --- Skema untuk Jejak Perhitungan (Trace) ---
class CalculationTrace(BaseModel):
    step: str                  # nama langkah (contoh: "Menentukan furudh", "Membandingkan penyebut")
    description: str            # penjelasan lengkap
    data: Optional[dict] = None # data tambahan (misalnya {"penyebut": [2, 3, 6], "ashl": 6})

class SahamItem(BaseModel):
    heir: Heir
    quantity: int
    saham_awal: int            # saham sebelum aul/radd
    saham_akhir: int           # saham setelah aul/radd (kalau ada perubahan)
    share_fraction: str        # pecahan awal (misal 1/6, 1/8)
    reason: str                # alasan (kenapa dapat bagian itu)

# --- Skema untuk Jumlah Akhir (Nominal) ---
class FinalAmount(BaseModel):
    heir: Heir
    quantity: int
    saham: int                 # jumlah saham final
    amount_each: float         # nominal per ahli waris (dibagi quantity)
    total_amount: float        # total nominal untuk semua (quantity × amount_each)


# --- Skema Output Utama untuk Kalkulasi Dasar ---
class CalculationResult(BaseModel):
    tirkah: float
    ashlul_masalah_awal: int   # AM sebelum 'Aul atau Radd
    ashlul_masalah_akhir: int  # AM setelah 'Aul atau Radd
    total_saham: float
    status: str                # Misal: "Adil", "Aul", "Radd", "Inkisar"
    notes: List[str]           # Catatan langkah-langkah sesuai kitab
    shares: List[HeirShare]
    model_config = ConfigDict(from_attributes=True)

# --- Skema untuk Munasakhot ---
class MunasakhotInput(BaseModel):
    masalah_ula: CalculationInput
    mayit_tsani_id: int
    masalah_tsaniyah_heirs: List[HeirInput]

class FinalShare(BaseModel):
    heir: Heir
    saham: float
    share_amount: float
    model_config = ConfigDict(from_attributes=True)

class MunasakhotResult(BaseModel):
    detail_masalah_ula: CalculationResult
    detail_masalah_tsaniyah: CalculationResult
    perbandingan: str   # Mumatsalah, Muwafaqoh, Mudakholah, Mubayanah
    jamiiah: int
    final_shares: List[FinalShare]
    model_config = ConfigDict(from_attributes=True)

# --- Skema untuk Mauquf (Mafqud, Khuntsa, Haml) ---
class MafqudInput(BaseModel):
    heirs: List[HeirInput]
    tirkah: float

class MafqudShare(BaseModel):
    heir: Heir
    quantity: int
    share_amount_yakin: float   # Bagian pasti
    reason: str

class KhuntsaInput(BaseModel):
    heirs: List[HeirInput]
    tirkah: float
    khuntsa_id: int
    male_equivalent_id: int
    female_equivalent_id: int

class HamlInput(BaseModel):
    heirs: List[HeirInput]
    tirkah: float

# Output gabungan untuk semua kasus Mauquf
class MauqufResult(BaseModel):
    tirkah: float
    pembagian_sekarang: List[MafqudShare]
    dana_mauquf: float
    detail_skenarios: Dict[str, CalculationResult]

# --- Skema untuk Gharqa (kematian bersamaan) ---
class GharqaProblem(BaseModel):
    problem_name: str
    heirs: List[HeirInput]
    tirkah: float

class GharqaInput(BaseModel):
    problems: List[GharqaProblem]

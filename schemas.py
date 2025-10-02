# Di dalam file: schemas.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional

# --- Skema Ahli Waris (Database) ---
class HeirBase(BaseModel):
    name_id: str
    name_ar: str

class HeirCreate(HeirBase):
    pass

class Heir(HeirBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Skema Kalkulator (Input & Output) ---
class HeirInput(BaseModel):
    id: int
    quantity: int = 1
    penghalang: Optional[str] = None # <-- TAMBAHKAN BARIS INI

class CalculationInput(BaseModel):
    heirs: list[HeirInput]
    tirkah: float

class HeirShare(BaseModel):
    heir: Heir
    quantity: int
    share_fraction: str
    saham: float # Menampilkan porsi saham
    reason: str
    share_amount: float
    model_config = ConfigDict(from_attributes=True)

class CalculationResult(BaseModel):
    tirkah: float
    ashlul_masalah_awal: int # Ashlul Masalah sebelum 'Aul atau Radd
    ashlul_masalah_akhir: int # Ashlul Masalah setelah 'Aul atau Radd
    total_saham: float
    status: str # Misal: "Adilah", "Masalah 'Aul", "Masalah Radd"
    notes: List[str] # Untuk menyimpan proses penentuan Ashlul Masalah
    shares: List[HeirShare]
    model_config = ConfigDict(from_attributes=True)

class MunasakhotInput(BaseModel):
    masalah_ula: CalculationInput  # Data untuk masalah pertama (pewaris & tirkah)
    mayit_tsani_id: int            # ID ahli waris dari masalah pertama yang meninggal
    masalah_tsaniyah_heirs: list[HeirInput] # Daftar ahli waris untuk orang yang meninggal kedua

class FinalShare(BaseModel):
    heir: Heir
    saham: float
    share_amount: float
    model_config = ConfigDict(from_attributes=True)

class MunasakhotResult(BaseModel):
    detail_masalah_ula: CalculationResult
    detail_masalah_tsaniyah: CalculationResult
    perbandingan: str
    jamiiah: int
    final_shares: list[FinalShare]
    model_config = ConfigDict(from_attributes=True)
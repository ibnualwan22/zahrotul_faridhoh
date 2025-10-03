# Di dalam file: main.py

from fastapi import FastAPI, Depends, HTTPException
from schemas import CalculationInput, CalculationResult
from calculator import calculate_inheritance
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware # <-- TAMBAHKAN IMPORT INI

import crud
import gharqa
import models
import schemas
from database import SessionLocal, engine
import calculator
import munasakhot, mauquf

# Membuat tabel di database (jika belum ada)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kalkulator Faraidh - Zahrotul Faridhoh",
    description="API untuk perhitungan waris Islam berdasarkan kitab Zahrotul Faridhoh."
)
origins = [
    "http://localhost",
    "http://localhost:3000", # Alamat frontend Next.js kita
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate", response_model=CalculationResult)
def api_calculate(payload: CalculationInput):
    return calculate(payload)
# --- Dependency untuk Sesi Database ---
# Ini adalah cara standar FastAPI untuk mengelola koneksi database per permintaan
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# -----------------------------------------

@app.get("/")
def read_root():
    """
    Endpoint utama untuk menyapa pengguna.
    """
    return {"message": "Selamat datang di Kalkulator Faraidh Zahrotul Faridhoh"}

@app.post("/heirs/", response_model=schemas.Heir)
def create_heir_endpoint(heir: schemas.HeirCreate, db: Session = Depends(get_db)):
    """
    Endpoint untuk membuat/menambahkan ahli waris baru.
    """
    # Cek apakah ahli waris dengan nama yang sama sudah ada
    db_heir = crud.get_heir_by_name(db, name_id=heir.name_id)
    if db_heir:
        # Jika sudah ada, kirim error
        raise HTTPException(status_code=400, detail="Ahli waris dengan nama ini sudah ada")
    
    # Jika belum ada, buat ahli waris baru
    return crud.create_heir(db=db, heir=heir)

@app.get("/heirs/", response_model=list[schemas.Heir])
def read_heirs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Endpoint untuk membaca daftar semua ahli waris.
    """
    heirs = crud.get_heirs(db, skip=skip, limit=limit)
    return heirs

@app.post("/calculate/", response_model=schemas.CalculationResult) # TAMBAHKAN INI
def run_calculation(calculation_data: schemas.CalculationInput, db: Session = Depends(get_db)):
    """
    Endpoint utama untuk menjalankan perhitungan Faraidh.
    """
    result = calculator.calculate_inheritance(db, calculation_input=calculation_data)
    return result

@app.post("/calculate/munasakhot/")
def run_munasakhot_calculation(munasakhot_data: schemas.MunasakhotInput, db: Session = Depends(get_db)):
    """
    Endpoint khusus untuk menjalankan perhitungan Munasakhot.
    """
    result = munasakhot.solve_munasakhot(db, munasakhot_input=munasakhot_data)
    return result

@app.post("/calculate/mafqud/", response_model=schemas.MauqufResult) # <-- Perbarui response_model
def run_mafqud_calculation(mafqud_data: schemas.MafqudInput, db: Session = Depends(get_db)):
    return mauquf.solve_mafqud(db, mafqud_input=mafqud_data)

# ==> ENDPOINT BARU UNTUK KHUNTSA <==
@app.post("/calculate/khuntsa/", response_model=schemas.MauqufResult)
def run_khuntsa_calculation(khuntsa_data: schemas.KhuntsaInput, db: Session = Depends(get_db)):
    return mauquf.solve_khuntsa(db, khuntsa_input=khuntsa_data)

# ==> ENDPOINT BARU UNTUK HAML <==
@app.post("/calculate/haml/", response_model=schemas.MauqufResult)
def run_haml_calculation(haml_data: schemas.HamlInput, db: Session = Depends(get_db)):
    return mauquf.solve_haml(db, haml_input=haml_data) # mafqud_input diganti haml_input jika ada error

@app.post("/calculate/gharqa/")
def run_gharqa_calculation(gharqa_data: schemas.GharqaInput, db: Session = Depends(get_db)):
    """Endpoint untuk kasus kematian bersamaan (al-Gharqa)."""
    return gharqa.solve_gharqa(db, gharqa_input=gharqa_data)
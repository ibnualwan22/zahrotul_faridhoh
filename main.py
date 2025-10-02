# Di dalam file: main.py

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import SessionLocal, engine
import calculator
import munasakhot

# Membuat tabel di database (jika belum ada)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kalkulator Faraidh - Zahrotul Faridhoh",
    description="API untuk perhitungan waris Islam berdasarkan kitab Zahrotul Faridhoh."
)

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
# Di dalam file: crud.py

from sqlalchemy.orm import Session
import models
import schemas

def get_heir_by_name(db: Session, name_id: str):
    """
    Fungsi untuk mencari ahli waris berdasarkan nama Indonesianya.
    Ini berguna agar tidak ada data duplikat.
    """
    return db.query(models.Heir).filter(models.Heir.name_id == name_id).first()

def create_heir(db: Session, heir: schemas.HeirCreate):
    """
    Fungsi untuk membuat dan menyimpan ahli waris baru ke database.
    """
    db_heir = models.Heir(name_id=heir.name_id, name_ar=heir.name_ar)
    db.add(db_heir)
    db.commit()
    db.refresh(db_heir)
    return db_heir

# TAMBAHKAN FUNGSI BARU INI
def get_heirs(db: Session, skip: int = 0, limit: int = 100):
    """
    Fungsi untuk mengambil daftar semua ahli waris dari database.
    'skip' dan 'limit' berguna untuk paginasi jika data sudah banyak.
    """
    return db.query(models.Heir).offset(skip).limit(limit).all()

def get_heirs_by_ids(db: Session, heir_ids: list[int]):
    """
    Fungsi untuk mengambil beberapa ahli waris berdasarkan daftar ID.
    """
    return db.query(models.Heir).filter(models.Heir.id.in_(heir_ids)).all()
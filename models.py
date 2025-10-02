# Di dalam file: models.py

from sqlalchemy import Column, Integer, String
from database import Base

# Mendefinisikan model tabel untuk Ahli Waris (Heir)
class Heir(Base):
    __tablename__ = "heirs"  # Nama tabel di database

    id = Column(Integer, primary_key=True, index=True)
    name_id = Column(String, unique=True, index=True) # Nama dalam Bahasa Indonesia
    name_ar = Column(String, unique=True) # Nama dalam Bahasa Arab
# Di dalam file: populate_db.py

import requests
import json

# URL endpoint API kita untuk membuat ahli waris
API_URL = "http://127.0.0.1:8000/heirs/"

# Salin seluruh data JSON yang saya berikan sebelumnya ke sini
heirs_data = [
    { "name_id": "Anak Laki-laki", "name_ar": "ابن" },
    { "name_id": "Cucu Laki-laki", "name_ar": "ابن ابن" },
    { "name_id": "Ayah", "name_ar": "أب" },
    { "name_id": "Kakek", "name_ar": "جد" },
    { "name_id": "Saudara Laki-laki Kandung", "name_ar": "أخ لأبوين" },
    { "name_id": "Saudara Laki-laki Seayah", "name_ar": "أخ لأب" },
    { "name_id": "Saudara Laki-laki Seibu", "name_ar": "أخ لأم" },
    { "name_id": "Keponakan Laki-laki (dari Sdr Lk Kandung)", "name_ar": "ابن أخ لأبوين" },
    { "name_id": "Keponakan Laki-laki (dari Sdr Lk Seayah)", "name_ar": "ابن أخ لأب" },
    { "name_id": "Paman Kandung", "name_ar": "عم لأبوين" },
    { "name_id": "Paman Seayah", "name_ar": "عم لأب" },
    { "name_id": "Sepupu Laki-laki (dari Paman Kandung)", "name_ar": "ابن عم لأبوين" },
    { "name_id": "Sepupu Laki-laki (dari Paman Seayah)", "name_ar": "ابن عم لأب" },
    { "name_id": "Suami", "name_ar": "زوج" },
    { "name_id": "Anak Perempuan", "name_ar": "بنت" },
    { "name_id": "Cucu Perempuan", "name_ar": "بنت ابن" },
    { "name_id": "Ibu", "name_ar": "أم" },
    { "name_id": "Nenek dari Ibu", "name_ar": "جدة من الأم" },
    { "name_id": "Nenek dari Ayah", "name_ar": "جدة من الأب" },
    { "name_id": "Saudari Kandung", "name_ar": "أخت لأبوين" },
    { "name_id": "Saudari Seayah", "name_ar": "أخت لأب" },
    { "name_id": "Saudari Seibu", "name_ar": "أخت لأم" },
    { "name_id": "Istri", "name_ar": "زوجة" },
    { "name_id": "Pria Pembebas Budak", "name_ar": "معتق" },
    { "name_id": "Wanita Pembebas Budak", "name_ar": "معتقة" }
]

def populate_database():
    print("Memulai proses memasukkan data ahli waris...")
    for heir in heirs_data:
        try:
            # Mengirim permintaan POST ke API kita dengan data JSON
            response = requests.post(API_URL, data=json.dumps(heir))
            
            # Memeriksa status respons
            if response.status_code == 200:
                print(f"  [BERHASIL] Menambahkan: {heir['name_id']}")
            elif response.status_code == 400:
                # Error 400 kita atur untuk data yang sudah ada
                print(f"  [INFO] Data untuk '{heir['name_id']}' sudah ada, dilewati.")
            else:
                print(f"  [ERROR] Gagal menambahkan {heir['name_id']}. Status: {response.status_code}, Pesan: {response.text}")

        except requests.exceptions.ConnectionError as e:
            print("\n[ERROR] Koneksi ke server gagal. Pastikan server Uvicorn Anda sedang berjalan.")
            print(f"Detail: {e}")
            break
    print("\nProses selesai.")

if __name__ == "__main__":
    populate_database()
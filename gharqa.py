# Di dalam file: gharqa.py
from sqlalchemy.orm import Session
from schemas import GharqaInput, CalculationInput
from calculator import calculate_inheritance

def solve_gharqa(db: Session, gharqa_input: GharqaInput):
    results = []
    
    # Dapatkan semua ID dari semua orang yang meninggal bersamaan
    deceased_ids = set()
    for problem in gharqa_input.problems:
        # Asumsi: Setiap masalah merepresentasikan 1 orang yg wafat
        # Kita perlu cara untuk menautkan orang ke masalahnya, untuk saat ini kita sederhanakan
        pass # Untuk saat ini kita anggap mereka tidak saling mewarisi

    for problem in gharqa_input.problems:
        # Jalankan kalkulator untuk setiap masalah secara terpisah
        calc_input = CalculationInput(heirs=problem.heirs, tirkah=problem.tirkah)
        result = calculate_inheritance(db, calc_input)
        results.append({
            "problem_name": problem.problem_name,
            "result": result
        })
        
    return results
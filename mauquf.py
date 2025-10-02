# Di dalam file: mauquf.py

from sqlalchemy.orm import Session
from schemas import CalculationInput, HeirInput, MafqudInput, MauqufResult, MafqudShare, KhuntsaInput, HamlInput
from calculator import calculate_inheritance
import copy

def _solve_mauquf_generic(db: Session, tirkah: float, scenarios: dict, all_heir_inputs: list):
    """Fungsi generik untuk menyelesaikan semua kasus mauquf."""
    
    scenario_results = {}
    all_heir_ids = {h.id for h in all_heir_inputs}

    for name, heirs in scenarios.items():
        input_data = CalculationInput(heirs=heirs, tirkah=tirkah)
        scenario_results[name] = calculate_inheritance(db, input_data)

    pembagian_sekarang = []
    total_yakin_dibagikan = 0

    non_mauquf_heirs = [h for h in all_heir_inputs if not h.status]
    for heir_input in non_mauquf_heirs:
        heir_id = heir_input.id
        share_amounts = []
        for result in scenario_results.values():
            share_obj = next((s for s in result.shares if s.heir.id == heir_id), None)
            share_amounts.append(share_obj.share_amount if share_obj else 0)
        
        share_yakin = min(share_amounts)
        
        heir_details = next((s.heir for res in scenario_results.values() for s in res.shares if s.heir.id == heir_id), None)
        if heir_details:
            pembagian_sekarang.append(MafqudShare(heir=heir_details, quantity=heir_input.quantity, share_amount_yakin=share_yakin, reason="Menerima bagian terkecil dari semua skenario."))
            total_yakin_dibagikan += share_yakin
    
    dana_mauquf = tirkah - total_yakin_dibagikan
    
    return MauqufResult(
        tirkah=tirkah,
        pembagian_sekarang=pembagian_sekarang,
        dana_mauquf=dana_mauquf,
        detail_skenarios=scenario_results
    )

def solve_mafqud(db: Session, mafqud_input: MafqudInput):
    all_heirs = mafqud_input.heirs
    scenarios = {
        "hidup": all_heirs,
        "mati": [h for h in all_heirs if h.status != "mafquf"]
    }
    return _solve_mauquf_generic(db, mafqud_input.tirkah, scenarios, all_heirs)

def solve_khuntsa(db: Session, khuntsa_input: KhuntsaInput):
    all_heirs = khuntsa_input.heirs
    
    heirs_as_male = copy.deepcopy(all_heirs)
    for h in heirs_as_male:
        if h.id == khuntsa_input.khuntsa_id: h.id = khuntsa_input.male_equivalent_id
        
    heirs_as_female = copy.deepcopy(all_heirs)
    for h in heirs_as_female:
        if h.id == khuntsa_input.khuntsa_id: h.id = khuntsa_input.female_equivalent_id
        
    scenarios = {
        "dianggap_laki": heirs_as_male,
        "dianggap_perempuan": heirs_as_female
    }
    return _solve_mauquf_generic(db, khuntsa_input.tirkah, scenarios, all_heirs)

def solve_haml(db: Session, haml_input: HamlInput):
    all_heirs = haml_input.heirs
    haml_heir = next((h for h in all_heirs if h.status == "haml"), None)
    if not haml_heir: raise ValueError("Tidak ada ahli waris janin (haml).")

    base_heirs = [h for h in all_heirs if h.status != "haml"]

    scenarios = {
        "dianggap_mati": base_heirs,
        "satu_anak_laki": base_heirs + [HeirInput(id=1, quantity=1)],      # ID 1 untuk Anak Laki-laki
        "satu_anak_perempuan": base_heirs + [HeirInput(id=16, quantity=1)], # ID 16 untuk Anak Perempuan
        "kembar_laki": base_heirs + [HeirInput(id=1, quantity=2)],
        "kembar_perempuan": base_heirs + [HeirInput(id=16, quantity=2)],    # <-- TAMBAHAN
        "kembar_campuran": base_heirs + [HeirInput(id=1, quantity=1), HeirInput(id=16, quantity=1)] # <-- TAMBAHAN
    }
    return _solve_mauquf_generic(db, haml_input.tirkah, scenarios, all_heirs)
from sqlalchemy.orm import Session
import crud
import schemas
import models
import jadd_wal_ikhwah
from fractions import Fraction
import math

# --- Helper Functions & Constants ---
def lcm(a, b):
    return abs(a * b) // math.gcd(a, b) if a and b else 0

def get_relation_name(a, b):
    if a is None or b is None: return ""
    a, b = int(a), int(b)
    if a == b: return "Mumatsalah"
    if a % b == 0 or b % a == 0: return "Mudakholah"
    if math.gcd(a, b) > 1: return "Muwafaqoh"
    return "Mubayanah"

ASHOBAH_NASAB_ORDER = [ "Anak Laki-laki", "Cucu Laki-laki", "Ayah", "Kakek", "Saudara Laki-laki Kandung", "Saudara Laki-laki Seayah", "Keponakan Laki-laki (dari Sdr Lk Kandung)", "Keponakan Laki-laki (dari Sdr Lk Seayah)", "Paman Kandung", "Paman Seayah", "Sepupu Laki-laki (dari Paman Kandung)", "Sepupu Laki-laki (dari Paman Seayah)" ]
ASHOBAH_SABAB_NAMES = ["Pria Pembebas Budak", "Wanita Pembebas Budak"]
DESCENDANT_NAMES = ["Anak Laki-laki", "Anak Perempuan", "Cucu Laki-laki", "Cucu Perempuan"]
MALE_DESCENDANT_NAMES = ["Anak Laki-laki", "Cucu Laki-laki"]
FEMALE_DESCENDANT_NAMES = ["Anak Perempuan", "Cucu Perempuan"]
SIBLING_NAMES = ["Saudara Laki-laki Kandung", "Saudara Laki-laki Seayah", "Saudara Laki-laki Seibu", "Saudari Kandung", "Saudari Seayah", "Saudari Seibu"]

def calculate_inheritance(db: Session, calculation_input: schemas.CalculationInput):
    input_heirs = calculation_input.heirs
    tirkah = calculation_input.tirkah
    heir_ids = [h.id for h in input_heirs]
    selected_heirs_db = crud.get_heirs_by_ids(db, heir_ids=heir_ids)
    
    selected_heirs = []
    for heir_input in input_heirs:
        db_data = next((h for h in selected_heirs_db if h.id == heir_input.id), None)
        if db_data:
            selected_heirs.append({ "data": db_data, "quantity": heir_input.quantity, "share_fraction_str": "0", "reason": "", "is_ashobah": False, "is_ashobah_bil_ghair": False, "is_ashobah_maal_ghair": False, "saham": 0.0 })

    # --- TAHAP 1: DEFINISI & HAJB ---
    blocked_heirs = set()
    blocking_heirs_details = {}
    heir_names = {h['data'].name_id for h in selected_heirs}

    # ==> LOGIKA BARU: Cek Mawani' al-Irts di Awal <==
    for i, heir_input in enumerate(input_heirs):
        if heir_input.penghalang:
            heir_to_block = selected_heirs[i]
            heir_name = heir_to_block['data'].name_id
            blocked_heirs.add(heir_name)
            blocking_heirs_details[heir_name] = f"sifat ({heir_input.penghalang})"
    
    son = next((h for h in selected_heirs if h['data'].name_id == "Anak Laki-laki"), None)
    father = next((h for h in selected_heirs if h['data'].name_id == "Ayah"), None)
    mother = next((h for h in selected_heirs if h['data'].name_id == "Ibu"), None)
    grandson = next((h for h in selected_heirs if h['data'].name_id == "Cucu Laki-laki"), None)
    brother_kandung = next((h for h in selected_heirs if h['data'].name_id == "Saudara Laki-laki Kandung"), None)
    sisters_kandung_count = sum(h['quantity'] for h in selected_heirs if h['data'].name_id == "Saudari Kandung")
    
    strongest_ashobah_nasab_name = next((name for name in ASHOBAH_NASAB_ORDER if any(h['data'].name_id == name for h in selected_heirs if h['data'].name_id not in ["Ayah", "Kakek"])), None)
    if strongest_ashobah_nasab_name:
        start_blocking = False
        for heir_name in ASHOBAH_NASAB_ORDER:
            if heir_name == strongest_ashobah_nasab_name: start_blocking = True; continue
            if start_blocking: blocked_heirs.add(heir_name); blocking_heirs_details[heir_name] = strongest_ashobah_nasab_name
        blocked_heirs.update(ASHOBAH_SABAB_NAMES); blocking_heirs_details.update({name: strongest_ashobah_nasab_name for name in ASHOBAH_SABAB_NAMES})

    if father:
        blocked_heirs.add("Kakek"); blocking_heirs_details["Kakek"] = "Ayah"
        blocked_heirs.add("Nenek dari Ayah"); blocking_heirs_details["Nenek dari Ayah"] = "Ayah"
        blocked_heirs.update(SIBLING_NAMES); [blocking_heirs_details.update({h: "Ayah"}) for h in SIBLING_NAMES]
    if mother:
        blocked_heirs.update(["Nenek dari Ibu", "Nenek dari Ayah"]); blocking_heirs_details.update({"Nenek dari Ibu": "Ibu", "Nenek dari Ayah": "Ibu"})
    if son:
        blocked_heirs.update(["Cucu Laki-laki", "Cucu Perempuan"]); blocking_heirs_details.update({"Cucu Laki-laki": "Anak Laki-laki", "Cucu Perempuan": "Anak Laki-laki"})
    
    descendant_or_male_ascendant = any(h['data'].name_id in DESCENDANT_NAMES + ["Ayah", "Kakek"] for h in selected_heirs)
    if descendant_or_male_ascendant:
        blocked_heirs.update(["Saudara Laki-laki Seibu", "Saudari Seibu"])
        blocking_heirs_details.update({"Saudara Laki-laki Seibu": "Keturunan/Ayah/Kakek", "Saudari Seibu": "Keturunan/Ayah/Kakek"})

    if sisters_kandung_count >= 2:
        brother_seayah = next((h for h in selected_heirs if h['data'].name_id == "Saudara Laki-laki Seayah"), None)
        if not brother_seayah:
            blocked_heirs.add("Saudari Seayah")
            blocking_heirs_details["Saudari Seayah"] = "2 Saudari Kandung"

    # --- TAHAP 2: PENENTUAN BAGIAN & SAHAM AWAL ---
    notes = []
    ashlul_masalah_awal = 1
    heir_names = {h['data'].name_id for h in selected_heirs}
    jadd = next((h for h in selected_heirs if h['data'].name_id == "Kakek" and h['data'].name_id not in blocked_heirs), None)
    ikhwah = [h for h in selected_heirs if h['data'].name_id in jadd_wal_ikhwah.IKHWAH_NAMES and h['data'].name_id not in blocked_heirs]
    
    is_gharrawain = (len(selected_heirs) == 3 and "Ayah" in heir_names and "Ibu" in heir_names and ("Suami" in heir_names or "Istri" in heir_names))
    is_musytarakah = ("Suami" in heir_names and ("Ibu" in heir_names or "Nenek dari Ibu" in heir_names) and sum(h['quantity'] for h in selected_heirs if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"]) >= 2 and "Saudara Laki-laki Kandung" in heir_names)


    if is_gharrawain:
        notes.append("Terdeteksi: Kasus Mas'alah Gharrawain.")
        spouse = next(h for h in selected_heirs if h['data'].name_id in ["Suami", "Istri"]); mother = next(h for h in selected_heirs if h['data'].name_id == "Ibu"); father = next(h for h in selected_heirs if h['data'].name_id == "Ayah")
        if spouse['data'].name_id == "Suami": ashlul_masalah_awal = 6; spouse['saham'] = 3; mother['saham'] = 1; father['saham'] = 2
        else: ashlul_masalah_awal = 4; spouse['saham'] = 1; mother['saham'] = 1; father['saham'] = 2
        spouse['share_fraction_str'] = "1/2" if spouse['data'].name_id == "Suami" else "1/4"; mother['share_fraction_str'] = "1/3 Sisa"; father['share_fraction_str'] = "Sisa"
    elif is_musytarakah:
        notes.append("Terdeteksi: Kasus Mas'alah Musytarakah."); ashlul_masalah_awal = 6
        suami = next(h for h in selected_heirs if h['data'].name_id == "Suami"); ibu_atau_nenek = next(h for h in selected_heirs if h['data'].name_id in ["Ibu", "Nenek dari Ibu", "Nenek dari Ayah"]); musytarakah_heirs = [h for h in selected_heirs if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu", "Saudara Laki-laki Kandung"]]
        suami['share_fraction_str'] = "1/2"; suami['saham_awal'] = 3; ibu_atau_nenek['share_fraction_str'] = "1/6"; ibu_atau_nenek['saham_awal'] = 1
        musytarakah_saham_awal = 2; musytarakah_heads = sum(h['quantity'] for h in musytarakah_heirs)
        tashih_multiplier = musytarakah_heads // math.gcd(musytarakah_saham_awal, musytarakah_heads) if musytarakah_saham_awal % musytarakah_heads != 0 else 1
        ashlul_masalah_awal *= tashih_multiplier
        suami['saham'] = suami['saham_awal'] * tashih_multiplier; ibu_atau_nenek['saham'] = ibu_atau_nenek['saham_awal'] * tashih_multiplier
        saham_per_kepala_saudara = (musytarakah_saham_awal * tashih_multiplier) / musytarakah_heads
        for heir in musytarakah_heirs: heir['saham'] = saham_per_kepala_saudara * heir['quantity']; heir['share_fraction_str'] = "1/3 (berbagi)"; heir['reason'] = "Ikut serta (musytarakah)."
    else: # KASUS STANDAR (JIKA BUKAN GHARRAWAIN ATAU MUSYTARAKAH)
        # TAHAP 2 (Lanjutan): Penentuan Fardh untuk kasus standar
        descendant_names_present = [h['data'].name_id for h in selected_heirs if h['data'].name_id in DESCENDANT_NAMES and h['data'].name_id not in blocked_heirs]
        female_descendants_present = [h for h in selected_heirs if h['data'].name_id in FEMALE_DESCENDANT_NAMES and h['data'].name_id not in blocked_heirs]
        male_descendant_names_present = [h['data'].name_id for h in selected_heirs if h['data'].name_id in MALE_DESCENDANT_NAMES and h['data'].name_id not in blocked_heirs]
        sibling_count = sum(h['quantity'] for h in selected_heirs if h['data'].name_id in SIBLING_NAMES and h['data'].name_id not in blocked_heirs)
        
        for heir in selected_heirs:
            name = heir['data'].name_id; quantity = heir['quantity']
            if name in blocked_heirs:
                heir['share_fraction_str'] = "Mahjub"
                heir['reason'] = f"Terhalang oleh kehadiran {blocking_heirs_details.get(name, 'ahli waris lain')}."
                continue
            
            if name == "Suami": heir['share_fraction_str'] = "1/4" if descendant_names_present else "1/2"
            elif name == "Istri": heir['share_fraction_str'] = "1/8" if descendant_names_present else "1/4"
            elif name == "Ayah":
                if male_descendant_names_present: heir['share_fraction_str'] = "1/6"
                elif descendant_names_present: heir['share_fraction_str'] = "1/6"; heir['is_ashobah'] = True
                else: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah'] = True
            elif name == "Ibu":
                if descendant_names_present or sibling_count > 1: heir['share_fraction_str'] = "1/6"
                else: heir['share_fraction_str'] = "1/3"
            elif name == "Anak Perempuan":
                if son: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_bil_ghair'] = True
                elif quantity == 1: heir['share_fraction_str'] = "1/2"
                else: heir['share_fraction_str'] = "2/3"
            elif name == "Cucu Perempuan":
                daughter_count_val = sum(h['quantity'] for h in selected_heirs if h['data'].name_id == "Anak Perempuan")
                if grandson: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_bil_ghair'] = True
                elif daughter_count_val == 1: heir['share_fraction_str'] = "1/6"
                elif daughter_count_val == 0 and quantity == 1: heir['share_fraction_str'] = "1/2"
                elif daughter_count_val == 0 and quantity > 1: heir['share_fraction_str'] = "2/3"
                else: heir['share_fraction_str'] = "Mahjub"
            elif name == "Kakek":
                if not jadd or not ikhwah: # Hanya jalankan jika bukan kasus Jadd wal Ikhwah
                    if male_descendant_names_present: heir['share_fraction_str'] = "1/6"
                    elif descendant_names_present: heir['share_fraction_str'] = "1/6"; heir['is_ashobah'] = True
                    else: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah'] = True
            elif name in ["Nenek dari Ibu", "Nenek dari Ayah"]: heir['share_fraction_str'] = "1/6"
            elif name in ["Saudara Laki-laki Seibu", "Saudari Seibu"]:
                siblings_seibu_count = sum(h['quantity'] for h in selected_heirs if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"])
                heir['share_fraction_str'] = "1/6" if siblings_seibu_count == 1 else "1/3 (berbagi)"
            elif name == "Saudari Kandung":
                if female_descendants_present: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_maal_ghair'] = True
                elif brother_kandung: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_bil_ghair'] = True
                elif quantity == 1: heir['share_fraction_str'] = "1/2"
                else: heir['share_fraction_str'] = "2/3"
            elif name == "Saudari Seayah":
                sister_kandung = next((h for h in selected_heirs if h['data'].name_id == "Saudari Kandung"), None)
                brother_seayah = next((h for h in selected_heirs if h['data'].name_id == "Saudara Laki-laki Seayah"), None)
                if female_descendants_present: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_maal_ghair'] = True
                elif brother_seayah: heir['share_fraction_str'] = "Sisa"; heir['is_ashobah_bil_ghair'] = True
                elif sister_kandung and sister_kandung['quantity'] == 1: heir['share_fraction_str'] = "1/6"
                elif quantity == 1: heir['share_fraction_str'] = "1/2"
                else: heir['share_fraction_str'] = "2/3"
            elif name in ASHOBAH_NASAB_ORDER or name in ASHOBAH_SABAB_NAMES: 
                heir['share_fraction_str'] = "Sisa"; heir['is_ashobah'] = True

        ## --- TAHAP 3: KALKULASI ASHLUL MAS'ALAH ---
        denominators = sorted(list(set([
            Fraction(h['share_fraction_str'].split()[0]).denominator 
            for h in selected_heirs if '/' in h['share_fraction_str']
        ])))
        if denominators:
            notes.append(f"Penyebut yang ada: {', '.join(map(str, denominators))}.")
            ashlul_masalah_awal = math.lcm(*denominators)
        notes.append(f"Ashlul Mas'alah awal ditentukan: {ashlul_masalah_awal}.")

        ## --- TAHAP 4: PERHITUNGAN & DISTRIBUSI SAHAM ---
        jadd = next((h for h in selected_heirs if h['data'].name_id == "Kakek" and h['data'].name_id not in blocked_heirs), None)
        ikhwah = [h for h in selected_heirs if h['data'].name_id in jadd_wal_ikhwah.IKHWAH_NAMES and h['data'].name_id not in blocked_heirs]

        if jadd and ikhwah:
            # Kasus Jadd wal Ikhwah
            notes.append("Terdeteksi: Kasus Jadd wal Ikhwah.")
            other_dzawil_furudh = [h for h in selected_heirs if h not in ikhwah and h != jadd and '/' in h.get('share_fraction_str','')]
            for h in other_dzawil_furudh:
                h['saham'] = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
            
            jadd_result = jadd_wal_ikhwah.calculate_jadd_share(jadd, ikhwah, other_dzawil_furudh, ashlul_masalah_awal)
            
            jadd['saham'] = jadd_result['jadd_saham']
            jadd['reason'] = f"Bagian terbaik adalah {jadd_result['chosen_option']}."
            for h in ikhwah:
                h['saham'] = jadd_result['ikhwah_shares'].get(h['data'].id, 0)
                h['share_fraction_str'] = "Sisa (bersama Kakek)"
        else:
            # Perhitungan Saham Standar
            total_fardh_saham = 0
            for h in selected_heirs:
                if '/' in h['share_fraction_str']:
                    saham_val = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
                    if h['data'].name_id not in ["Saudara Laki-laki Seibu", "Saudari Seibu"]:
                        h['saham'] = saham_val
                        total_fardh_saham += saham_val
            
            seibu_heirs = [h for h in selected_heirs if h['data'].name_id in ["Saudara Laki-laki Seibu", "Saudari Seibu"] and '/' in h['share_fraction_str']]
            if seibu_heirs:
                seibu_total_saham = int(Fraction(seibu_heirs[0]['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
                total_fardh_saham += seibu_total_saham
                seibu_total_quantity = sum(h['quantity'] for h in seibu_heirs)
                if seibu_total_quantity > 0:
                    for h in seibu_heirs:
                        h['saham'] = (seibu_total_saham / seibu_total_quantity) * h['quantity']

            # Distribusi Sisa ke Ashobah
            remaining_saham = ashlul_masalah_awal - total_fardh_saham
            ashobah_heirs = [h for h in selected_heirs if h.get('is_ashobah') or h.get('is_ashobah_bil_ghair') or h.get('is_ashobah_maal_ghair')]
            if remaining_saham > 0 and ashobah_heirs:
                ashobah_heads = sum((2 if h['data'].name_id.startswith(("Anak Laki-laki", "Cucu Laki-laki", "Saudara Laki-laki", "Keponakan", "Paman", "Sepupu")) or h['data'].name_id in ["Ayah", "Kakek"] else 1) * h['quantity'] for h in ashobah_heirs)
                if ashobah_heads > 0:
                    for h in ashobah_heirs:
                        head_count = (2 if h['data'].name_id.startswith(("Anak Laki-laki", "Cucu Laki-laki", "Saudara Laki-laki", "Keponakan", "Paman", "Sepupu")) or h['data'].name_id in ["Ayah", "Kakek"] else 1)
                        h['saham'] += (remaining_saham * head_count) / ashobah_heads * h['quantity']
    
    # --- TAHAP FINAL: 'AUL, RADD, INKISAR, FINALISASI ---
    total_saham_final = sum(h.get('saham', 0) for h in selected_heirs)
    ashlul_masalah_akhir = ashlul_masalah_awal
    status = "Masalah 'Adilah (Pas)"
    if jadd and ikhwah:
        notes.append("Terdeteksi: Kasus Jadd wal Ikhwah.")
        other_dzawil_furudh = [h for h in selected_heirs if h not in ikhwah and h != jadd and '/' in h.get('share_fraction_str','')]
        for h in other_dzawil_furudh:
            h['saham'] = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
        
        jadd_result = jadd_wal_ikhwah.calculate_jadd_share(jadd, ikhwah, other_dzawil_furudh, ashlul_masalah_awal)
        
        jadd['saham'] = jadd_result['jadd_saham']
        jadd['reason'] = f"Bagian terbaik adalah {jadd_result['chosen_option']}."
        for h in ikhwah:
            h['saham'] = jadd_result['ikhwah_shares'].get(h['data'].id, 0)
            h['share_fraction_str'] = "Sisa (bersama Kakek)"
            
    else:
        for h in selected_heirs:
            if h.get('saham', 0) == 0 and '/' in h.get('share_fraction_str',''):
                h['saham'] = int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_awal)
        total_saham_final = sum(h.get('saham', 0) for h in selected_heirs)
    
    if not is_gharrawain:
        if round(total_saham_final) > ashlul_masalah_awal:
            ashlul_masalah_akhir = int(round(total_saham_final)); status = f"Masalah 'Aul (naik dari {ashlul_masalah_awal} menjadi {ashlul_masalah_akhir})"
        elif round(total_saham_final) < ashlul_masalah_awal and not any(h.get('is_ashobah') for h in selected_heirs):
            has_spouse = any(h['data'].name_id in ["Suami", "Istri"] for h in selected_heirs)
            if not has_spouse:
                ashlul_masalah_akhir = int(round(total_saham_final)); status = f"Masalah Radd (turun dari {ashlul_masalah_awal} menjadi {ashlul_masalah_akhir})"
            else:
                spouse = next((h for h in selected_heirs if h['data'].name_id in ["Suami", "Istri"]), None)
                radd_heirs = [h for h in selected_heirs if h != spouse]
                ashlul_masalah_spouse = Fraction(spouse['share_fraction_str'].split()[0]).denominator
                spouse['saham'] = 1
                remaining_saham_from_spouse_problem = ashlul_masalah_spouse - 1
                radd_denominators = sorted(list(set([Fraction(h['share_fraction_str'].split()[0]).denominator for h in radd_heirs if '/' in h['share_fraction_str']])))
                ashlul_masalah_radd = math.lcm(*radd_denominators) if radd_denominators else 1
                total_saham_radd_group = sum(int(Fraction(h['share_fraction_str'].split()[0]) * ashlul_masalah_radd) for h in radd_heirs)
                common_divisor = math.gcd(remaining_saham_from_spouse_problem, total_saham_radd_group)
                multiplier_spouse_problem = total_saham_radd_group // common_divisor
                multiplier_radd_problem = remaining_saham_from_spouse_problem // common_divisor
                ashlul_masalah_akhir = ashlul_masalah_spouse * multiplier_spouse_problem
                spouse['saham'] *= multiplier_spouse_problem
                for heir in radd_heirs: heir['saham'] = int(Fraction(heir['share_fraction_str'].split()[0]) * ashlul_masalah_radd) * multiplier_radd_problem
                status = f"Masalah Radd (dengan Suami/Istri), AM Gabungan: {ashlul_masalah_akhir}"
    notes.append(status)

    inkisar_groups = [h for h in selected_heirs if h.get('saham', 0) > 0 and (h.get('saham') * 1000) % (h['quantity'] * 1000) != 0]
    final_multiplier = 1
    if inkisar_groups:
        multipliers = [h['quantity'] // math.gcd(int(h['saham']), h['quantity']) for h in inkisar_groups]
        if multipliers: final_multiplier = math.lcm(*multipliers)
        if final_multiplier > 1:
            notes.append(f"Terjadi Inkisar. Dilakukan Tashihul Mas'alah: {ashlul_masalah_akhir} x {final_multiplier} = {ashlul_masalah_akhir * final_multiplier}")
            ashlul_masalah_akhir *= final_multiplier
            for heir in selected_heirs: heir['saham'] *= final_multiplier
    
    total_saham_final = sum(h.get('saham', 0) for h in selected_heirs)
    final_shares = []
    
    for heir in selected_heirs:
        final_saham = round(heir.get('saham', 0))
        share_amount = (tirkah / ashlul_masalah_akhir) * final_saham if ashlul_masalah_akhir > 0 else 0
        final_shares.append(schemas.HeirShare(heir=heir['data'], quantity=heir['quantity'], share_fraction=heir['share_fraction_str'], saham=final_saham, reason=heir['reason'], share_amount=share_amount))

    return schemas.CalculationResult(
        tirkah=tirkah, ashlul_masalah_awal=int(ashlul_masalah_awal), ashlul_masalah_akhir=int(ashlul_masalah_akhir),
        total_saham=round(total_saham_final), status=status, notes=notes, shares=final_shares
    )
# ΔΙΟΡΘΩΣΗ: Προσθέτει τις εισαγωγές που λείπουν
import sys
import json
import os

SCENARIO_FILE = sys.argv[1] if len(sys.argv) > 1 else "data.json"

def load_world_state(filename):
    if not os.path.exists(filename):
        print(f"Σφάλμα: Το αρχείο {filename} δεν υπάρχει.")
        sys.exit(1)
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_world_state(state, filename):
    # Αποθηκεύει τα αποτελέσματα σε νέο αρχείο 'results_...'
    result_file = "result_" + filename
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    print(f"[SYSTEM] Τα αποτελέσματα αποθηκεύτηκαν στο: {result_file}")

# Φόρτωση του επιλεγμένου σεναρίου
WORLD_STATE = load_world_state(SCENARIO_FILE)
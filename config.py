import subprocess
import time
import shutil
import importlib.util
import os
import sys

if __name__ == '__main__':
    print(f"running on local runtime")
    print(f"output gets sent: {os.getcwd()}")

seed = "1407931694"
assigned_domain = "Infrastructure Failure Management Agent"
base_path = "/Users/kostasniafas/Library/CloudStorage/GoogleDrive-dit21140@go.uop.gr/My Drive/Agent"
runs_path = os.path.join(base_path, "/runs")

# Δημιουργία φακέλου runs αν δεν υπάρχει
if os.path.exists(base_path):
    if not os.path.exists(runs_path):
        os.makedirs(runs_path)
        print(f"Created runs directory: {runs_path}")
else:
    print(f"Warning: Base path {base_path} not found. Runs folder not created there.")

#για να δεί άμα το path υπάρχει πριν προχωρήσει
if not os.path.exists(base_path):
    if __name__ == '__main__':
        print(f"Error: Το path δεν βρέθηκε: {base_path}")
else:
    if __name__ == '__main__':
        print(f"Path found: {base_path}")

seed_int = int(seed)
print_every = 100


# ΕΛΕΓΧΟΣ & ΕΓΚΑΤΑΣΤΑΣΗ OLLAMA
if not shutil.which("ollama"):
    print("Το Ollama δεν βρέθηκε. Γίνεται εγκατάσταση...")
    # Εγκατάσταση zstd (απαραίτητο για το colab extraction)
    subprocess.run(["sudo", "apt-get", "install", "-y", "zstd"], check=True)
    # Εγκατάσταση Ollama
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
else:
    print("✓ Το Ollama binary είναι ήδη εγκατεστημένο.")

# ΕΚΚΙΝΗΣΗ SERVER (ΑΝ ΔΕΝ ΤΡΕΧΕΙ ΗΔΗ) 
# Ελέγχουμε αν τρέχει ήδη κάτι στην πόρτα 11434
try:
    import urllib.request
    urllib.request.urlopen("http://localhost:11434")
    print("✓ Ο Ollama Server τρέχει ήδη.")
except:
    print("Εκκίνηση του Ollama Server στο background...")
    # Αρχεία καταγραφής για debugging
    with open("ollama_log.txt", "w") as log_file:
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=log_file,
            stderr=log_file
        )
    time.sleep(5) # Αναμονή για εκκίνηση

# --- 3. ΚΑΤΕΒΑΣΜΑ ΜΟΝΤΕΛΟΥ (ΑΝ ΔΕΝ ΥΠΑΡΧΕΙ) ---
# Ελέγχουμε αν το μοντέλο υπάρχει στη λίστα
result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
if "llama3.2:1b" not in result.stdout:
    print("Το μοντέλο llama3.2:1b δεν βρέθηκε. Κατέβασμα (αυτό μπορεί να πάρει λίγο)...")
    subprocess.run(["ollama", "pull", "llama3.2:1b"], check=True)
else:
    print("✓ Το μοντέλο llama3.2:1b είναι ήδη κατεβασμένο.")

# --- 4. ΕΓΚΑΤΑΣΤΑΣΗ ΒΙΒΛΙΟΘΗΚΗΣ PYTHON ---
if importlib.util.find_spec("ollama") is None:
    print("Εγκατάσταση βιβλιοθήκης Python 'ollama'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
else:
    print("✓ Η βιβλιοθήκη Python 'ollama' είναι ήδη εγκατεστημένη.")

print("\nΌλα έτοιμα! Μπορείς να τρέξεις τον Agent.")
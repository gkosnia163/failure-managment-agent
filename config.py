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
runs_path = os.path.join(base_path, "runs")

# Δημιουργία φακέλου runs (και του base_path αν λείπει)
try:
    os.makedirs(runs_path, exist_ok=True)
    if __name__ == '__main__':
        print(f"✓ Path found/created: {runs_path}")
except OSError:
    # Fallback σε local αν αποτύχει (π.χ. δεν υπάρχει το drive)
    base_path = os.getcwd()
    runs_path = os.path.join(base_path, "runs")
    os.makedirs(runs_path, exist_ok=True)
    if __name__ == '__main__':
        print(f"Warning: Drive path failed. Using local: {runs_path}")

seed_int = int(seed)
print_every = 100


# ΕΛΕΓΧΟΣ & ΕΓΚΑΤΑΣΤΑΣΗ OLLAMA
if not shutil.which("ollama"):
    print("Το Ollama δεν βρέθηκε. Γίνεται εγκατάσταση...")
    if sys.platform.startswith("win"):
        print("Εντοπίστηκαν Windows. Προσπάθεια εγκατάστασης μέσω winget...")
        try:
            subprocess.run(["winget", "install", "Ollama.Ollama"], check=True)
        except subprocess.CalledProcessError:
            print("Η εγκατάσταση απέτυχε. Παρακαλώ εγκαταστήστε το χειροκίνητα από https://ollama.com/download/windows")
    elif sys.platform.startswith("darwin") or sys.platform.startswith("linux"):
        print("Εντοπίστηκε macOS/Linux. Προσπάθεια εγκατάστασης...")
        # Εγκατάσταση zstd για Linux (αν υπάρχει apt-get - π.χ. Colab)
        if sys.platform.startswith("linux") and shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "install", "-y", "zstd"], check=True)
        # Εγκατάσταση Ollama με curl
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
if "lfm2.5-thinking:1.2b" not in result.stdout:
    print("Το μοντέλο lfm2.5-thinking:1.2b δεν βρέθηκε. Κατέβασμα (αυτό μπορεί να πάρει λίγο)...")
    subprocess.run(["ollama", "pull", "lfm2.5-thinking:1.2b"], check=True)
else:
    print("✓ Το μοντέλο lfm2.5-thinking:1.2b είναι ήδη κατεβασμένο.")

# --- 4. ΕΓΚΑΤΑΣΤΑΣΗ ΒΙΒΛΙΟΘΗΚΗΣ PYTHON ---
if importlib.util.find_spec("ollama") is None:
    print("Εγκατάσταση βιβλιοθήκης Python 'ollama'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
else:
    print("✓ Η βιβλιοθήκη Python 'ollama' είναι ήδη εγκατεστημένη.")

print("\nΌλα έτοιμα! Μπορείς να τρέξεις τον Agent.")
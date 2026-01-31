import subprocess
import time
import shutil
import importlib.util
import os
import sys
import json

Warning_message = """
\nΠΡΟΣΟΧΗ!
--------------------------------------------------------------------------
-Σε περίπτωση που δεν θα τρέξει το πρόγραμμα με API key, 
 κατεβαίνει το ollama και ανάλογο μοντέλο ≈ 4 GIGABYTE! <---ΠΡΟΣΟΧΗ 


-Για χρήση API key, απαιτείται η ένταξη API key στο config.py scripts
 Γραμμή 29 @config.py:
 CLOUD_API_KEY = "" #βάλτε το δικό σας API key apo https://console.groq.com -> φτιάξε account -> φτιάξε key βάλτο εδώ (συνήθως ξεκινάει με gsk_)
 Χρησιμοποιούμε την πλατφόρμα groq για τα κλειδιά μας, για δωρεάν χρήση (με όριο) μοντέλο openai-gpt-oss.128\n\n\n"""
print(Warning_message)

VERBOSE = True

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_config.json")

if os.path.exists(CONFIG_FILE) and __name__ != "__main__":
    with open(CONFIG_FILE, 'r') as f:
        USE_CLOUD = json.load(f).get("use_cloud", False)
else:
    if VERBOSE: cloud = input("Do you want to use Cloud LLM [y/n]: ")
    USE_CLOUD = (cloud.lower() == 'y') if VERBOSE else False
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"use_cloud": USE_CLOUD}, f)

# True = groq api | False = Ollama - local
if VERBOSE: print(f"[CONFIG] Cloud enabled: {USE_CLOUD}")
CLOUD_PROVIDER = "groq"  # 'groq' ή 'openai'


#----ΒΑΛΤΕ ΤΟ groq api key παρακάτω ανάμεσα στα CLOUD_API_KEY = "here"----
################################################################################################################################################
CLOUD_API_KEY = "" #βάλτε το δικό σας API key apo https://console.groq.com -> φτιάξε account -> φτιάξε key βάλτο εδώ (συνήθως ξεκινάει με gsk_)
################################################################################################################################################


CLOUD_MODEL = "openai/gpt-oss-120b"

if __name__ == '__main__':
    if VERBOSE: print(f"[CONFIG] downlods probably get sent: {os.getcwd()}")

seed = "1407931694"
assigned_domain = "Infrastructure Failure Management Agent"


#----ΒΑΛΤΕ ΤΟ path που θέλετε να πηγαίνουν τα runs σας (κενό = πάνε στο ίδιο μέρος με αυτό το script)----
#################################################################################################################################################
base_path = r"" #    <-ανάμεσα απο τα ""    
runs_path = os.path.join(base_path, "")
#################################################################################################################################################

# Δημιουργία φακέλου runs (και του base_path αν λείπει)
try:
    os.makedirs(runs_path, exist_ok=True)
    if __name__ == '__main__':
        if VERBOSE: print(f"[CONFIG] Path found/created: {runs_path}")
except OSError:
    # Fallback σε local αν αποτύχει (π.χ. δεν υπάρχει το drive)
    base_path = os.getcwd()
    runs_path = os.path.join(base_path, "runs")
    os.makedirs(runs_path, exist_ok=True)
    if __name__ == '__main__':
        if VERBOSE: print(f"[CONFIG] Warning: Drive path failed. Using local: {runs_path}")

seed_int = int(seed)
print_every = 100


# ΕΛΕΓΧΟΣ & ΕΓΚΑΤΑΣΤΑΣΗ OLLAMA (ΜΟΝΟ ΑΝ ΔΕΝ ΕΙΝΑΙ CLOUD)
if not USE_CLOUD:
    if not shutil.which("ollama"):
        if VERBOSE: print("[CONFIG] Το Ollama δεν βρέθηκε. Γίνεται εγκατάσταση...")
        if sys.platform.startswith("win"):
            if VERBOSE: print("[CONFIG] Εντοπίστηκαν Windows. Προσπάθεια εγκατάστασης μέσω winget...")
            try:
                subprocess.run(["winget", "install", "Ollama.Ollama"], check=True)
            except subprocess.CalledProcessError:
                if VERBOSE: print("[CONFIG] Η εγκατάσταση απέτυχε. Παρακαλώ εγκαταστήστε το χειροκίνητα από https://ollama.com/download/windows")
        elif sys.platform.startswith("darwin") or sys.platform.startswith("linux"):
            if VERBOSE: print("[CONFIG] Εντοπίστηκε macOS/Linux. Προσπάθεια εγκατάστασης...")
            if sys.platform.startswith("linux") and shutil.which("apt-get"):
                subprocess.run(["sudo", "apt-get", "install", "-y", "zstd"], check=True)
            subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    else:
        if VERBOSE: print("[CONFIG] Το Ollama binary είναι ήδη εγκατεστημένο.")

    # ΕΚΚΙΝΗΣΗ SERVER
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434")
        if VERBOSE: print("[CONFIG] Ο Ollama Server τρέχει ήδη.")
    except:
        if VERBOSE: print("[CONFIG] Εκκίνηση του Ollama Server στο background...")
        with open("ollama_log.txt", "w") as log_file:
            subprocess.Popen(["ollama", "serve"], stdout=log_file, stderr=log_file)
        time.sleep(5)

    # ΚΑΤΕΒΑΣΜΑ ΜΟΝΤΕΛΟΥ
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if "qwen3:4b" not in result.stdout:
        if VERBOSE: print("[CONFIG] Το μοντέλο qwen3:4b δεν βρέθηκε. Κατέβασμα...")
        subprocess.run(["ollama", "pull", "qwen3:4b"], check=True)

    # ΕΓΚΑΤΑΣΤΑΣΗ ΒΙΒΛΙΟΘΗΚΗΣ PYTHON OLLAMA
    if importlib.util.find_spec("ollama") is None:
        if VERBOSE: print("[CONFIG] Εγκατάσταση βιβλιοθήκης Python 'ollama'...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])

if importlib.util.find_spec("openai") is None:
    if VERBOSE: print("[CONFIG] Εγκατάσταση βιβλιοθήκης Python 'openai' (για Cloud)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])

if VERBOSE: print("\n[CONFIG] Όλα έτοιμα! Μπορείς να τρέξεις τον Agent.")

WORLD_STATE = {} #global ώστε να μην μπερδεύονται με την main του 'core.py' 
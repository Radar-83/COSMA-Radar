import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SCRIPTS = [
    "01_Scraper.py",
    "02_Cleaner.py",
    "03_Enricher.py",
    "04_Notation.py",
    "05_excel_to_json.py",
]

def run_script(name: str) -> int:
    script_path = BASE_DIR / name
    if not script_path.exists():
        print(f"[ERREUR] Le fichier {name} est introuvable.", flush=True)
        return 1

    print(f"\n\033[96m--- Exécution de {name} ---\033[0m", flush=True)
    p = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in iter(p.stdout.readline, ''):
        print(line.rstrip(), flush=True)
    p.stdout.close()
    p.wait()

    if p.returncode != 0:
        print(f"\033[91m[ERREUR] dans {name} (code {p.returncode})\033[0m", flush=True)
    else:
        print(f"\033[92m[SUCCESS] {name} terminé\033[0m", flush=True)

    return p.returncode

def main():
    for script in SCRIPTS:
        rc = run_script(script)
        if rc != 0:
            sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()

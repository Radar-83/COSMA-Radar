# Créez ce fichier comme test_executable.py dans le dossier public/
import sys
import os
from pathlib import Path

print("=== TEST D'EXÉCUTION ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Script location: {__file__}")

BASE_DIR = Path(__file__).resolve().parent
print(f"Base directory: {BASE_DIR}")

# Vérifiez la présence des scripts requis
SCRIPTS = [
    "01_Scraper.py",
    "02_Cleaner.py", 
    "03_Enricher.py",
    "04_Notation.py",
    "05_excel_to_json.py",
]

print("\n=== VÉRIFICATION DES FICHIERS ===")
for script in SCRIPTS:
    script_path = BASE_DIR / script
    exists = script_path.exists()
    print(f"{script}: {'✓ TROUVÉ' if exists else '✗ MANQUANT'}")
    if not exists:
        print(f"  Chemin recherché: {script_path}")

# Listez tous les fichiers .py dans le dossier
print(f"\n=== FICHIERS .py DANS {BASE_DIR} ===")
for py_file in BASE_DIR.glob("*.py"):
    print(f"  {py_file.name}")

print("\n=== FIN DU TEST ===")
sys.exit(0)  # Sortie propre
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
EXCEL_FILE = BASE / "Scored_Enriched.xlsx"
OUTPUT_JSON = BASE / "Scored_Enriched_clean.json"

# --- utilitaires fichiers ---
def file_exists(p: Path) -> bool:
    return p.exists()

def remove_if_exists(p: Path) -> None:
    if p.exists():
        p.unlink()

# --- nettoyage ---
def clean_value(value, default="N/A", max_length=50_000):
    if pd.isna(value):
        return default
    if isinstance(value, str):
        return value.strip()[:max_length]
    return value

def sanitize_df(df: pd.DataFrame, default="N/A", max_length=50_000) -> pd.DataFrame:
    for col in df.columns:
        df[col] = df[col].apply(lambda x: clean_value(x, default=default, max_length=max_length))
    return df

# --- lecture Excel robuste ---
def read_excel_df(path: Path, sheet="first") -> pd.DataFrame:
    """
    sheet:
      - "first" (défaut) : première feuille
      - "all"            : concatène toutes les feuilles
      - int              : index de feuille (0, 1, 2, …)
      - str              : nom de feuille
    """
    if sheet == "first":
        return pd.read_excel(path, sheet_name=0)            # <-- renvoie un DataFrame
    if sheet == "all":
        dct = pd.read_excel(path, sheet_name=None)          # dict[str, DataFrame]
        return pd.concat(dct.values(), ignore_index=True)
    # int ou str
    return pd.read_excel(path, sheet_name=sheet)

# --- pipeline ---
def save_json(records, path: Path, indent=2) -> None:
    remove_if_exists(path)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=indent), encoding="utf-8")

def clean_and_convert_excel(input_excel: Path, output_json: Path, sheet="first") -> None:
    print(f"[debug] script_dir={BASE}")
    print(f"[debug] excel_path={input_excel} (sheet={sheet})")

    if not file_exists(input_excel):
        print(f"Le fichier {input_excel} est introuvable.")
        return

    # Assurez-vous d'avoir 'openpyxl' installé: pip install openpyxl
    df = read_excel_df(input_excel, sheet=sheet)
    df = sanitize_df(df)

    data = df.to_dict(orient="records")
    save_json(data, output_json)

    print(f"Conversion terminée. {len(data)} lignes sauvegardées dans {output_json}")

if __name__ == "__main__":
    clean_and_convert_excel(EXCEL_FILE, OUTPUT_JSON, sheet="first")

import pandas as pd
import re
import os

# Fonction de nettoyage sans emojis
def clean_text(text):
    if pd.isna(text):
        return ""
    text = re.sub(r"http\S+", "", text)                 
    text = re.sub(r"@[A-Za-z0-9_]+", "", text)          
    text = re.sub(r"#\S+", "", text)                    
    text = re.sub(r"[^\x00-\x7F]+", "", text)           
    text = re.sub(r"[^\w\s]", "", text)                 
    return text.lower().strip()

def load_data(filepath="Scraped.xlsx"):
    return pd.read_excel(filepath)

# Nettoyage 
def enrich_data(df):
    # Nettoyer post_text (remplacer la colonne originale)
    df["post_text"] = df["post_text"].apply(clean_text).str[:100000]
    df = df.drop_duplicates(subset=["post_id"])
    return df

def main():
    df = load_data()
    df = enrich_data(df)
    
    # Supprimer le fichier existant s'il existe pour le remplacer
    output_file = "Cleaned.xlsx"
    if os.path.exists(output_file):
        os.remove(output_file)
    
    df.to_excel(output_file, index=False)
    print(f"Fichier nettoyé généré : {output_file}")

if __name__ == "__main__":
    main()

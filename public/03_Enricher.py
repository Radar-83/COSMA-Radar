import os
import re
import json
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from random import uniform
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

# === SETTINGS ===
INPUT_FILE = "Cleaned.xlsx"
OUTPUT_FILE = "Enriched.xlsx"

# --- Nouveau schéma de logs ---
LOG_FILE = "log_03.csv"        # CSV append-only succès/erreurs
LOG_TXT = "log.txt"            # Liste simple d'index traités (reprise)
BATCH_SAVE = 50                # Sauvegarde vers Enriched.xlsx toutes les N lignes

SLEEP_MIN, SLEEP_MAX = 1.5, 3.0
DEBUG = False

# Colonnes à logger (append dans LOG_FILE, dédupliquées sur 'index' à l'export)
COLUMNS_TO_LOG = [
    "index", "company_name", "website", "location",
    "one_sentence_description",
    "professional_email", "post_author", "author_role",
    "city", "country", "web_source_used", "inference_confidence",
    "theme", "post_url", "error"
]

# === UTILITAIRES WEB ===
def duckduckgo_search_with_urls(query, max_results=3):
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        for link in soup.select(".result__a")[:max_results]:
            href = link.get("href")
            if href and href.startswith("http"):
                results.append(href)
        return results
    except Exception as e:
        print(f"[ERROR] DuckDuckGo search failed: {str(e)}")
        return []

def scrape_page_text(url):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        meta = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
        paragraphs = " ".join(p.get_text(strip=True) for p in soup.find_all("p")[:5])
        return f"[URL: {url}]\nTitle: {title}\nMeta: {meta}\nContent: {paragraphs[:1000]}"
    except Exception as e:
        return f"[URL: {url}] - Failed to scrape: {str(e)}"

# === JSON SAFE PARSE ===
def safe_json_parse(response_text):
    """Safely parse JSON from LLM response"""
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print(f"[WARNING] No JSON found in response: {response_text[:200]}...")
            return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed: {str(e)}")
        print(f"Response was: {response_text[:200]}...")
        return {}

# === LOGGING (CSV + TXT) ===
def ensure_log_headers():
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=COLUMNS_TO_LOG).to_csv(LOG_FILE, index=False)

def load_logged_items_from_csv():
    if os.path.exists(LOG_FILE):
        try:
            logged_df = pd.read_csv(LOG_FILE, usecols=["index"])
            return set(logged_df["index"].tolist())
        except Exception:
            return set()
    return set()

def load_logged_items_from_txt():
    if not os.path.exists(LOG_TXT):
        return set()
    items = set()
    with open(LOG_TXT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.isdigit() or (line and line.lstrip("-").isdigit()):
                items.add(int(line))
    return items

def append_log_txt(item_id):
    try:
        with open(LOG_TXT, "a", encoding="utf-8") as f:
            f.write(f"{item_id}\n")
    except Exception as e:
        print(f"[WARNING] Failed to append to {LOG_TXT}: {e}")

def clear_log_txt():
    try:
        if os.path.exists(LOG_TXT):
            os.remove(LOG_TXT)
    except Exception as e:
        print(f"[WARNING] Failed to clear {LOG_TXT}: {e}")

def _append_log_row(row_dict):
    # Écrit une ligne dans LOG_FILE en respectant l'ordre des colonnes
    try:
        pd.DataFrame([row_dict])[COLUMNS_TO_LOG].to_csv(LOG_FILE, mode="a", header=False, index=False)
    except Exception as e:
        print(f"[ERROR] Failed writing to {LOG_FILE}: {e}")

def save_enriched_snapshot(df_input):
    """Fusionne df_input (Cleaned.xlsx) avec le LOG_FILE dédupliqué, puis écrit OUTPUT_FILE."""
    try:
        if not os.path.exists(LOG_FILE):
            # Si pas de log, exporter seulement l'input
            df_input.to_excel(OUTPUT_FILE, index=False)
            return
        log_df = pd.read_csv(LOG_FILE)
        # Déduplication stricte sur 'index' (on garde la dernière occurrence)
        log_df = log_df.drop_duplicates(subset=["index"], keep="last")
        merged = df_input.merge(log_df, how="left", left_index=True, right_on="index")
        merged.to_excel(OUTPUT_FILE, index=False)
    except Exception as e:
        print(f"[WARNING] Failed to save snapshot to {OUTPUT_FILE}: {e}")

# === MAIN ===
def main():
    # Lecture input
    df = pd.read_excel(INPUT_FILE)
    print(f"[INFO] Total rows: {len(df)}")

    # Prépare fichiers de log
    ensure_log_headers()

    # Reprise: indices déjà faits
    already_done_csv = load_logged_items_from_csv()
    processed_items_txt = load_logged_items_from_txt()
    already_done = already_done_csv.union(processed_items_txt)
    print(f"[INFO] Already processed rows (CSV+TXT): {len(already_done)}")

    # LLM
    llm = OllamaLLM(model="mistral", temperature=0)

    # --- Prompt inférence nom de société (inchangé) ---
    inference_prompt = PromptTemplate(
        input_variables=["author_name", "author_role", "post_text"],
        template="""
You are a professional assistant. Based on the following LinkedIn post and author info, infer the name of the company the author works at.
Author: {author_name}
Role: {author_role}
Post: {post_text}
Return the result in this strict JSON format:
{{
  "inferred_company_name": "..."
}}
If the company cannot be determined, return:
{{
  "inferred_company_name": "Not found"
}}
"""
    )
    inference_chain = inference_prompt | llm

    # --- Prompt classification du thème (5 catégories fixes) ---
    theme_prompt = PromptTemplate(
        input_variables=["post_text"],
        template="""
You are an expert in marine and offshore infrastructure. Based on the LinkedIn post below, classify the topic into one of the following categories:
- MARINE INFRASTRUCTURE
- PIPELINES
- SUBMARINE CABLES
- OFFSHORE WIND FARMS
- OTHER
Post:
"{post_text}"
Return your answer in this strict JSON format:
{{
  "theme": "..."
}}
"""
    )
    theme_chain = theme_prompt | llm

    # --- Prompt enrichissement (inchangé) ---
    enrichment_prompt = PromptTemplate(
        input_variables=["post_text", "company_name", "author_name", "author_role", "city", "country", "web_snippets"],
        template="""
You are a B2B research assistant. Your task is to enrich company information based on the provided data and web content.
Here is the available data:
LinkedIn Post:
"{post_text}"
Author: {author_name}
Role: {author_role}
City: {city}
Country: {country}
Company Name: {company_name}
Web content collected:
{web_snippets}
Instructions:
1. Use the provided company name to find information
2. Identify the official website of the company using the most trustworthy source
3. Extract or infer the location/headquarters of the company
5. Provide a one-sentence description of what the company does
6. Infer a likely professional email addresss — e.g., info@company.com or firstname.lastname@company.com — based on the company domain and author name
7. If any information cannot be found confidently, say "Not found"
Return this strict JSON format:
{{
  "company_name": "{company_name}",
  "website": "...",
  "location": "...",
  "one_sentence_description": "...",
  "professional_email": "...",
  "web_source_used": "...",
  "inference_confidence": "e.g. 90%"
}}
"""
    )
    enrichment_chain = enrichment_prompt | llm

    # === Cache du thème: clé (company_name|author_name) ===
    theme_cache = {}

    processed_since_save = 0

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Enriching"):
        if idx in already_done:
            continue

        post_text = str(row.get("post_text", "")).strip()[:1000]
        author_name = str(row.get("author_name", "")).strip()
        author_role = str(row.get("author_role", "")).strip()
        city = str(row.get("city", "")).strip()
        country = str(row.get("country", "")).strip()
        company_name = str(row.get("company_name", "")).strip()
        post_url = str(row.get("post_url", "")).strip()  # --- nouveau transfert pur ---

        # 1) Inférence nom société si manquant
        if not company_name or company_name.lower() in ['nan', 'none', '']:
            try:
                print(f"[INFO] Inferring company name for row {idx}...")
                inferred_response = inference_chain.invoke({
                    "author_name": author_name,
                    "author_role": author_role,
                    "post_text": post_text
                })
                parsed_inference = safe_json_parse(inferred_response)
                company_name = parsed_inference.get("inferred_company_name", "")
                if company_name and company_name.lower() != "not found":
                    print(f"[INFO] Successfully inferred company at row {idx}: {company_name}")
                else:
                    company_name = ""
                    print(f"[INFO] Could not infer company name for row {idx}")
            except Exception as e:
                print(f"[ERROR] Company inference failed at row {idx}: {str(e)}")
                company_name = ""

        # Skip si données essentielles manquantes
        if not post_text or not author_name or not company_name:
            result = {
                "index": idx,
                "company_name": company_name or "Missing",
                "website": "Missing",
                "location": "Missing",
                "one_sentence_description": "Missing",
                "professional_email": "Missing",
                "post_author": author_name or "Missing",
                "author_role": author_role,
                "city": city,
                "country": country,
                "web_source_used": "",
                "inference_confidence": "",
                "theme": "OTHER" if post_text else "Missing",
                "post_url": post_url,
                "error": "Missing essential fields"
            }
            _append_log_row(result)
            append_log_txt(idx)
            processed_since_save += 1
            if processed_since_save >= BATCH_SAVE:
                save_enriched_snapshot(df)
                processed_since_save = 0
            time.sleep(uniform(SLEEP_MIN, SLEEP_MAX))
            continue

        # 2) Enrichissement via recherche web
        try:
            print(f"[INFO] Enriching data for {company_name} (row {idx})...")
            urls = duckduckgo_search_with_urls(f'"{company_name}" official website headquarters about')
            if not urls:
                urls = duckduckgo_search_with_urls(f"{company_name} company")
            snippets = "\n\n".join([scrape_page_text(url) for url in urls]) if urls else "No web content available"
            if DEBUG:
                print(f"\n[DEBUG] Web snippets for {company_name}:\n{snippets[:500]}...\n")

            response = enrichment_chain.invoke({
                "post_text": post_text,
                "company_name": company_name,
                "author_name": author_name,
                "author_role": author_role,
                "city": city,
                "country": country,
                "web_snippets": snippets
            })
            parsed = safe_json_parse(response)

            # 3) Thème (avec cache)
            cache_key = f"{company_name}|{author_name}"
            if cache_key in theme_cache:
                theme = theme_cache[cache_key]["theme"]
            else:
                try:
                    theme_response = theme_chain.invoke({"post_text": post_text})
                    parsed_theme = safe_json_parse(theme_response)
                    theme = parsed_theme.get("theme", "OTHER")
                except Exception as e:
                    print(f"[ERROR] Theme classification failed for row {idx}: {str(e)}")
                    theme = "OTHER"
                    parsed_theme = {}
                # Mise en cache
                theme_cache[cache_key] = {"parsed": parsed_theme if 'parsed_theme' in locals() else {}, "theme": theme}

            result = {
                "index": idx,
                "company_name": parsed.get("company_name", company_name),
                "website": parsed.get("website", "Not found"),
                "location": parsed.get("location", "Not found"),
                "one_sentence_description": parsed.get("one_sentence_description", "Not found"),
                "professional_email": parsed.get("professional_email", "Not found"),
                "post_author": author_name,
                "author_role": author_role,
                "city": city,
                "country": country,
                "web_source_used": parsed.get("web_source_used", ", ".join(urls) if urls else ""),
                "inference_confidence": parsed.get("inference_confidence", "Not specified"),
                "theme": theme,
                "post_url": post_url,
                "error": ""
            }

        except Exception as e:
            print(f"[ERROR] Enrichment failed for row {idx}: {str(e)}")
            result = {
                "index": idx,
                "company_name": company_name,
                "website": "Error",
                "location": "Error",
                "one_sentence_description": "Error",
                "professional_email": "Error",
                "post_author": author_name,
                "author_role": author_role,
                "city": city,
                "country": country,
                "web_source_used": ", ".join(urls) if 'urls' in locals() else "",
                "inference_confidence": "",
                "theme": "OTHER",
                "post_url": post_url,
                "error": str(e)
            }

        # 4) Log CSV append-only + log.txt (reprise)
        _append_log_row(result)
        append_log_txt(idx)

        # 5) Sauvegarde par lot (merge + dédup sur 'index')
        processed_since_save += 1
        if processed_since_save >= BATCH_SAVE:
            save_enriched_snapshot(df)
            processed_since_save = 0

        # Pause anti-rate-limit
        time.sleep(uniform(SLEEP_MIN, SLEEP_MAX))

    # === Sortie finale ===
    print("\n[INFO] Creating final output file...")
    save_enriched_snapshot(df)
    print(f"[INFO] Enriched file saved as: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

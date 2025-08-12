import os
import re
import json
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from random import uniform
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

# === SETTINGS (paths resolved relative to this script) ===
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = Path(os.environ.get("INPUT_FILE", "Enriched.xlsx"))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", "Scored_Enriched.xlsx"))
LOG_FILE = Path(os.environ.get("LOG_FILE", "log_04.txt"))
SLEEP_MIN, SLEEP_MAX = 1.5, 3.0

# Make relative paths point to the script folder
if not INPUT_FILE.is_absolute():
    INPUT_FILE = BASE_DIR / INPUT_FILE
if not OUTPUT_FILE.is_absolute():
    OUTPUT_FILE = BASE_DIR / OUTPUT_FILE
if not LOG_FILE.is_absolute():
    LOG_FILE = BASE_DIR / LOG_FILE

print(f"Script dir: {BASE_DIR}")
print(f"CWD:        {Path.cwd()}")
print(f"INPUT_FILE: {INPUT_FILE}")

# Preflight: ensure the input exists
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"INPUT_FILE not found at: {INPUT_FILE}")

# === LOGGING FUNCTIONS ===
def load_logged_items():
    if not LOG_FILE.exists():
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def append_log(item_id):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{item_id}\n")

def clear_log():
    LOG_FILE.write_text("", encoding="utf-8")

# === SEARCH FUNCTION ===
def duckduckgo_search(query):
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        results = [a.text.strip() for a in soup.select(".result__a")]
        if not results:
            return "No relevant web results found."
        return "\n".join(results[:5])
    except Exception as e:
        return f"Web search unavailable ({e})."

# 1. Project Summary and phase
project_analysis_prompt = PromptTemplate(
    input_variables=["post_text", "company_name", "web_results"],
    template="""
You are analyzing a LinkedIn post for COSMA, a company that develops autonomous underwater vehicles (AUVs) for marine surveys.

COSMA'S TARGET SECTORS:
- Offshore wind farms (site surveys, UXO detection, foundation inspection)
- Submarine cables (power/telecom cable installation, route planning)
- Pipelines (oil, gas, hydrogen - route clearance, UXO detection)
- Marine infrastructure (ports, coastal construction)

TASK: Analyze this post and provide:
1. A brief project summary (2-3 sentences)
2. Project phase classification (Planning/Survey/Construction/Operational)
3. Key relevant keywords found in the post

Post: {post_text}
Company: {company_name}
Web Results: {web_results}

Return in this format:
PROJECT_SUMMARY: [2-3 sentence summary]
PROJECT_PHASE: [Planning/Survey/Construction/Operational]
KEYWORDS: [comma-separated relevant keywords]
"""
)

# 2. Scoring
scoring_prompt = PromptTemplate(
    input_variables=["post_text", "project_summary", "company_name", "author_role", "one_sentence_description"],
    template="""
Score this opportunity for COSMA's AUV services on three criteria (0-100 each):

SCORING CRITERIA:
1. PROJECT_RELEVANCE (0-100):
   - 90-100: Direct mentions of offshore wind, submarine cables, or pipelines
   - 70-89: Marine infrastructure, subsea construction projects
   - 50-69: General offshore/marine activities
   - 30-49: Peripheral maritime relevance
   - 0-29: Not relevant to marine surveys

2. PROJECT_STAGE (0-100):
   - 90-100: Early-stage (feasibility, site selection, planning)
   - 70-89: Environmental impact studies, pre-construction
   - 50-69: Pre-installation, technical planning
   - 30-49: Active construction
   - 0-29: Maintenance or completed

3. COMPANY_FIT (0-100):
   - 90-100: Large offshore energy firms, cable/pipeline developers
   - 70-89: Marine survey/engineering firms
   - 50-69: Construction companies with marine capabilities
   - 30-49: Occasional marine involvement
   - 0-29: Not relevant

INPUT:
Post: {post_text}
Project Summary: {project_summary}
Company: {company_name}
Author Role: {author_role}
Company Description: {one_sentence_description}

Return only in this format:
PROJECT_RELEVANCE: [score]
PROJECT_STAGE: [score]
COMPANY_FIT: [score]
"""
)

# 3. Cosma Opportunity (tight, single-sentence with evidence + capability)
opportunity_analysis_prompt = PromptTemplate(
    input_variables=["post_text", "project_summary", "company_name"],
    template="""
You are writing one specific reason linking this project to one COSMA capability.

COSMA CAPABILITIES (choose ONE):
- Photogrammetry (3D inspection/foundations)
- Sonar & multibeam echosounders (bathymetry, cable/route mapping)
- Sub-bottom profilers (sediment layers, route clearance)
- Magnetometers (UXO detection)

RULES:
- Pick the single best-matching capability.
- Use a concrete cue from the post or summary as evidence (quote a keyword/phrase).
- One sentence, 25 words max. No lists or extra fields.

INPUT:
Post: {post_text}
Project Summary: {project_summary}
Company: {company_name}

Return EXACTLY:
COSMA_OPPORTUNITY: Because [evidence], COSMA can [outcome] using [capability].
CAPABILITY: [one of the four above]
EVIDENCE: "[quoted keyword/phrase]"
"""
)

# 4. Contact & Action Recommendations
contact_action_prompt = PromptTemplate(
    input_variables=["author_name", "author_role", "project_summary", "relevance_score", "stage_score", "company_score"],
    template="""
Provide contact and action recommendations based on the analysis:

INPUT:
Author: {author_name}
Role: {author_role}
Project: {project_summary}
Scores: Relevance={relevance_score}, Stage={stage_score}, Company={company_score}

ACTION GUIDELINES:
- High scores (>70): "Reach out immediately"
- Medium scores (40-70): "Monitor for developments"
- Low scores (<40): "Low priority - archive"

Return in this format:
IDEAL_CONTACT: [Who to contact and why]
RECOMMENDED_ACTION: [Next step recommendation]
REASONING: [Brief explanation of scores and recommendations]
"""
)

# === INITIALIZE LLM AND CHAINS ===
llm = OllamaLLM(model="mistral", temperature=0)

project_analysis_chain = project_analysis_prompt | llm
scoring_chain = scoring_prompt | llm
opportunity_chain = opportunity_analysis_prompt | llm
contact_action_chain = contact_action_prompt | llm

geo_chain = PromptTemplate(
    input_variables=["city", "country"],
    template="""Estimate the accessibility score (0-100) for COSMA to operate based on the city and country. Coastal European areas are high priority.
City: {city}
Country: {country}
Return only the number."""
) | llm

# === HELPER FUNCTIONS ===
def extract_field(text, field_name):
    """Extract a specific field from structured LLM response."""
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?=\n[A-Z_]+:|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_score(text, field_name):
    """Extract numeric score from structured response."""
    field_text = extract_field(text, field_name)
    score_match = re.search(r"\d+", field_text)
    return int(score_match.group()) if score_match else 0

def enforce_one_sentence(text, max_words=25):
    """Keep the first sentence and hard-cap to max_words."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    first = re.split(r"(?<=[.!?])\s", text)[0] if text else ""
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words]).rstrip(".") + "."
    return first

# === LOAD EXCEL INPUT ===
df = pd.read_excel(INPUT_FILE)
results = []
logged_items = load_logged_items()

# === MAIN PROCESSING LOOP ===
for idx, row in tqdm(df.iterrows(), total=len(df), desc="Scoring LinkedIn posts for COSMA"):
    try:
        item_id = str(row.get("item_id", idx))
        if item_id in logged_items:
            continue  # Skip already processed

        # Robust fallbacks for missing fields
        post_text = str(
            row.get("post_text")
            or row.get("one_sentence_description")
            or row.get("post")
            or row.get("content")
            or row.get("text")
            or ""
        )[:1500]

        raw_company_name = row.get("company_name", "")

        author_name = str(
            row.get("author_name")
            or row.get("post_author")
            or row.get("author")
            or row.get("profile_name")
            or row.get("author_full_name")
            or ""
        )

        author_role = str(row.get("author_role", ""))
        city = str(row.get("city", ""))
        country = str(row.get("country", ""))
        website = str(row.get("website", ""))
        one_sentence_description = str(row.get("one_sentence_description", ""))
        post_url = str(row.get("post_url") or row.get("post_url_x") or row.get("post_url_y") or "")

        if not post_text or not author_name:
            row_dict = row.to_dict()
            row_dict["error"] = "Missing required fields"
            results.append(row_dict)
            continue

        # Web search
        search_query = f"{website} offshore marine survey {city} {country}"
        web_results = duckduckgo_search(search_query)

        final_company_name = (
            raw_company_name.strip()
            if isinstance(raw_company_name, str) and raw_company_name.strip()
            else "Company name not identified"
        )

        # STEP 1: Project Analysis
        analysis_response = project_analysis_chain.invoke({
            "post_text": post_text,
            "company_name": final_company_name,
            "web_results": web_results
        })

        project_summary = extract_field(analysis_response, "PROJECT_SUMMARY")
        project_phase = extract_field(analysis_response, "PROJECT_PHASE")
        relevant_keywords = extract_field(analysis_response, "KEYWORDS")

        # STEP 2: Scoring
        scoring_response = scoring_chain.invoke({
            "post_text": post_text,
            "project_summary": project_summary,
            "company_name": final_company_name,
            "author_role": author_role,
            "one_sentence_description": one_sentence_description
        })

        project_relevance = extract_score(scoring_response, "PROJECT_RELEVANCE")
        project_stage = extract_score(scoring_response, "PROJECT_STAGE")
        company_fit = extract_score(scoring_response, "COMPANY_FIT")

        # STEP 3: Opportunity Analysis
        opportunity_response = opportunity_chain.invoke({
            "post_text": post_text,
            "project_summary": project_summary,
            "company_name": final_company_name
        })

        cosma_opportunity = extract_field(opportunity_response, "COSMA_OPPORTUNITY")
        opportunity_capability = extract_field(opportunity_response, "CAPABILITY")
        opportunity_evidence = extract_field(opportunity_response, "EVIDENCE")

        # Enforce single concise sentence (belt-and-braces)
        cosma_opportunity = enforce_one_sentence(cosma_opportunity, 25)

        # STEP 4: Contact & Action Recommendations
        contact_response = contact_action_chain.invoke({
            "author_name": author_name,
            "author_role": author_role,
            "project_summary": project_summary,
            "relevance_score": project_relevance,
            "stage_score": project_stage,
            "company_score": company_fit
        })

        ideal_contact = extract_field(contact_response, "IDEAL_CONTACT")
        recommended_action = extract_field(contact_response, "RECOMMENDED_ACTION")
        reasoning = extract_field(contact_response, "REASONING")

        # Geo score
        geo_score_raw = geo_chain.invoke({"city": city, "country": country}).strip()
        digits = re.findall(r"\d+", geo_score_raw)
        geo_score = int(digits[0]) if digits else 0

        # Calculate global score
        global_score = 0.50 * project_relevance + 0.35 * project_stage + 0.15 * company_fit
        if geo_score > 70:
            global_score = min(100, global_score + 2)

        # Save results
        row_dict = row.to_dict()
        row_dict.update({
            "company_name": final_company_name,
            "geographic_accessibility": geo_score,
            "project_summary": project_summary,
            "project_phase": project_phase,
            "relevant_keywords": relevant_keywords,
            "cosma_opportunity": cosma_opportunity,
            "opportunity_capability": opportunity_capability,
            "opportunity_evidence": opportunity_evidence,
            "ideal_contact": ideal_contact,
            "recommended_action": recommended_action,
            "reasoning": reasoning,
            "score_project_relevance": project_relevance,
            "score_project_stage": project_stage,
            "score_company_fit": company_fit,
            "score_global": round(global_score, 1),
            "post_url": post_url
        })

        results.append(row_dict)
        append_log(item_id)

    except Exception as e:
        row_dict = row.to_dict()
        row_dict["error"] = str(e)
        results.append(row_dict)

    time.sleep(uniform(SLEEP_MIN, SLEEP_MAX))

# === EXPORT TO EXCEL (APPEND + DEDUP) ===
final_df = pd.DataFrame(results)

if OUTPUT_FILE.exists():
    existing_df = pd.read_excel(OUTPUT_FILE)
    final_df = pd.concat([existing_df, final_df], ignore_index=True)

# Remove duplicates based on item_id if exists
if "item_id" in final_df.columns:
    final_df = final_df.drop_duplicates(subset=["item_id"], keep="last")

# Safe sort (avoid KeyError if nothing scored)
if "score_global" in final_df.columns:
    final_df = final_df.sort_values("score_global", ascending=False)
else:
    print("No 'score_global' column found; writing output without sorting. "
          "This usually means inputs were missing (e.g., post_text/author_name).")

final_df.to_excel(OUTPUT_FILE, index=False)

print(f"File saved: {OUTPUT_FILE}")
print("Top 10 leads preview:")
preview_cols = [c for c in ["company_name", "score_global", "cosma_opportunity", "opportunity_capability", "post_url"] if c in final_df.columns]
print(final_df[preview_cols].head(10))
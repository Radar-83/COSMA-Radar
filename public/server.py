from __future__ import annotations

import json
import os
import sys
import threading
import subprocess
from pathlib import Path
from subprocess import Popen, TimeoutExpired
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent      
DATA_FILE = BASE_DIR / "Scored_Enriched_clean.json"


KEYWORDS_FILE = BASE_DIR / "keywords.txt"
KEYWORDS_LOCK = threading.Lock()


def _read_keywords() -> list[str]:
    """Return keywords from keywords.txt (skip blanks and # comments)."""
    if not KEYWORDS_FILE.exists():
        return []
    with KEYWORDS_FILE.open("r", encoding="utf-8") as f:
        result: list[str] = []
        for raw in f:
            s = raw.strip()
            if s and not s.startswith("#"):
                result.append(s)
        return result


def _write_keywords(kws: list[str]) -> None:
    """Write keywords, one per line, preserving order."""
    with KEYWORDS_FILE.open("w", encoding="utf-8") as f:
        for k in kws:
            f.write(k + "\n")


class KeywordPayload(BaseModel):
    keyword: str



app = FastAPI(title="Cosma API", version="1.1.0")

# Autoriser le front en dev (CRA sur 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUN_PROC: Optional[Popen] = None
PROC_LOCK = threading.Lock()


def find_executable() -> Path:
    """
    Trouve le fichier '06_Executable' dans BASE_DIR.
    Priorité au .py, puis .exe, puis fichier sans extension.
    """
    candidates = [
        BASE_DIR / "06_Executable.py",
        BASE_DIR / "06_Executable.exe",
        BASE_DIR / "06_Executable",
    ]
    for p in candidates:
        if p.exists():
            return p

    for p in BASE_DIR.glob("06_Executable*"):
        if p.is_file():
            return p
    raise HTTPException(status_code=404, detail="06_Executable introuvable dans 'public/'")


def start_job() -> dict:
    """Lance 06_Executable en tâche de fond et mémorise le Popen."""
    global RUN_PROC
    with PROC_LOCK:
        if RUN_PROC and RUN_PROC.poll() is None:
            raise HTTPException(status_code=409, detail="Un job est déjà en cours")

        exe = find_executable()

        # Sous Windows : créer un nouveau process group pour pouvoir tuer tout l'arbre.
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

        if exe.suffix.lower() == ".py":
            cmd = [sys.executable, str(exe.name)]
        else:
            cmd = [str(exe.name)]

        # cwd=BASE_DIR pour que le script s'exécute au bon endroit
        RUN_PROC = Popen(cmd, cwd=str(BASE_DIR), creationflags=creation_flags)
        return {"pid": RUN_PROC.pid}


def stop_job() -> dict:
    """Arrête le process si il est en cours."""
    global RUN_PROC
    with PROC_LOCK:
        if not RUN_PROC or RUN_PROC.poll() is not None:
            return {"stopped": False, "reason": "aucun job en cours"}

        pid = RUN_PROC.pid
        try:
            if os.name == "nt":
                # Tue le process ET ses enfants
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                RUN_PROC.terminate()
                try:
                    RUN_PROC.wait(timeout=5)
                except TimeoutExpired:
                    RUN_PROC.kill()
            return {"stopped": True, "pid": pid}
        finally:
            RUN_PROC = None


def job_status() -> dict:
    running = RUN_PROC is not None and RUN_PROC.poll() is None
    return {"running": running, "pid": RUN_PROC.pid if running else None}


@app.get("/api/ping")
def ping():
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    return job_status()


@app.post("/api/run")
def api_run():
    return start_job()


@app.post("/api/stop")
def api_stop():
    return stop_job()

@app.get("/api/data")
def get_data():
    """
    Renvoie le contenu JSON de Scored_Enriched_clean.json.
    """
    if not DATA_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Fichier de données introuvable : {DATA_FILE.name}",
        )
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture JSON : {e}")
    return data


@app.get("/api/keywords")
def get_keywords():
    """
    Renvoie la liste des mots-clés. Retourne 200 [] s'il n'y en a aucun.
    """
    return {"keywords": _read_keywords()}


@app.post("/api/keywords")
def add_keyword(payload: KeywordPayload):
    """
    Ajoute un mot-clé (si non vide et non dupliqué).
    Corps JSON attendu: {"keyword": "texte"}
    """
    kw = (payload.keyword or "").strip()
    if not kw:
        raise HTTPException(status_code=400, detail="keyword manquant ou vide")

    with KEYWORDS_LOCK:
        kws = _read_keywords()
        if kw not in kws:
            kws.append(kw)
            _write_keywords(kws)
    return {"keywords": kws}


@app.delete("/api/keywords")
def delete_keyword(
    
    payload: Optional[KeywordPayload] = Body(None),
    keyword: Optional[str] = Query(None),
):
    kw = (payload.keyword if payload else keyword) or ""
    kw = kw.strip()
    if not kw:
        raise HTTPException(status_code=400, detail="keyword manquant")

    with KEYWORDS_LOCK:
        kws = [k for k in _read_keywords() if k != kw]
        _write_keywords(kws)
    return {"keywords": kws}



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app", 
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

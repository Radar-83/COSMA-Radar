@echo off
setlocal EnableExtensions

REM === Absolute project path (adjust only if you move the project) ===
set "PROJECT_ROOT=C:\Users\yannd_qhxuxne\Documents\COSMA_Radar"

REM === Start backend (Uvicorn) in a new window ===
start "BACKEND" cmd /k ^
  cd /d "%PROJECT_ROOT%" ^& ^
  py -m uvicorn public.server:app --host 127.0.0.1 --port 8000

REM === Start frontend (npm start) in a new window ===
start "FRONTEND" cmd /k ^
  cd /d "%PROJECT_ROOT%" ^& ^
  npm start

REM Optional: open browser to the frontend (change port if needed)
REM start "" "http://127.0.0.1:3000"

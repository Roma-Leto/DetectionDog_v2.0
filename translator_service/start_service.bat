@echo off
REM ============================================================
REM DetectionDog Translator Service - launcher for NSSM
REM This script is called by NSSM service at Windows startup.
REM ============================================================

cd /d "E:\FlaskProjects\detectiondog\translator_service"

"E:\FlaskProjects\detectiondog\translator_service\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 5002 --log-level info
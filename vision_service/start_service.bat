@echo off
cd /d "E:\FlaskProjects\detectiondog\vision_service"
"E:\FlaskProjects\detectiondog\vision_service\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 5001 --log-level info
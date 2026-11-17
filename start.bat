@echo off
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env >nul
  echo Created .env - open it, fill in your Discord + DB details, then run start.bat again.
  notepad .env
  exit /b
)
python -c "import flask, mysql.connector, requests" 2>nul || python -m pip install -r requirements.txt
echo TOP-X running at http://localhost:5000
python app.py
pause

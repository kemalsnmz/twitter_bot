@echo off
cd /d C:\Users\kemal\Downloads\twitter_bot\twitter_bot

echo [1/2] FastAPI backend baslatiliyor (port 8000)...
start "Twitter Bot API" cmd /k "cd /d C:\Users\kemal\Downloads\twitter_bot\twitter_bot && uvicorn web.api:app --reload --port 8000"

timeout /t 2 /nobreak >nul

echo [2/2] React frontend baslatiliyor (port 5173)...
start "Twitter Bot UI" cmd /k "cd /d C:\Users\kemal\Downloads\twitter_bot\twitter_bot\frontend && npm run dev"

echo.
echo Panel aciliyor: http://localhost:5173
timeout /t 3 /nobreak >nul
start http://localhost:5173

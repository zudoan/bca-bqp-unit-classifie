@echo off
echo 🚀 Starting BCA-BQP Application Stack...
echo.

REM Build and start all services
docker compose up -d --build

echo.
echo ✅ Services starting...
echo.
echo 📊 Backend API:  http://localhost:7860
echo    - Health:     http://localhost:7860/health
echo    - API Docs:   http://localhost:7860/docs
echo.
echo 🎨 Frontend:     http://localhost:3000
echo.
echo 📝 View logs:    docker compose logs -f
echo 🛑 Stop:         docker compose down
echo.

pause

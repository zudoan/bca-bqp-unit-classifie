#!/bin/bash
set -e

echo "==================================================================="
echo "   BCA-BQP Organization Registry - Khoi dong he thong 1-Click"
echo "==================================================================="
echo ""

# Kiem tra file cau hinh .env
if [ ! -f .env ]; then
    echo "[CAU HINH LAN DAU] Chua tim thay file .env"
    echo ""
    echo "He thong su dung Google Gemini 2.5 Flash de OCR tai lieu PDF scan."
    echo "Ban co the lay API key mien phi tai: https://aistudio.google.com/app/apikey"
    echo ""
    read -r -p ">> Nhap Gemini API Key cua ban (Nhan Enter de bo qua neu chua co): " USER_KEY
    
    if [ -n "$USER_KEY" ]; then
        cat <<EOF > .env
# Google Gemini API Key for OCR on scanned PDFs
GEMINI_API_KEY=${USER_KEY}
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT=300
GEMINI_MAX_OUTPUT_TOKENS=32768
EOF
        echo ""
        echo "[DA LUU] Da luu Gemini API Key vao file .env thanh cong!"
    else
        if [ -f .env.example ]; then
            cp .env.example .env
        else
            cat <<EOF > .env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT=300
GEMINI_MAX_OUTPUT_TOKENS=32768
EOF
        fi
        echo ""
        echo "[THONG BAO] Da tao file .env mac dinh. Ban co the them key sau vao file .env."
    fi
    echo "Cac lan khoi dong tiep theo se tu dong chay ma khong can nhap lai!"
    echo "==================================================================="
    echo ""
fi

echo "🚀 Dang khoi dong cac dich vu BCA-BQP (Docker Compose)..."
echo ""

# Build and start all services
docker compose up -d --build

echo ""
echo "✅ He thong dang chay tai:"
echo ""
echo "🎨 Giao dien Web (Frontend): http://localhost:3000"
echo "📊 Backend API:             http://localhost:7860"
echo "   - Health check:           http://localhost:7860/health"
echo "   - API Docs (Swagger):     http://localhost:7860/docs"
echo ""
echo "📝 Xem log he thong:        docker compose logs -f"
echo "🛑 Dung he thong:           docker compose down"
echo ""

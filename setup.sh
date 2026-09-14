#!/usr/bin/env bash
# ============================================================
# ChitralSafe — Mac/Linux Auto Setup Script
# Run from project root:
#   chmod +x setup.sh
#   ./setup.sh
# ============================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  ChitralSafe — Auto Setup Script (Mac/Linux)${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# ── Step 1: Check Python ──────────────────────────────────────
echo -e "${YELLOW}[1/6] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version)
    echo -e "  ${GREEN}✓ $PY_VER${NC}"
    PYTHON=python3
elif command -v python &>/dev/null; then
    PY_VER=$(python --version)
    echo -e "  ${GREEN}✓ $PY_VER${NC}"
    PYTHON=python
else
    echo -e "  ${RED}✗ Python not found. Install from https://python.org/downloads${NC}"
    exit 1
fi

# ── Step 2: Create virtual environment ───────────────────────
echo -e "${YELLOW}[2/6] Setting up Python virtual environment...${NC}"
cd backend

if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "  ${GREEN}✓ Virtual environment already exists${NC}"
fi

source .venv/bin/activate

# ── Step 3: Install dependencies ─────────────────────────────
echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"
echo -e "  ${GRAY}(This may take 2-5 minutes on first run)${NC}"
pip install -r requirements.txt --quiet
echo -e "  ${GREEN}✓ All dependencies installed${NC}"

# ── Step 4: Setup .env ────────────────────────────────────────
echo -e "${YELLOW}[4/6] Configuring environment...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}✓ .env created from template${NC}"
    echo -e "  ${CYAN}ℹ  Edit backend/.env to customize settings${NC}"
else
    echo -e "  ${GREEN}✓ .env already exists (keeping existing config)${NC}"
fi

cd ..

# ── Step 5: Check Flutter ─────────────────────────────────────
echo -e "${YELLOW}[5/6] Checking Flutter...${NC}"
if command -v flutter &>/dev/null; then
    FLUTTER_VER=$(flutter --version 2>&1 | head -1)
    echo -e "  ${GREEN}✓ $FLUTTER_VER${NC}"

    echo -e "  ${GRAY}Installing Flutter dependencies...${NC}"
    cd app
    flutter pub get --suppress-analytics > /dev/null 2>&1
    cd ..
    echo -e "  ${GREEN}✓ Flutter dependencies ready${NC}"
else
    echo -e "  ${YELLOW}⚠  Flutter not found. Install from https://docs.flutter.dev/get-started/install${NC}"
    echo -e "  ${CYAN}ℹ  Backend will still work without Flutter${NC}"
fi

# ── Step 6: Done ──────────────────────────────────────────────
echo -e "${YELLOW}[6/6] Setup complete!${NC}"
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  ✅ Setup Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Next steps:"
echo ""
echo -e "  ${CYAN}1. Start backend:${NC}"
echo -e "     cd backend"
echo -e "     source .venv/bin/activate"
echo -e "     python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload"
echo ""
echo -e "  ${CYAN}2. Start Flutter app (new terminal):${NC}"
echo -e "     cd app"
echo -e "     flutter run -d chrome --web-port 8080"
echo ""
echo -e "  ${CYAN}3. Open in browser:${NC}"
echo -e "     App  → http://localhost:8080"
echo -e "     API  → http://127.0.0.1:8002/docs"
echo ""
echo -e "  ${CYAN}4. (Optional) Enable AI chat:${NC}"
echo -e "     Install Ollama: https://ollama.com"
echo -e "     Run: ollama pull llama3"
echo -e "     Set LLM_PROVIDER=ollama in backend/.env"
echo ""
echo -e "  ${GRAY}See SETUP.md for detailed instructions and troubleshooting.${NC}"
echo ""

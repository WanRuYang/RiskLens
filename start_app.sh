#!/bin/bash

# start_app.sh: Unified launch script for Gemma 4 Good v11.0

# 1. Colors for visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Starting gemma4good v11.0 (Agentic Forensic Flow) ===${NC}"

# 2. Check for local safety API
echo -e "${BLUE}Checking local safety API...${NC}"
curl -s http://127.0.0.1:8010/health > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${GREEN}API not detected. Please ensure your database API is running on port 8010.${NC}"
    echo "Hint: cd ../database_project && python3 -m uvicorn api:app --port 8010"
    exit 1
fi

# 3. Check for LoRA adapters
if [ -d "./adapters" ]; then
    echo -e "${GREEN}Found LoRA adapters. mlx_engine will auto-load them.${NC}"
else
    echo -e "${BLUE}Running in Base Model mode (No adapters found).${NC}"
fi

# 4. Launch Gradio UI
echo -e "${GREEN}Launching Chatbot Interface...${NC}"
python3 app.py

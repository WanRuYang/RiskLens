#!/bin/bash

# start_app.sh: Unified launch script for Gemma 4 Good v11.0

# 1. Colors for visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Starting gemma4good v26.0 (Forensic Peak Peak) ===${NC}"

# 2. Check for local safety API
echo -e "${BLUE}Checking local safety API...${NC}"
curl -s http://127.0.0.1:8010/health > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${GREEN}API not detected. Native retrieval (v8.0+) will proceed without it, but local API is recommended for full forensics.${NC}"
fi

# 3. Check for Semantic Knowledge Store (v21.0)
if [ ! -f "./data/semantic_index.pkl" ]; then
    echo -e "${BLUE}Semantic Index missing. Rebuilding from 9,133 samples...${NC}"
    uv run python -u semantic_store.py
fi

# 4. Check for LoRA adapters
if [ -d "./adapters" ]; then
    echo -e "${GREEN}Found LoRA adapters. mlx_engine will auto-load them.${NC}"
fi

# 5. Launch Chatbot (v26.0)
echo -e "${GREEN}Launching Forensic Peak Chatbot...${NC}"
uv run python -u app.py

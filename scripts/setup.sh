#!/bin/bash

# 確保腳本在發生錯誤時停止執行
set -e

echo "🚀 偵測到路徑：$PWD"
echo "📦 正在檢查 pyproject.toml..."

# 檢查當前目錄是否有 pyproject.toml
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 錯誤：找不到 pyproject.toml。請確保此腳本與 pyproject.toml 放在同一個資料夾。"
    exit 1
fi

echo "🌟 正在使用 uv 初始化環境..."

# 建立虛擬環境 (.venv)
uv venv

# 啟動虛擬環境 (針對 macOS/Linux)
source .venv/bin/activate

# 同步安裝 pyproject.toml 裡定義的套件
echo "⏳ 正在同步套件 (這可能需要一點時間)..."
uv sync

echo "---"
echo "✅ 環境架設完成！"
echo "👉 請執行以下指令來啟動環境："
echo "   source .venv/bin/activate"
echo ""
echo "🚀 然後執行專案："
echo "   python app.py"

import os
import torch
import kagglehub
import gradio as gr
from pathlib import Path
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

# ==========================================
# 1. 身分驗證設定 (從你的隱藏檔讀取)
# ==========================================
def load_kaggle_credentials():
    kaggle_dir = Path.home() / ".kaggle"
    user_file = kaggle_dir / "user_name"
    token_file = kaggle_dir / "access_token"

    if not user_file.exists() or not token_file.exists():
        print(f"❌ 找不到憑證檔案於 {kaggle_dir}")
        print("請確認檔案存在且內容正確。")
        return False

    # 讀取並設定環境變數，kagglehub 會自動使用這些變數
    os.environ["KAGGLE_USERNAME"] = user_file.read_text().strip()
    os.environ["KAGGLE_KEY"] = token_file.read_text().strip()
    
    print(f"✅ 已載入 Kaggle 憑證: {os.environ['KAGGLE_USERNAME']}")
    return True

# ==========================================
# 2. 模型下載與載入
# ==========================================
# 根據你的截圖，這裡選擇最適合手機測試的 e4b-it 版本
# 如果要測 26B，請改為 "gemma-4-26b-a4b-it"
VARIATION = "gemma-4-e4b-it"
MODEL_HANDLE = f"google/gemma-4/transformers/{VARIATION}"

# 初始化變數避免 NameError
model = None
processor = None

if load_kaggle_credentials():
    try:
        print(f"⏳ 正在從 Kaggle 下載/檢查模型: {MODEL_HANDLE}")
        # 下載模型並取得本機路徑
        model_path = kagglehub.model_download(MODEL_HANDLE)
        print(f"📍 模型存放路徑: {model_path}")

        print("🚀 正在載入模型至記憶體 (使用 bfloat16)...")
        # 載入處理器與模型
        processor = AutoProcessor.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        print("✨ 模型載入成功！")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        print("💡 提示：如果出現 404，請檢查你的 Kaggle Username 是否為全小寫 ID，並確認網頁上已按過 'Accept Terms'。")
        exit(1)
else:
    exit(1)

# ==========================================
# 3. 推論邏輯
# ==========================================
def process_vision(image, prompt):
    if image is None:
        return "請先上傳圖片。"
    
    if model is None or processor is None:
        return "模型尚未準備就緒。"

    # 建立對話格式
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt if prompt else "請擷取圖片中的所有文字。"}
            ]
        }
    ]
    
    # 處理輸入
    # 先轉為字串 template，再轉為 tensors
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, images=image, return_tensors="pt").to(model.device)
    
    # 生成回應
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=512)
        # 排除輸入部分，只解碼生成的 ID
        generated_ids = output[0][inputs.input_ids.shape[-1]:]
        response = processor.decode(generated_ids, skip_special_tokens=True)
    
    return response

# ==========================================
# 4. Gradio 介面
# ==========================================
with gr.Blocks(title="Gemma 4 Vision Experiment") as demo:
    gr.Markdown("# 📷 Gemma 4 多模態掃描器")
    gr.Markdown(f"目前運行模型: `{VARIATION}`")
    
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(type="pil", label="上傳圖片")
            input_prompt = gr.Textbox(
                label="指令", 
                value="請擷取圖片中的所有文字並格式化輸出。",
                placeholder="例如：這份食物標籤裡有哪些過敏原？"
            )
            btn = gr.Button("開始分析", variant="primary")
        
        with gr.Column():
            output_text = gr.Textbox(label="掃描結果", lines=15)

    btn.click(fn=process_vision, inputs=[input_img, input_prompt], outputs=output_text)

if __name__ == "__main__":
    # 啟動 UI
    demo.launch()

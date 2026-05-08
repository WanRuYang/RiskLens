import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr
import requests

from mlx_engine import (
    run_scribe_agent,
    run_web_scribe_agent,
    run_classifier_agent,
    run_search_agent,
    run_editor_agent,
    run_feedback_agent,
    verify_category_vlm
)

# Configuration
API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
PROJECT_ROOT = Path(__file__).resolve().parent
HISTORY_FILE = PROJECT_ROOT / "data" / "user_queries.jsonl"
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

class SessionState:
    def __init__(self):
        self.user_id = "local_demo_user"
        self.region = "California, USA"
        self.current_state = "INIT"
        self.raw_ocr_text = ""
        self.confirmed_text = ""
        self.proposed_category = {}
        self.confirmed_category = {}
        self.api_result = {}
        self.final_report = ""
        self.image_paths = []
        self.product_link = ""

def save_to_history(state: SessionState):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": state.user_id,
        "region": state.region,
        "product_name": state.confirmed_category.get("product_name", ""),
        "category": state.confirmed_category.get("product_use_category", ""),
        "ocr_text": state.confirmed_text,
        "final_report": state.final_report
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def process_chat(message, history, state: SessionState, user_id_val, region_val, product_link_val, image_files):
    # Initialize session if needed
    if state is None:
        state = SessionState()
    
    # Update global configs from UI components
    state.user_id = user_id_val or state.user_id
    state.region = region_val or state.region
    
    bot_message = ""
    
    # --- State Machine ---
    
    if state.current_state == "INIT":
        # Handle initial upload (Image or Link)
        if product_link_val:
            state.product_link = product_link_val
            bot_message = "I see a product link. Let me fetch the info...\n"
            web_info = run_web_scribe_agent(product_link_val)
            state.raw_ocr_text = web_info
            state.current_state = "AWAITING_TEXT_CONFIRM"
            bot_message += f"\n**Extracted Info:**\n{web_info}\n\nIs this info correct? You can edit it or just say 'yes' to proceed."
        elif image_files:
            state.image_paths = [f.name for f in image_files]
            bot_message = "I've received your images. Running high-performance OCR scan...\n"
            ocr_text = run_scribe_agent(state.image_paths)
            state.raw_ocr_text = ocr_text
            state.current_state = "AWAITING_TEXT_CONFIRM"
            bot_message += f"\n**Extracted Text:**\n{ocr_text}\n\nIs this transcription correct? You can provide corrections or say 'yes' to continue."
        else:
            bot_message = "Please upload 1-3 images of the product or provide a product link above."

    elif state.current_state == "AWAITING_TEXT_CONFIRM":
        # User confirmed or corrected the text
        if message.lower().strip() in ["yes", "y", "correct", "ok"]:
            state.confirmed_text = state.raw_ocr_text
        else:
            state.confirmed_text = message
        
        bot_message = "Text confirmed. Now aligning product category...\n"
        proposed = run_classifier_agent(state.confirmed_text)
        state.proposed_category = proposed
        state.current_state = "AWAITING_CAT_CONFIRM"
        
        # v10.0: Autonomous Self-Verification
        vlm_check = "N/A"
        if state.image_paths:
            print("Running system self-verification...")
            vlm_verified = verify_category_vlm(proposed.get('product_use_category', 'Other'), state.image_paths)
            vlm_check = "PASSED ✅" if vlm_verified else "CAUTION ⚠️ (Visual drift detected)"
        
        bot_message += f"\nI categorized this as: **{proposed.get('product_use_category', 'Other')}**"
        bot_message += f"\nSystem Self-Verification: **{vlm_check}**"
        bot_message += f"\nPriority: **{proposed.get('information_priority', 'material_first')}**"
        bot_message += f"\nReasoning: *{proposed.get('reasoning', 'No reasoning provided')}*"
        bot_message += "\n\nDoes this look correct? Say 'yes' or specify the correct category."

    elif state.current_state == "AWAITING_CAT_CONFIRM":
        # User confirmed or corrected the category
        if message.lower().strip() in ["yes", "y", "correct", "ok"]:
            state.confirmed_category = state.proposed_category
        else:
            # Simple override if user types a new category
            state.confirmed_category = state.proposed_category.copy()
            state.confirmed_category["product_use_category"] = message
        
        bot_message = "Category aligned. Searching safety database for matches...\n"
        
        # Assemble search context
        search_data = {
            "user_id": state.user_id,
            "product_name": state.confirmed_category.get("product_name", "Unknown"),
            "ingredient_text": state.confirmed_category.get("ingredient_text", ""),
            "warning_text": state.confirmed_category.get("warning_text", ""),
            "region": state.region
        }
        
        # Call Search Agent
        api_result = run_search_agent(search_data)
        state.api_result = api_result
        
        # Final formatting
        bot_message += "Synthesizing final report...\n"
        final_report = run_editor_agent(state.confirmed_category, api_result)
        state.final_report = final_report
        state.current_state = "FEEDBACK"
        
        # Save to user history
        save_to_history(state)
        
        bot_message = f"### Final Safety Analysis\n\n{final_report}\n\n--- \nAnalysis saved to history. Do you have any follow-up questions about these findings?"

    elif state.current_state == "FEEDBACK":
        # v11.0: Multimodal Feedback - check for new images first
        if image_files and len([f.name for f in image_files]) > len(state.image_paths):
            new_images = [f.name for f in image_files]
            added_images = [p for p in new_images if p not in state.image_paths]
            state.image_paths = new_images
            bot_message = f"I've received {len(added_images)} new images. Let me re-analyze the specific details...\n"
            
            # Re-run OCR on just the new images
            new_ocr = run_scribe_agent(added_images)
            state.confirmed_text += f"\n\n[SUPPLEMENTAL OCR]:\n{new_ocr}"
            
            # Suggest a re-search
            bot_message += f"\n**Supplemental Text:**\n{new_ocr}\n\nWould you like me to rerun the safety search with this new information?"
        else:
            # Standard conversational feedback with potential actions
            feedback_result = run_feedback_agent(message, {"api_result": state.api_result, "report": state.final_report})
            bot_message = feedback_result.get("response", "I'm sorry, I couldn't process that request.")
            
            action = feedback_result.get("action", "NONE")
        if action == "RERUN_SEARCH":
            payload = feedback_result.get("action_payload", {})
            state.region = payload.get("region", state.region)
            # Trigger a silent re-search
            bot_message += "\n\n(Triggering re-search with updated parameters...)"
            
            search_data = {
                "user_id": state.user_id,
                "product_name": state.confirmed_category.get("product_name", "Unknown"),
                "ingredient_text": payload.get("ingredients", state.confirmed_category.get("ingredient_text", "")),
                "warning_text": state.confirmed_category.get("warning_text", ""),
                "region": state.region
            }
            api_result = run_search_agent(search_data)
            state.api_result = api_result
            final_report = run_editor_agent(state.confirmed_category, api_result)
            state.final_report = final_report
            bot_message += f"\n\n### Updated Safety Analysis\n\n{final_report}"
            save_to_history(state)
            
        elif action == "UPDATE_CATEGORY":
            payload = feedback_result.get("action_payload", {})
            new_cat = payload.get("category", "Other")
            bot_message += f"\n\n(Switching category to: {new_cat} and re-searching...)"
            state.confirmed_category["product_use_category"] = new_cat
            
            search_data = {
                "user_id": state.user_id,
                "product_name": state.confirmed_category.get("product_name", "Unknown"),
                "ingredient_text": state.confirmed_category.get("ingredient_text", ""),
                "warning_text": state.confirmed_category.get("warning_text", ""),
                "region": state.region
            }
            api_result = run_search_agent(search_data)
            state.api_result = api_result
            final_report = run_editor_agent(state.confirmed_category, api_result)
            state.final_report = final_report
            bot_message += f"\n\n### Updated Safety Analysis\n\n{final_report}"
            save_to_history(state)

    return bot_message, state

# Custom Chat Function to handle Gradio interface
def chat_wrapper(message, history, state, user_id, region, link, files):
    bot_msg, updated_state = process_chat(message, history, state, user_id, region, link, files)
    history.append((message, bot_msg))
    return history, updated_state, "" # Reset input box

with gr.Blocks(theme=gr.themes.Soft(), title="gemma4good v4.0") as demo:
    session_state = gr.State()
    
    gr.Markdown("# gemma4good v4.0 (Agentic Flow)")
    gr.Markdown("Interactive consumer safety assistant with Human-in-the-Loop verification.")

    with gr.Row():
        with gr.Column(scale=1):
            user_id = gr.Textbox(label="User ID", value="local_demo_user")
            region = gr.Textbox(label="Region", value="California, USA")
            product_link = gr.Textbox(label="Optional Product Link", placeholder="https://...")
            input_files = gr.File(file_count="multiple", label="Upload 1-3 Labels")
            reset_btn = gr.Button("Start New Analysis", variant="secondary")
            
        with gr.Column(scale=3):
            with gr.Row():
                state_indicator = gr.Label(value="Status: Ready", label="Agent Activity", num_top_classes=0)
            chatbot = gr.Chatbot(height=500, show_label=False)
            msg = gr.Textbox(label="Your message (Confirmation or Question)", placeholder="Type 'yes' to proceed or ask a question...")
            
    # Handle message submission
    msg.submit(
        fn=chat_wrapper,
        inputs=[msg, chatbot, session_state, user_id, region, product_link, input_files],
        outputs=[chatbot, session_state, msg]
    ).then(
        fn=lambda state: f"Status: {state.current_state}" if state else "Status: Ready",
        inputs=[session_state],
        outputs=[state_indicator]
    )

    # Initial prompt when starting
    def start_over():
        return [], SessionState(), "", "", "Status: Ready"

    reset_btn.click(
        fn=start_over,
        outputs=[chatbot, session_state, msg, product_link, state_indicator]
    )

    gr.HTML(
        """
        <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; font-size: 0.9em;">
            <b>Agentic Flow:</b> Scribe (OCR/Link) -> Classifier (Alignment) -> Search (DB) -> Editor (Report) -> Consultant (Feedback)
        </div>
        """
    )

if __name__ == "__main__":
    # Ensure database API is checked or mentioned
    demo.launch()

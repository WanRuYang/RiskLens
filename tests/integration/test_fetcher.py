import sys
import json
from browser_fetcher import BrowserFetcher

def test_url(url):
    print(f"Testing URL: {url}")
    print("-" * 50)
    try:
        from database_manager import ProductDatabase
        db = ProductDatabase()
        
        # Check if already in DB
        existing = db.get_product(url)
        if existing:
            print("DB STATUS: Found in local cache (Response will be INSTANT)")
        else:
            print("DB STATUS: Not in cache (Launching browser, will take ~20s)")

        from app_shared import preview_url
        data = preview_url(url)
        
        print(json.dumps(data, indent=2))
        print("-" * 50)
        
        url_ctx = data.get("url_context", {})
        if not url_ctx.get("product_text") and not url_ctx.get("ingredients_text"):
            print("Fetch status: PARTIAL (Blocked or Selectors Failed)")
        else:
            print("Fetch status: SUCCESS")
            
    except Exception as e:
        print(f"Fetch FAILED: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_fetcher.py <url>")
        sys.exit(1)
    
    test_url(sys.argv[1])

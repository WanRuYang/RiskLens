import sys
def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

log("STAGE 1: IMPORTS")
import csv
import json
import os
import random
import time
import re
from pathlib import Path

log("STAGE 2: SELENIUM IMPORTS")
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

log("STAGE 3: CONSTANTS")
PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "benchmark_real_image_manifest_v2.csv"
BENCHMARK_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases_v2.json"

STORES = {
    "Walmart": "https://www.walmart.com/search?q=",
    "Target": "https://www.target.com/s?searchTerm=",
    "Sayweee": "https://www.sayweee.com/en/search?keyword=",
    "99 Ranch": "https://www.99ranch.com/search?q=",
    "Amazon": "https://www.amazon.com/s?k=",
    "Safeway": "https://www.safeway.com/shop/search-results.html?q=",
    "Costco": "https://www.costco.com/CatalogSearch?keyword=",
    "H-Mart": "https://www.hmart.com/search/result/?q="
}

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    log("Starting browser...")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    return driver

def scrape_literal_label(driver, store, title):
    search_url = STORES.get(store, STORES["Amazon"]) + title.replace(" ", "+")
    log(f"  Searching {store} for: {title[:50]}...")
    
    try:
        driver.get(search_url)
        time.sleep(random.uniform(2, 4))
        
        # 1. Click first product link
        link_selectors = [
            "a[href*='/ip/']", "a[href*='/p/']", "a[href*='/dp/']", 
            "a[href*='/product/']", "a.product-item-link", "a.product-title-link",
            "h2 a", "h3 a"
        ]
        
        product_link = None
        for selector in link_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    href = el.get_attribute("href")
                    if href and ("amazon.com" in href or "walmart.com" in href or "target.com" in href or "99ranch.com" in href or "sayweee.com" in href):
                        if "/slredirect/" not in href: 
                            product_link = el
                            break
                if product_link: break
            except: continue
            
        if product_link:
            target_url = product_link.get_attribute("href")
            log(f"    Navigating to: {target_url[:60]}...")
            driver.get(target_url)
            time.sleep(random.uniform(3, 5))
            
            # 2. Extract Ingredients / Warnings text surgically
            ingredients = ""
            warnings = ""
            
            # Try specific containers first
            if "amazon.com" in target_url:
                try:
                    important_info = driver.find_elements(By.ID, "important-information")
                    if important_info:
                        txt = important_info[0].text
                        if "Ingredients" in txt:
                            chunk = txt.split("Ingredients")[-1]
                            ingredients = re.split(r'\nDirections|\nLegal Disclaimer|\nSafety|\nAbout this item', chunk, flags=re.I)[0].strip()
                except: pass

            if not ingredients:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                match = re.search(r'Ingredients[:\s]+(.*?)(?:\n\n|\n[A-Z][a-z]+[:\s]|\nDirections|\nLegal Disclaimer)', body_text, re.I | re.S)
                if match:
                    ingredients = match.group(1).strip()
            
            warn_match = re.search(r'(?:Warnings|Safety Information|Proposition 65|Caution|Alert)[:\s]+(.*?)(?:\n\n|\n[A-Z][a-z]+[:\s])', body_text if 'body_text' in locals() else driver.find_element(By.TAG_NAME, "body").text, re.I | re.S)
            warnings = warn_match.group(1).strip() if warn_match else ""
            
            return {
                "web_ingredients": ingredients,
                "web_warnings": warnings,
                "url": target_url
            }
            
    except Exception as e:
        log(f"    Scrape error: {type(e).__name__}")
        
    return {"web_ingredients": "", "web_warnings": "", "url": ""}

def main():
    log("MAIN START")
    if not MANIFEST_PATH.exists() or not BENCHMARK_JSON.exists():
        log("Required files missing.")
        return
        
    driver = setup_driver()
    manifest = []
    with MANIFEST_PATH.open(newline="", encoding="utf-8-sig") as f:
        manifest = list(csv.DictReader(f))
        
    cases = json.loads(BENCHMARK_JSON.read_text())
    cases_by_id = {c["id"]: c for c in cases}
    
    log(f"Starting Ground Truth Labeler for {len(manifest)} cases...")
    count_success = 0
    batch_size = 5
    try:
        for idx, row in enumerate(manifest):
            case_id = row["case_id"]
            if case_id not in cases_by_id: continue

            # v19.1: Smarter skip logic - if it has noise, re-scrape
            existing_truth = cases_by_id[case_id].get("web_ground_truth", {})
            existing_ingred = existing_truth.get("web_ingredients", "")

            should_scrape = False
            if not existing_ingred:
                should_scrape = True
            else:
                noise_markers = ["Top highlights", "Item details", "Frequently bought together", "Consider a similar item"]
                if any(existing_ingred.startswith(marker) for marker in noise_markers):
                    should_scrape = True
                    log(f"  [RE-SCRAPE] Case {case_id} looks noisy.")

            if not should_scrape:
                continue

            # Re-initialize driver every batch to prevent hangs
            if idx % batch_size == 0:
                if 'driver' in locals() and driver:
                    try: driver.quit()
                    except: pass
                driver = setup_driver()

            # Add a small delay between products to avoid retailer blocks
            time.sleep(random.uniform(5, 10))

            try:
                truth = scrape_literal_label(driver, row["source_marketplace"], row["product_title"])
            except Exception as e:
                log(f"  [CRITICAL] Browser error on {case_id}: {e}")
                try: driver.quit()
                except: pass
                driver = setup_driver()
                continue
            
            if truth["web_ingredients"] or truth["web_warnings"]:
                cases_by_id[case_id]["expected_strings"] = [row["product_title"]]
                if truth["web_ingredients"]:
                    cases_by_id[case_id]["expected_strings"].append(truth["web_ingredients"][:300])
                if truth["web_warnings"]:
                    cases_by_id[case_id]["expected_strings"].append(truth["web_warnings"][:300])
                
                cases_by_id[case_id]["web_ground_truth"] = truth
                log(f"  [SUCCESS] Labeled {case_id}")
                count_success += 1
            else:
                log(f"  [SKIPPED] No literal text found for {case_id}")
                
            # Save progress every iteration
            BENCHMARK_JSON.write_text(json.dumps(list(cases_by_id.values()), indent=2, ensure_ascii=False))
            log(f"  Progress: {idx+1}/{len(manifest)} processed. Run Successes: {count_success}")
                
    finally:
        driver.quit()
        
    log(f"Done. Final Success count: {count_success}")

if __name__ == "__main__":
    main()

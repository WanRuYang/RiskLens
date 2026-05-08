import csv
import json
import os
import random
import time
import sys
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_ROOT = Path(__file__).resolve().parent
IMAGES_ROOT = PROJECT_ROOT / "benchmark_images_real_extended"
AMAZON_100 = PROJECT_ROOT / "benchmark_amazon_100.csv"
MANIFEST_PATH = PROJECT_ROOT / "benchmark_product_image_manifest.csv"
OUTPUT_MANIFEST = PROJECT_ROOT / "benchmark_real_image_manifest_v2.csv"
OUTPUT_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases_v2.json"

# --- Target 100 New Products ---
FOOD_SEEDS = [
    "Shin Ramyun Gourmet Spicy", "Calbee Shrimp Chips", "Otsuka Pocari Sweat",
    "Matcha Green Tea Powder", "Organic Extra Virgin Olive Oil", "Peanut Butter Creamy", 
    "Sriracha Hot Chili Sauce", "Frozen Gyoza Dumplings", "Golden Curry Medium Hot",
    "Jasmine Rice 20lb", "Seaweed Snacks Roasted", "Gummy Bear Multivitamins",
    "Honey Nut Cheerios", "Coca-Cola Classic", "Starbucks Whole Bean Coffee",
    "Buldak Carbonara Ramen", "Kirkland Signature Organic Quinoa", "La Croix Lime"
]
OTHER_SEEDS = [
    "Tide Pods Free & Gentle", "Windex Original Glass Cleaner", "LEGO Classic Brick Box",
    "Huggies Little Snugglers", "Clorox Disinfecting Wipes", "Method All-Purpose Cleaner", 
    "Silicon Spatula Set", "Ceramic Dinnerware Set", "USB-C Charging Cable", 
    "Neutrogena Hydro Boost", "Bounty Paper Towels", "Fisher-Price Baby Teether"
]

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def download_image(url, save_path):
    try:
        if not url or not url.startswith("http"):
            return False
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        log(f"    Failed download {url[:50]}...: {e}")
    return False

def search_images(driver, query):
    # Try DuckDuckGo first
    engines = [
        (f"https://duckduckgo.com/?q={query.replace(' ', '+')}&iax=images&ia=images", "img.tile--img__img, .tile--img__img, img[src*='external-content']"),
        (f"https://www.bing.com/images/search?q={query.replace(' ', '+')}", "img.mimg, .iusc img")
    ]
    
    for url, selector in engines:
        log(f"  Searching: {query} on {url.split('/')[2]}")
        try:
            driver.get(url)
            wait = WebDriverWait(driver, 15)
            img_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
            
            links = []
            for img in img_elements[:10]:
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if src and src.startswith("http"):
                    links.append(src)
            if links:
                return links
        except Exception as e:
            log(f"    Search failed on {url.split('/')[2]}: {type(e).__name__}")
            time.sleep(1)
            
    return []

def main():
    IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
    driver = setup_driver()
    
    all_targets = []
    
    # 1. Existing Amazon 100
    if AMAZON_100.exists():
        with AMAZON_100.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_targets.append({
                    "case_id": f"amazon_{row['benchmark_id']}",
                    "title": row['amazon_seed_title'],
                    "store": "Amazon",
                    "segment": row['segment'],
                    "category": row['category_group']
                })

    # 2. Existing Product Manifest (Another ~100)
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_targets.append({
                    "case_id": f"manifest_{row['case_id']}",
                    "title": row['product_title'],
                    "store": row['source_marketplace'],
                    "segment": row['segment'],
                    "category": row['category_group']
                })
    
    # 3. Curated 100 new cases
    new_cases = []
    for i in range(100):
        if i % 3 == 0: # 30% Other
            seed = random.choice(OTHER_SEEDS)
            segment, cat = "household", "general"
        else: # 70% Food
            seed = random.choice(FOOD_SEEDS)
            segment, cat = "food", "grocery"
            
        new_cases.append({
            "case_id": f"new_{i:03d}",
            "title": f"{seed} {random.randint(1,500)}",
            "store": random.choice(["Costco", "Walmart", "H-Mart", "Sayweee", "Target"]),
            "segment": segment,
            "category": cat
        })
    all_targets.extend(new_cases)
    
    final_manifest = []
    ocr_cases = []
    
    log(f"Starting Optical Deep Miner for {len(all_targets)} products...")
    
    try:
        for idx, target in enumerate(all_targets):
            case_id = target['case_id']
            title = target['title']
            log(f"[{idx+1}/{len(all_targets)}] Case: {case_id} - {title}")
            
            case_dir = IMAGES_ROOT / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            
            tasks = [
                ("front", f"{title} product packaging"),
                ("ingredients", f"{title} ingredients list nutritional"),
                ("warning", f"{title} warning label caution")
            ]
            
            paths_found = {"front": "", "ingredients": "", "warning": ""}
            
            for suffix, query in tasks:
                save_path = case_dir / f"{suffix}.jpg"
                if save_path.exists():
                    paths_found[suffix] = str(save_path.relative_to(PROJECT_ROOT))
                    continue
                
                links = search_images(driver, query)
                for link in links:
                    if download_image(link, save_path):
                        paths_found[suffix] = str(save_path.relative_to(PROJECT_ROOT))
                        break
                time.sleep(random.uniform(0.5, 1.5))
                
            if any(paths_found.values()):
                row = {
                    "case_id": case_id,
                    "product_title": title,
                    "source_marketplace": target['store'],
                    "segment": target['segment'],
                    "category_group": target['category'],
                    "front_image_path": paths_found["front"],
                    "ingredients_image_path": paths_found["ingredients"],
                    "warning_image_path": paths_found["warning"]
                }
                final_manifest.append(row)
                
                valid_paths = [p for p in paths_found.values() if p]
                ocr_cases.append({
                    "id": case_id,
                    "image_paths": [str((PROJECT_ROOT / p).resolve()) for p in valid_paths],
                    "expected_strings": [title], 
                    "source_marketplace": target['store'],
                    "segment": target['segment'],
                    "category_group": target['category']
                })
            
            if (idx + 1) % 5 == 0:
                log(f"  Progress: {len(final_manifest)} cases with images so far.")
                
    finally:
        driver.quit()
        
    if final_manifest:
        with OUTPUT_MANIFEST.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=final_manifest[0].keys())
            writer.writeheader()
            writer.writerows(final_manifest)
            
        OUTPUT_JSON.write_text(json.dumps(ocr_cases, indent=2, ensure_ascii=False))
        log(f"Success! Created {len(final_manifest)} real-world benchmark cases.")

if __name__ == "__main__":
    main()

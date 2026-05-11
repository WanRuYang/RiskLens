from __future__ import annotations

import time
import random
import re
from typing import Any

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth


class BrowserFetcher:
    """
    A surgical programmatic scraper that directly extracts product data 
    fields (name, ingredients, materials, category, warnings) from retail sites.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    def fetch(self, url: str) -> dict[str, Any]:
        # Clean URL
        if "amazon.com" in url and "/dp/" in url:
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
            if asin_match:
                url = f"https://www.amazon.com/dp/{asin_match.group(1)}"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 1024}
            )
            
            page = context.new_page()
            stealth(page)
            
            try:
                print(f"Direct Fetch: Navigating to {url}...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Check for blocks
                if "amazon.com" in url and ("robot" in page.content().lower() or "continue shopping" in page.content().lower()):
                    print("Amazon bot check detected. Attempting one reload...")
                    page.wait_for_timeout(3000)
                    page.reload(wait_until="domcontentloaded")

                # Scroll to bottom slowly
                for _ in range(3):
                    page.mouse.wheel(0, 800)
                    page.wait_for_timeout(1000)
result = {
    "product_name": "",
    "category": "",
    "ingredients": "",
    "materials": "",
    "claims": "",
    "warnings": "",
    "safety_concerns": "",
    "product_images": [], # New field for discovered label images
    "raw_text_dump": "", 
    "is_blocked": False
}

if "amazon.com" in url:
    self._extract_amazon_surgical(page, result)
elif "target.com" in url:
    self._extract_target_surgical(page, result)
elif "sayweee.com" in url:
    self._extract_sayweee_surgical(page, result)
else:
    self._extract_generic_surgical(page, result)


                # Final Block Check
                if "amazon" in url and "continue shopping" in page.content().lower():
                    result["is_blocked"] = True
                
                # Capture a dump of the whole page text as fallback
                result["raw_text_dump"] = page.locator("body").inner_text()[:8000]

                return result

            except Exception as e:
                print(f"Scraper error: {e}")
                raise e
            finally:
                browser.close()

    def _extract_amazon_surgical(self, page, result):
        try:
            result["product_name"] = page.locator("#productTitle").inner_text().strip()
        except: pass

        try:
            # Breadcrumbs
            result["category"] = " > ".join(page.locator("#wayfinding-breadcrumbs_container a").all_inner_texts())
        except: pass

        try:
            # Ingredients (Surgical)
            important_info = page.locator("#important-information").inner_text()
            if "Ingredients" in important_info:
                result["ingredients"] = important_info.split("Ingredients")[1].split("\n\n")[0].strip()
        except: pass

        try:
            # Claims & Warnings
            result["claims"] = page.locator("#feature-bullets").inner_text().strip()
            result["warnings"] = page.locator("#service-announcements, #safety-warning").inner_text().strip()
        except: pass

    def _extract_target_surgical(self, page, result):
        try:
            result["product_name"] = page.locator("h1[data-test='product-title']").inner_text().strip()
        except: pass

        # Click to reveal ingredients/details
        try:
            # Click the 'Details' or 'Ingredients' accordions directly
            page.evaluate("""() => {
                const targets = ['Ingredients', 'Specifications', 'Details', 'Sustainability'];
                const btns = Array.from(document.querySelectorAll('button'));
                for (const btn of btns) {
                    if (targets.some(t => btn.innerText.includes(t))) {
                        btn.click();
                    }
                }
            }""")
            page.wait_for_timeout(2000)
        except: pass

        try:
            # Category
            result["category"] = " > ".join(page.locator("nav[data-test='breadcrumb'] a").all_inner_texts())
        except: pass

        try:
            # Ingredients
            result["ingredients"] = page.locator("[data-test='label-info-ingredients'], [data-test='drug-facts-ingredients']").inner_text().strip()
        except: pass

        try:
            # Materials & Claims
            result["materials"] = page.locator("[data-test='item-details-specifications']").inner_text().strip()
            result["claims"] = page.locator("[data-test='product-highlights']").inner_text().strip()
        except: pass

    def _extract_sayweee_surgical(self, page, result):
        try:
            result["product_name"] = page.locator("h1[class*='product_title']").inner_text().strip()
        except: pass

        try:
            # SayWeee Category
            result["category"] = " > ".join(page.locator("div[class*='breadcrumb'] a").all_inner_texts())
        except: pass

        # Capture ALL images that might be labels (SayWeee specific)
        try:
            images = page.locator("img").all()
            for img in images:
                src = img.get_attribute("src")
                alt = (img.get_attribute("alt") or "").lower()
                # Look for labels or detail images
                if src and any(k in alt for k in ["ingredient", "label", "nutrition", "fact", "warning"]):
                    if src not in result["product_images"]:
                        result["product_images"].append(src)
            
            # If no alts match, take the first 3 product gallery images
            if not result["product_images"]:
                gallery = page.locator("img[class*='product_image']").all()
                for img in gallery[:3]:
                    src = img.get_attribute("src")
                    if src and src not in result["product_images"]:
                        result["product_images"].append(src)
        except: pass

    def _extract_generic_surgical(self, page, result):
        result["product_name"] = page.title()
        # Generic strategy: look for common headers
        content = page.locator("body").inner_text()
        ing_match = re.search(r"Ingredients[:\n]+(.*?)(?:\n\n|\Z)", content, re.I | re.S)
        if ing_match:
            result["ingredients"] = ing_match.group(1).strip()


if __name__ == "__main__":
    import sys
    import json
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.target.com/p/lavender-38-bergamot-liquid-laundry-detergent-100-fl-oz-everspring-8482/-/A-75663151"
    fetcher = BrowserFetcher(headless=True)
    print(json.dumps(fetcher.fetch(url), indent=2))

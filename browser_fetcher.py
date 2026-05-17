from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from app_shared import (
    canonicalize_product_url,
    clean_html_text,
    extract_ingredient_text_from_readable,
    extract_nutrition_text_from_readable,
    extract_serving_size,
)


class BrowserFetcher:
    """
    Programmatic retailer fetcher for fields that often need rendered DOM state.

    The static HTTP path should remain the first attempt. This browser path is
    for pages where product facts live behind accordions/dropdowns, especially
    Amazon ingredients and Target details.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    def fetch(self, url: str) -> dict[str, Any]:
        url = canonicalize_product_url(url)
        result: dict[str, Any] = {
            "product_name": "",
            "category": "",
            "ingredients": "",
            "nutrition_text": "",
            "serving_size": "",
            "materials": "",
            "claims": "",
            "warnings": "",
            "safety_concerns": "",
            "product_images": [],
            "raw_text_dump": "",
            "is_blocked": False,
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1368, "height": 1400},
                locale="en-US",
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            try:
                print(f"Browser Fetch: Navigating to {url}...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)

                if self._page_looks_blocked(page):
                    print("Retailer block page detected. Attempting one reload...")
                    page.wait_for_timeout(2500)
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1500)

                for _ in range(4):
                    page.mouse.wheel(0, 900)
                    page.wait_for_timeout(600)

                if "amazon." in url:
                    self._extract_amazon_surgical(page, result)
                elif "target.com" in url:
                    self._extract_target_surgical(page, result)
                elif "sayweee.com" in url:
                    self._extract_sayweee_surgical(page, result)
                else:
                    self._extract_generic_surgical(page, result)

                if self._page_looks_blocked(page):
                    result["is_blocked"] = True

                result["raw_text_dump"] = self._safe_body_text(page)[:10000]
                if not result["ingredients"]:
                    result["ingredients"] = extract_ingredient_text_from_readable(result["raw_text_dump"])
                if not result["nutrition_text"]:
                    result["nutrition_text"] = extract_nutrition_text_from_readable(result["raw_text_dump"])
                    result["serving_size"] = extract_serving_size(result["nutrition_text"])
                return result
            except Exception as exc:
                print(f"BrowserFetcher error: {exc}")
                raise
            finally:
                browser.close()

    def _page_looks_blocked(self, page) -> bool:
        content = page.content().lower()
        return any(
            marker in content
            for marker in [
                "robot check",
                "continue shopping",
                "enter the characters you see below",
                "api-services-support@amazon",
                "captcha",
                "access denied",
                "503 - service unavailable",
            ]
        )

    def _safe_body_text(self, page) -> str:
        try:
            return page.locator("body").inner_text(timeout=5000)
        except Exception:
            return clean_html_text(page.content())

    def _click_text_sections(self, page, labels: list[str]) -> None:
        page.evaluate(
            """(labels) => {
                const norm = (value) => (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const wanted = labels.map(norm);
                const candidates = Array.from(document.querySelectorAll(
                    'button, [role="button"], summary, a, h2, h3, div, span'
                ));
                for (const el of candidates) {
                    const text = norm(el.innerText || el.textContent || el.getAttribute('aria-label'));
                    if (!text) continue;
                    if (!wanted.some(label => text === label || text.includes(label))) continue;
                    const expanded = el.getAttribute('aria-expanded');
                    if (expanded === 'true') continue;
                    try { el.scrollIntoView({block: 'center', inline: 'center'}); } catch (_) {}
                    try { el.click(); } catch (_) {}
                }
            }""",
            labels,
        )
        page.wait_for_timeout(1000)

    def _extract_amazon_surgical(self, page, result: dict[str, Any]) -> None:
        try:
            result["product_name"] = page.locator("#productTitle").inner_text(timeout=3000).strip()
        except Exception:
            pass

        try:
            result["category"] = " > ".join(
                text.strip()
                for text in page.locator("#wayfinding-breadcrumbs_container a").all_inner_texts()
                if text.strip()
            )
        except Exception:
            pass

        self._click_text_sections(
            page,
            [
                "Ingredients",
                "Important Information",
                "Nutrition Facts",
                "Product Details",
                "Item Details",
                "About this item",
            ],
        )

        section_texts: list[str] = []
        selectors = [
            "#important-information",
            "#productFactsDesktop_feature_div",
            "#productOverview_feature_div",
            "#nutrition-info",
            "#nic-ingredients-content",
            "#detailBullets_feature_div",
            "[id*='ingredient' i]",
            "[data-feature-name*='ingredient' i]",
            "[cel_widget_id*='ingredient' i]",
        ]
        for selector in selectors:
            try:
                for text in page.locator(selector).all_inner_texts():
                    if text.strip():
                        section_texts.append(text)
            except Exception:
                continue

        body_text = self._safe_body_text(page)
        section_texts.append(body_text)
        for candidate in section_texts:
            ingredients = extract_ingredient_text_from_readable(candidate)
            if ingredients:
                result["ingredients"] = ingredients
                break
        for candidate in section_texts:
            nutrition_text = extract_nutrition_text_from_readable(candidate)
            if nutrition_text:
                result["nutrition_text"] = nutrition_text
                result["serving_size"] = extract_serving_size(nutrition_text)
                break

        try:
            result["claims"] = page.locator("#feature-bullets, #productOverview_feature_div").inner_text(timeout=3000).strip()
        except Exception:
            pass

        try:
            result["warnings"] = page.locator("#service-announcements, #safety-warning").inner_text(timeout=3000).strip()
        except Exception:
            pass

        self._collect_label_images(page, result)

    def _extract_target_surgical(self, page, result: dict[str, Any]) -> None:
        try:
            result["product_name"] = page.locator("h1[data-test='product-title']").inner_text(timeout=3000).strip()
        except Exception:
            pass

        self._click_text_sections(page, ["Ingredients", "Specifications", "Details", "Sustainability", "Label info"])

        try:
            result["category"] = " > ".join(page.locator("nav[data-test='breadcrumb'] a").all_inner_texts())
        except Exception:
            pass

        try:
            result["ingredients"] = page.locator(
                "[data-test='label-info-ingredients'], [data-test='drug-facts-ingredients']"
            ).inner_text(timeout=3000).strip()
        except Exception:
            result["ingredients"] = extract_ingredient_text_from_readable(self._safe_body_text(page))

        try:
            body_text = self._safe_body_text(page)
            result["nutrition_text"] = extract_nutrition_text_from_readable(body_text)
            result["serving_size"] = extract_serving_size(result["nutrition_text"])
        except Exception:
            pass

        try:
            result["materials"] = page.locator("[data-test='item-details-specifications']").inner_text(timeout=3000).strip()
        except Exception:
            pass
        try:
            result["claims"] = page.locator("[data-test='product-highlights']").inner_text(timeout=3000).strip()
        except Exception:
            pass

    def _extract_sayweee_surgical(self, page, result: dict[str, Any]) -> None:
        try:
            result["product_name"] = page.locator("h1[class*='product_title']").inner_text(timeout=3000).strip()
        except Exception:
            pass

        try:
            result["category"] = " > ".join(page.locator("div[class*='breadcrumb'] a").all_inner_texts())
        except Exception:
            pass

        self._collect_label_images(page, result)

    def _extract_generic_surgical(self, page, result: dict[str, Any]) -> None:
        """v26.10: Universal Keyword-Targeted Extraction for general web pages."""
        result["product_name"] = page.title()
        
        # 1. Attempt to find high-signal sections by keyword
        keywords = [
            "Materials", "Fabric", "Composition", "Ingredients", 
            "Specifications", "Details", "Care", "Built with",
            "Content", "What's inside"
        ]
        
        # Click potentially collapsed sections first
        self._click_text_sections(page, keywords)
        
        # Extract snippets around keywords to keep context small and fast
        snippets = page.evaluate(
            """(keywords) => {
                const results = [];
                const norm = (t) => (t || '').toLowerCase();
                const allElements = Array.from(document.querySelectorAll('h1, h2, h3, h4, p, li, dt, dd, span, div'));
                
                keywords.forEach(kw => {
                    const target = kw.toLowerCase();
                    allElements.forEach(el => {
                        const text = el.innerText || '';
                        if (norm(text).includes(target) && text.length < 500) {
                            // Grab current element + next 2 siblings for context
                            let context = text;
                            let sibling = el.nextElementSibling;
                            for(let i=0; i<2 && sibling; i++) {
                                context += "\\n" + (sibling.innerText || '');
                                sibling = sibling.nextElementSibling;
                            }
                            results.push(`--- ${kw} SECTION ---\\n${context}`);
                        }
                    });
                });
                return results.join("\\n\\n");
            }""",
            keywords,
        )
        
        # 2. Extract specific fields from the snippets + body fallback
        body_text = self._safe_body_text(page)
        full_context = f"{snippets}\\n\\n{body_text[:5000]}" # Limit to 5k chars for speed
        
        result["ingredients"] = extract_ingredient_text_from_readable(full_context)
        # For non-food, 'ingredients' often maps to 'materials'
        if not result["ingredients"]:
            # Basic regex fallback for materials if ingredients fail
            mat_match = re.search(r"(?i)(?:materials?|fabric|composition)[:：]\\s*(.{5,500})", full_context)
            if mat_match:
                result["materials"] = mat_match.group(1).strip()
        
        result["nutrition_text"] = extract_nutrition_text_from_readable(body_text)
        result["serving_size"] = extract_serving_size(result["nutrition_text"])
        
        # Capture the product name more cleanly if possible
        try:
            h1 = page.locator("h1").first.inner_text(timeout=2000)
            if h1 and len(h1) < 100:
                result["product_name"] = h1.strip()
        except: pass

    def _collect_label_images(self, page, result: dict[str, Any]) -> None:
        try:
            preferred_urls: list[str] = []
            try:
                dynamic_image_json = page.locator("#landingImage").get_attribute("data-a-dynamic-image")
                if dynamic_image_json:
                    dynamic_images = json.loads(dynamic_image_json)
                    preferred_urls.extend(dynamic_images.keys())
            except Exception:
                pass

            try:
                for img in page.locator("#altImages img, img[data-old-hires]").all():
                    src = img.get_attribute("data-old-hires") or img.get_attribute("src")
                    if src:
                        preferred_urls.append(urljoin(page.url, src))
            except Exception:
                pass

            for src in preferred_urls:
                if self._looks_like_product_image(src) and src not in result["product_images"]:
                    result["product_images"].append(src)

            images = page.locator("img").all()
            for img in images:
                src = img.get_attribute("data-old-hires") or img.get_attribute("src")
                alt = (img.get_attribute("alt") or "").lower()
                if not src:
                    continue
                src = urljoin(page.url, src)
                if not self._looks_like_product_image(src):
                    continue
                if any(token in alt for token in ["ingredient", "label", "nutrition", "fact", "warning", "back"]):
                    if src not in result["product_images"]:
                        result["product_images"].append(src)
            if result["product_images"]:
                return
            for img in images[:24]:
                src = img.get_attribute("data-old-hires") or img.get_attribute("src")
                if src:
                    src = urljoin(page.url, src)
                if src and self._looks_like_product_image(src) and src not in result["product_images"]:
                    result["product_images"].append(src)
                    if len(result["product_images"]) >= 8:
                        break
        except Exception:
            pass

    def _looks_like_product_image(self, src: str) -> bool:
        lowered = src.lower()
        if any(token in lowered for token in ["nav-sprite", "transparent-pixel", "/g/", ".gif"]):
            return False
        return any(token in lowered for token in ["m.media-amazon.com/images/i/", "images-na.ssl-images-amazon.com/images/i/", "target.scene7.com", "product"])


if __name__ == "__main__":
    import sys

    input_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.amazon.com/dp/B0C449R6PX"
    fetcher = BrowserFetcher(headless=True)
    print(json.dumps(fetcher.fetch(input_url), indent=2, ensure_ascii=False))

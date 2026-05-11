from __future__ import annotations

import re
import json
from typing import Any
from duckduckgo_search import DDGS


class SearchFetcher:
    """
    A secondary fetcher that uses DuckDuckGo search to find product information
    when direct retail sites are blocked.
    """

    def __init__(self):
        self.ddgs = DDGS()

    def search_product(self, url: str) -> dict[str, Any]:
        """Search for product info using keywords extracted from the URL."""
        print(f"Direct fetch blocked. Searching for product info via DuckDuckGo...")
        
        # 1. Extract keywords and ID
        product_id = ""
        keywords = ""
        
        # Better Amazon ASIN extraction
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if asin_match:
            product_id = asin_match.group(1)
            # Try to get keywords from slug (Product-Name-Part)
            slug_match = re.search(r"amazon\.com/([^/]+)/dp/", url)
            if slug_match:
                keywords = slug_match.group(1).replace("-", " ")
        
        # Target ID extraction
        target_match = re.search(r"/A-(\d+)", url)
        if target_match:
            product_id = target_match.group(1)
            slug_match = re.search(r"target\.com/p/([^/]+)/-/", url)
            if slug_match:
                keywords = slug_match.group(1).replace("-", " ")

        # 2. Build smart queries with explicit exclusions
        # Adding '-protocol -https -ssl' helps filter out technical junk
        search_query = f"{keywords} {product_id} retail product description -protocol -https -ssl"
        ing_query = f"{keywords} {product_id} ingredients materials ingredients-list safety facts"
        
        result = {
            "product_name": "",
            "product_text": "",
            "ingredients": "",
            "category": "",
            "found": False
        }

        try:
            # First search: General info and name
            print(f"Searching: {search_query}")
            # Use a slightly different method to avoid the generic URL search
            results = self.ddgs.text(search_query, max_results=8)
            
            combined_text = []
            for r in results:
                title = r.get("title", "")
                snippet = r.get("body", "")
                
                # Strict noise filter
                low_title = title.lower()
                if any(x in low_title for x in ["http", "protocol", "tls", "ssl", "server", "dns", "domain"]):
                    continue
                
                combined_text.append(f"{title}: {snippet}")
                
                if not result["product_name"] and len(title) > 10:
                    clean_name = re.sub(r" - Amazon\.com| \| Target|: Amazon\.com", "", title, flags=re.I).strip()
                    result["product_name"] = clean_name

            if combined_text:
                result["product_text"] = "\n\n".join(combined_text)
                result["found"] = True

            # Second search: Ingredients specifically
            print(f"Searching ingredients: {ing_query}")
            ing_results = self.ddgs.text(ing_query, max_results=5)
            for r in ing_results:
                body = r.get("body", "").lower()
                if any(x in body for x in ["ingredients", "contains", "made of", "materials", "composition"]):
                    # Don't capture ingredients if it looks like technical server info
                    if "server" not in body and "protocol" not in body:
                        result["ingredients"] += r.get("body") + "\n---\n"

        except Exception as e:
            print(f"Search fallback failed: {e}")

        return result

        return result


if __name__ == "__main__":
    # Test
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.target.com/p/lavender-38-bergamot-liquid-laundry-detergent-100-fl-oz-everspring-8482/-/A-75663151"
    fetcher = SearchFetcher()
    data = fetcher.search_product(url)
    print(json.dumps(data, indent=2))

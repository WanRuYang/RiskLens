import csv
from pathlib import Path
from urllib.parse import quote_plus


PROJECT_ROOT = Path(__file__).resolve().parent
TEXT_BENCHMARK_CSV = PROJECT_ROOT / "benchmark_amazon_100.csv"
OUTPUT_CSV = PROJECT_ROOT / "benchmark_product_image_manifest.csv"


SAYWEEE_FOOD_CASES = [
    ("weee_001", "food", "weee_dessert", "Hema Taro mochi ice cream 200g", "https://www.sayweee.com/ja/product/Hema-Taro-mochi-ice-cream/110225"),
    ("weee_002", "food", "weee_dessert", "Bubbies Mochi Ice Cream Cookies & Cream 7.5 oz", "https://www.sayweee.com/en/product/Bubbies-Mochi-Ice-Cream-Cookies-Cream/104612"),
    ("weee_003", "food", "weee_noodles", "Instant Noodles 480 g", "https://www.sayweee.com/en/product/Instant-Noodles/2142633"),
    ("weee_004", "food", "weee_dessert", "Shirakiku Mochi Ice Cream Black Sesame 6pcs 8.4 oz", "https://www.sayweee.com/vi/product/Shirakiku-Mochi-Ice-Cream-Black-Sesame-6pcs/103307/"),
    ("weee_005", "food", "weee_beverage", "Hata Ramune Original (Japan)", "https://www.sayweee.com/en/product/Hata-Ramune-Original-Japan/2032383"),
    ("weee_006", "food", "weee_noodles", "Bak Kut Teh Flavor Instant Noodles", "https://www.sayweee.com/en/product/Bak-Kut-Teh-Flavor-Instant-Noodles/2024912"),
    ("weee_007", "food", "weee_dessert", "Mikawaya Mochi Ice Cream Green Tea 6pc", "https://www.sayweee.com/en/product/Mikawaya-Mochi-Ice-Cream--Green-Tea-6pc/20776"),
    ("weee_008", "food", "weee_dessert", "Amazing Matcha Mochi Ice Cream 473 ml", "https://www.sayweee.com/zh/product/Amazing-Matcha-Mochi-Ice-Cream/15554"),
    ("weee_009", "food", "weee_dessert", "Bubbies Mochi Ice Cream Passion Fruit 7.5 oz", "https://www.sayweee.com/en/product/Bubbies-Mochi-Ice-Cream-Passion-Fruit/104613"),
    ("weee_010", "food", "weee_dessert", "Imuraya Soft Mochi Ice Cream, Red bean and Matcha Flavor 4pk 320 ml", "https://www.sayweee.com/product/Imuraya-Soft-Mochi-Ice-Cream-Red-bean-and-Matcha-Flavor-4pk/92855/"),
    ("weee_011", "food", "weee_beverage", "Sangaria Ramune Original Japanese Soda 6.7 fl oz", "https://www.sayweee.com/en/product/Sangaria-Ramune-Original-Japanese-Soda-6-7fl-oz-/2141089"),
    ("weee_012", "food", "weee_dessert", "Shirakiku Mochi Ice Cream Matcha 6pcs 8.4 oz", "https://www.sayweee.com/ko/product/Shirakiku-Mochi-Ice-Cream-Matcha-6pcs/103305/"),
    ("weee_013", "food", "weee_dessert", "My Mochi ice cream Mango 7.5 oz", "https://www.sayweee.com/en/product/My-Mochi-ice-cream-Mango/110364"),
    ("weee_014", "food", "weee_dessert", "My Mochi ice cream Matcha Green Tea 7.5 oz", "https://www.sayweee.com/en/product/My-Mochi-ice-cream-Matcha-Green-Tea/110365"),
    ("weee_015", "food", "weee_beverage", "Lychee Green Tea", "https://www.sayweee.com/en/product/Lychee-Green-Tea/2041167"),
    ("weee_016", "food", "weee_tea", "Itoen Oi Ocha Tea Bag Green Tea 0.07 oz*20 pack", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/green-tea"),
    ("weee_017", "food", "weee_tea", "Itoen Oi Ocha Green Tea Unsweetened 67.6 fl oz", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/green-tea"),
    ("weee_018", "food", "weee_tea", "Itoen Jasmine Green Tea Unsweetened 67.6 fl oz", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/green-tea"),
    ("weee_019", "food", "weee_snacks", "Good Day Fresh Shrimp Chips 80g", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/shrimp-or-prawn-chips"),
    ("weee_020", "food", "weee_snacks", "Dragonfly Shrimp Chips 210 g", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/shrimp-or-prawn-chips"),
    ("weee_021", "food", "weee_snacks", "J-basket Shrimp Chips Spicy Flavor", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/j-basket-shrimp-chips-spicy-flavor"),
    ("weee_022", "food", "weee_snacks", "Crab Shrimp Chips", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/crab-shrimp-chips"),
    ("weee_023", "food", "weee_beverage", "TH Green Tea Natural Lemon Flavor", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/th-green-tea"),
    ("weee_024", "food", "weee_beverage", "Zero Degrees Khong Do Lemon Flavored Green Tea 15.4 fl oz", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/th-green-tea"),
    ("weee_025", "food", "weee_tea", "Yamamotoyama Sencha Green Tea Bag 0.07 oz*16 pack", "https://www.sayweee.com/en/grocery-near-me/lang-en/explore/green-tea"),
]


def amazon_search_url(title: str) -> str:
    return f"https://www.amazon.com/s?k={quote_plus(title)}"


def image_rel_path(case_id: str, image_type: str) -> str:
    return f"benchmark_images/{case_id}/{image_type}.png"


def load_amazon_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    food_rows: list[dict[str, str]] = []
    nonfood_rows: list[dict[str, str]] = []
    with TEXT_BENCHMARK_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["segment"] == "food":
                food_rows.append(row)
            else:
                nonfood_rows.append(row)
    return food_rows, nonfood_rows


def main() -> None:
    amazon_food, amazon_nonfood = load_amazon_rows()
    selected_amazon_food = amazon_food[:25]
    selected_amazon_nonfood = amazon_nonfood[:50]

    rows: list[dict[str, str]] = []

    for idx, row in enumerate(selected_amazon_food, start=1):
        case_id = f"amazon_food_img_{idx:03d}"
        rows.append(
            {
                "case_id": case_id,
                "source_marketplace": "Amazon",
                "segment": "food",
                "category_group": row["category_group"],
                "product_title": row["amazon_seed_title"],
                "marketplace_reference_url": amazon_search_url(row["amazon_seed_title"]),
                "front_image_path": image_rel_path(case_id, "front"),
                "ingredients_image_path": image_rel_path(case_id, "ingredients"),
                "warning_image_path": image_rel_path(case_id, "warning"),
                "capture_status": "pending",
                "notes": "Capture 1 to 3 images from listing, ingredients, or warning view.",
            }
        )

    for case_id, segment, category_group, product_title, url in SAYWEEE_FOOD_CASES:
        rows.append(
            {
                "case_id": case_id,
                "source_marketplace": "SayWeee",
                "segment": segment,
                "category_group": category_group,
                "product_title": product_title,
                "marketplace_reference_url": url,
                "front_image_path": image_rel_path(case_id, "front"),
                "ingredients_image_path": image_rel_path(case_id, "ingredients"),
                "warning_image_path": image_rel_path(case_id, "warning"),
                "capture_status": "pending",
                "notes": "Capture 1 to 3 images from listing, ingredients, or warning view.",
            }
        )

    for idx, row in enumerate(selected_amazon_nonfood, start=1):
        case_id = f"amazon_nonfood_img_{idx:03d}"
        notes = "Capture 1 to 3 images from listing, ingredients, warning, or use-instruction view."
        if row["category_group"] in {"fabric_cleaners", "laundry_softener"}:
            notes = "Include caution statements such as gloves, mask, ventilation, eye protection, or keep away from children if visible."
        rows.append(
            {
                "case_id": case_id,
                "source_marketplace": "Amazon",
                "segment": "non_food",
                "category_group": row["category_group"],
                "product_title": row["amazon_seed_title"],
                "marketplace_reference_url": amazon_search_url(row["amazon_seed_title"]),
                "front_image_path": image_rel_path(case_id, "front"),
                "ingredients_image_path": image_rel_path(case_id, "ingredients"),
                "warning_image_path": image_rel_path(case_id, "warning"),
                "capture_status": "pending",
                "notes": notes,
            }
        )

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "source_marketplace",
                "segment",
                "category_group",
                "product_title",
                "marketplace_reference_url",
                "front_image_path",
                "ingredients_image_path",
                "warning_image_path",
                "capture_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

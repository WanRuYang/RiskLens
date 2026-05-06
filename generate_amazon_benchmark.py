import csv
import random
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = PROJECT_ROOT / "benchmark_amazon_100.csv"


FOOD_POOLS = {
    "grocery_general": [
        "CELSIUS Assorted Flavors Official Variety Pack, Functional Essential Energy Drinks, 12 Fl Oz (Pack of 12)",
        "Nespresso Capsules Vertuo, Variety Pack, Medium and Dark Roast Coffee, 30 Count Coffee Pods, Brews 7.8 oz.",
        "Premier Protein Shake, Chocolate, 30g Protein 1g Sugar 24 Vitamins Minerals Nutrients to Support Immune Health, 11.5 fl oz (Pack of 12)",
        "Sparkling Ice, Black Raspberry Sparkling Water, Zero Sugar Flavored Water, with Vitamins and Antioxidants, Low Calorie Beverage, 17 fl oz Bottles (Pack of 12)",
        "Monster Energy Zero Ultra, Sugar Free Energy Drink, 16 Ounce (Pack of 15)",
        "Core Power Protein Shake, Chocolate, 26g Bottle, 14oz, 12 Pack",
    ],
    "granola_bars": [
        "Nature Valley Crunchy Oats 'n Honey Granola Bars, 60 Bars, 44.7 OZ (30 Pouches)",
        "Quaker Chewy Granola Bars, Chocolate Chip, 58 Count - Packaging May Vary",
        "Fiber One Chewy Bars, Oats and Chocolate, Fiber Snacks, Mega Pack, 15 Ct, 21.2 oz",
        "Nature Valley Crunchy Granola Bars, Value Pack, 60 Bars, 44.7 OZ Count (30 Pouches)",
        "Nature Valley Chewy Granola Bars, Protein, Peanut Butter Dark Chocolate, 15 bars, 21.3 OZ",
        "Nature Valley Sweet and Salty Granola Bars, Peanut, 30 Bars, 36 OZ",
        "CLIF Kid Zbar - Chocolate Brownie - Soft Baked Whole Grain Snack Bars - USDA Organic - Non-GMO - Plant-Based - 1.27 oz. (18 Pack)",
        "KIND Breakfast Bars, Peanut Butter, Healthy Snacks, Gluten Free, 5g Protein, 6 Count",
    ],
    "granola_cereal": [
        "Purely Elizabeth Organic Original, Ancient Grain Granola, Gluten-Free, Non-GMO (3 Ct, 12oz Bags)",
        "Cascadian Farm Organic Granola with No Added Sugar, Blueberry Vanilla Cereal, Resealable Pouch, 11 oz.",
        "Nature Valley Protein Granola, Oats and Honey Granola, Resealable Snack Pouch, Family Size, 17 oz",
        "Cascadian Farm Organic Granola, Oats and Honey Cereal, Resealable Pouch, 11 oz.",
        "MadeGood Chocolate Chip Granola Minis, 28 Count, Organic and Delicious Snacks",
        "Quaker Simply Granola Honey & Almond, (Pack of 2)",
        "Purely Elizabeth Vanilla Almond Butter Keto Granola, Made with Nuts and Seeds, Grain-Free, Gluten-Free, Non-GMO (8oz Bag)",
        "Purely Elizabeth Cookie Granola Choc Chip 11 OZ",
        "NuTrail Nut Granola Cereal, Blueberry Cinnamon, No Sugar Added, Keto, Low Carb, Gluten Free, Grain Free, Healthy Breakfast 8 oz. 1 Count",
    ],
    "whole_coffee_beans": [
        "Lavazza Super Crema Whole Bean Coffee, Medium Espresso Roast, Arabica and Robusta Blend, 2.2 lb Bag, Package May Vary (Pack of 1)",
        "Lavazza Espresso Whole Bean Coffee, Medium Roast, 100% Arabica, 2.2 lb Bag",
        "Amazon Fresh, Colombia Whole Bean Coffee Medium Roast, 32 Oz",
        "San Francisco Bay Coffee - Decaf Medium-Dark Roast Whole Bean Coffee - Decaf Gourmet Blend (2 lb bag) - Swiss Water Processed",
        "Lavazza Espresso Whole Bean Coffee, Medium Roast, 100% Arabica, 2.2 lb Bag (Pack of 1)",
        "Lavazza Espresso Barista Gran Crema Whole Bean Coffee Blend, Medium Espresso Roast, 2.2 LB",
        "Illy Classico Whole Bean Coffee, Medium Roast, Classic Roast With Notes Of Caramel, Orange Blossom And Jasmine, 100% Arabica Coffee, No Preservatives, 8.8 Ounce Can (Pack Of 1)",
        "Starbucks Whole Bean Coffee, Dark Roast Coffee, Espresso Roast, 100% Arabica, 1 bag (18 oz)",
        "Peet's Coffee, Dark Roast Whole Bean Coffee - Major Dickason's Blend 18 Ounce Bag",
    ],
    "sunflower_seeds": [
        "DAVID Roasted and Salted Sunflower Seeds, Original Flavor, 1.75oz. (Pack of 24)",
        "DAVID Roasted and Salted Jumbo Sunflower Seeds, Sweet and Spicy Flavor, 5.25oz.",
        "DAVID Roasted and Salted Jumbo Sunflower Seeds, Original Flavor, 5.25oz. (Pack of 12)",
        "DAVID Roasted and Salted Jumbo Sunflower Seeds, Bar-B-Q Flavor, 5.25oz.",
        "DAVID Roasted and Salted Jumbo Sunflower Seeds, Original Flavor, 5.25oz.",
        "BIGS Sunflower Seeds, Vlasic Dill Pickle Flavor, 5.35 oz.",
        "Elan Organic Raw Sunflower Seeds, 7.1 oz, Unsalted Kernels, Shelled Seeds, No Shell, Non-GMO, Vegan, Gluten-Free, Kosher, All Natural Snacks & Toppings",
        "DAVID Roasted and Salted Jumbo Sunflower Seeds, Cracked Pepper Flavor, 5.25oz.",
        "PLANTERS Pop & Pour Dry Roasted Sunflower Seeds to Eat, Road Trip Snack, Plant-Based Protein, Snacks for Adults, After School Snacks for Kids, Bulk Nuts, Kosher, 5.85oz Jar (4 Count)",
        "DAVID Roasted and Salted Reduced Sodium Sunflower Seeds, Original Flavor, 16oz.",
    ],
    "whey_protein": [
        "Optimum Nutrition Gold Standard 100% Whey Protein Powder, Double Rich Chocolate, 2 Pound (Packaging May Vary)",
        "Premier Protein Powder, Vanilla Milkshake, 30g Protein, 1g Sugar, 100% Whey Protein, Keto Friendly, No Soy Ingredients, Gluten Free, 17 Servings, 23.3 Ounces",
        "Dymatize ISO 100 Whey Protein Powder with 25g of Hydrolyzed 100% Whey Isolate, Vanilla 5 Pound, Package may vary",
        "Body Fortress Super Advanced Whey Protein Powder, Vanilla, Immune Support, Vitamins C & D Plus Zinc, 1.74 lbs",
        "NAKED Whey Vanilla Protein Powder - Only 3 Ingredients - Grass Fed Whey Protein Powder, Vanilla Flavor, and Organic Coconut Sugar, No GMO, No Soy, and Gluten Free - 24 Servings",
        "FlavCity Grass Fed Whey Protein Powder - Vanilla Smoothie - 25g Protein & 10g Collagen - Made with Real Vanilla Bean & Organic Coconut Milk - Gluten Free & No Added Sugars (20 Servings)",
        "Levels Grass Fed Whey Protein Powder, No Artificials, 24G of Protein, Vanilla Bean, 2LB",
    ],
    "collagen": [
        "Vital Proteins Collagen Peptides Powder - Grass Fed Collagen Peptides for Hair, Nail, Skin, Bone & Joint Health, Unflavored, 27 Servings",
        "Vital Proteins Collagen Peptides Powder Advanced with Hyaluronic Acid & Vitamin C - 20oz Collagen Protein, Unflavored, 28 Servings",
        "Collagen Peptides Powder - Naturally-Sourced Hydrolyzed Collagen Powder - Hair, Skin, Nail, and Joint Support - Type I & III Grass-Fed Collagen Supplements for Women and Men - 41 Servings - 16oz",
        "Sports Research Collagen Peptides for Women & Men, Unflavored, 16 oz., Hydrolyzed Type 1 & 3 Collagen Powder Protein Supplement for Healthy Skin, Nails, Bones & Joints",
        "Vital Vitamins Multi Collagen for Women & Men - Type I, II, III, V, X - Grass Fed, Non-GMO - 150 Capsules",
        "Ancient Nutrition Collagen Powder Protein with Probiotics, Unflavored Multi Collagen Protein with Vitamin C, 45 Servings, Hydrolyzed Collagen Peptides Supports Skin and Nails, Gut Health, 16oz",
        "Multi Collagen Protein Powder, 2lbs – Hydrolyzed Collagen Peptides | Type I,II,III,V,X with Biotin 10000mcg, Hyaluronic Acid, Vitamin C – Unflavored – Keto & Paleo Friendly, Easy Dissolve, Non-GMO",
    ],
    "mct_oil": [
        "Nature's Way Organic MCT Oil, 16 Fl Oz, Brain and Body Fuel from Coconuts, C8 Caprylic Acid and C10 Capric Acid, Keto and Paleo Certified, Organic, Non-GMO Project Verified",
        "Sports Research Organic MCT Oil - Keto & Vegan MCTs C8, C10, C12 from Coconuts - Fatty Acid Brain & Body Fuel, Non-GMO & Gluten Free - Flavorless Oil, Perfect in Coffee, Tea & Protein Shakes - 32 oz",
        "Bulletproof Coconut Brain Octane C8 MCT Oil, 16 Ounces, Premium Keto Supplement for Sustained Energy and Fewer Cravings, Brain and Body Fuel, Unflavored, Add to Coffee and Smoothies",
        "NOW Supplements, Berberine Glucose Support, Combined with MCT Oil for Optimal Berberine Absorption, 90 Softgels",
        "Organic MCT Oil Powder with Prebiotic Fiber, 1 Pound (16 Ounce), Fast Fuel for Body and Brain, C8 MCT Oil for Coffee Creamer, No GMOs, Keto Diet, Vegan",
    ],
    "candy_and_energy_bars": [
        "NO COW Chocolate Peanut Butter Energy Bar, 1.77 OZ",
        "JOHN KELLY CHOCOLATES Dark Chocolate Bourbon Fudge Bar, 1.7 OZ",
        "ALTER ECO Organic Velvet Truffles, 0.42 OZ",
        "BARKTHINS Dark Chocolate Pretzel Snack, 10 OZ",
        "Optimum Nutrition Micronized Creatine Monohydrate Powder, Blueberry Lemonade Creatine, 60 Servings, 360 Grams",
    ],
}

NONFOOD_POOLS = {
    "baby_everyday": [
        "Pampers Baby Diapers - Swaddlers - Size 5, 132 Count, Ultra Absorbent Disposable Infant Diaper",
        "Huggies Natural Care Sensitive Baby Wipes, Unscented, Hypoallergenic, 99% Purified Water, 12 Flip-Top Packs (768 Wipes Total), Packaging May Vary",
        "Pampers Sensitive Baby Wipes, Water Based, Hypoallergenic and Unscented, 8 Flip-Top Packs, 4 Refill Packs (1008 Wipes Total)",
        "The Honest Company Clean Conscious Multi-Use Wipes | Hypoallergenic + Unscented for Sensitive Skin | Over 99% Water, Compostable, Plant Based, Baby Wipes | Pattern Play, 720 Count",
        "WaterWipes Plastic-Free Original Baby Wipes, 99.9% Water Based Wipes, Unscented & Hypoallergenic for Sensitive Skin, 60 Count (Pack of 12), Packaging May Vary",
        "Huggies Newborn Diapers, Little Snugglers Baby Diapers, Size Newborn (up to 10 lbs), 31 Count",
        "Huggies Size 5 Diapers, Little Movers Baby Diapers, Size 5 (27+ lbs), 132 Count (2 Packs of 66), Packaging May Vary",
        "Huggies Simply Clean Unscented Baby Diaper Wipes, 11 Flip-Top Packs (704 Wipes Total), Packaging May Vary",
        "Pampers Swim Diapers - Splashers - Size 5+, 17 Count, Gap-Free Disposable Baby Swimming Pants",
        "Dr. Brown’s Natural Flow Level 2 Narrow Baby Bottle Silicone Nipple, Medium Flow, 3m+, 100% Silicone Bottle Nipple, 6 Count",
        "Pampers Training Pants - Easy Ups Boys & Girls Bluey - Size 3T-4T, 124 Count, Children's Potty Underwear",
        "The Honest Company 2-in-1 Cleansing Shampoo + Body Wash for Sensitive Skin | Gentle for Baby | Naturally Derived, Tear-free, Hypoallergenic | Fragrance Free, 10 fl oz",
        "Pampers Diapers - Cruisers 360 - Size 5, 128 Count, Pull-On Diaper",
        "Pampers Diapers - Baby Dry - Size 1, 120 Count, Absorbent Disposable Infant Diaper",
        "Amazon Brand - Mama Bear Gentle Touch Diapers, Size 5, 132 Count",
        "Gaiatop Mini Portable Stroller Fan, Battery Operated Small Clip on, Rechargeable, 360° Rotate Flexible Tripod",
    ],
    "baby_walkers": [
        "VTech Sit-to-Stand Learning Walker (Frustration Free Packaging), Blue",
        "Smart Steps 3.0 Activity Walker, Emily",
        "Boyro Baby Baby Walker, 5-in-1 Baby Walkers for Boys and Girls 6-12 Months with Bouncer, Removable Footrest, Feeding Tray & Music",
        "Uuoeebb Baby Walker with Wheels, One-Touch Folding Anti-Roll 8-Wheel Baby Walkers, 7-Speed Height Adjustment",
        "Bright Starts Disney Baby Mickey Mouse Original Bestie 2-in-1 Baby Activity Walker",
        "Smart Steps Trend Activity Walker, Space Walk Navy",
        "Baby Walker Head Protector Toddler Adjustable Baby Head Protection Backpack Wear Safety Pad (Flying Dragon)",
        "BABY JOY 4-in-1 Baby Walker, Foldable Activity Walker with Adjustable Height & Speed, Music, Lights, Anti-Rollover",
        "5 in 1 Foldable Baby Walker, Activity Baby Walker-Baby Bouncer, Rocker, Activity Center, Seat and Push Walker",
    ],
    "clothing_and_wearables": [
        "Crocs Unisex Adult Classic Clog",
        "Gildan Men's Crew T-Shirts, Multipack, Style G1100",
        "Hanes Men's Boxer Briefs, Cool Dri Moisture-Wicking Underwear, Cotton No-Ride-up for Men, Multi-Packs",
        "Nippies Nipple Covers for Women - Sticky Adhesive Silicone Pasties - Reusable Pasty Nipple Cover with Travel Box",
        "Carhartt Men's Loose Fit Heavyweight Short-Sleeve Pocket T-Shirt",
        "Wrangler Authentics Men's Classic Cargo Stretch Short",
    ],
    "sports_and_hydration": [
        "ZELUS Weighted Vest, 6lb/8lb/12lb/16lb/20lb/25lb/30lb Weight Vest with Reflective Stripe for Workout, Strength Training, Running, Fitness, Muscle Building, Weight Loss, Weightlifting",
        "Stanley IceFlow Stainless Steel Tumbler - Vacuum Insulated Water Bottle with Straw Leak Resistant Flip Cold for 12 Hours or Iced for 2 Days, Black 2.0, 30oz",
        "Amazon Basics Neoprene Dumbbell Hand Weights for Exercise and Muscle Toning",
        "Callaway Golf Supersoft Golf Balls",
        "Fit Simplify Resistance Loop Exercise Bands with Instruction Guide and Carry Bag, Set of 5",
        "Seago Swim Goggles 2 Pack Anti-Fog Anti-UV Wide View Swimming Goggles for Kids 3-14",
    ],
    "fabric_cleaners": [
        "Scotchgard Fabric Water Shield, 13.5 Ounces, Repels Water, Ideal for Couches, Pillows, Furniture, Shoes and More, Long Lasting Protection",
        "Scotchgard Fabric Water Shield, Water Repellent Spray for Spring and Summer Clothing and Household Upholstery Items, Two 10 Oz Cans (Pack of 2)",
        "ForceField Fabric Cleaner Professional Strength, Deeply Penetrates Water Safe Fabric & Fibers of Upholstery, Clothing, Rugs & Carpeting - 22oz",
        "NOYATECH Couch Cleaner and Stain Remover Spray – Professional Strength, Multi-Surface Fabric and Upholstery Cleaner – Pet-Safe, Non-Toxic, Quick-Drying for Couches, Sofas & Car Interiors (32 oz)",
        "Rocco & Roxie Oxy Stain Remover - Oxygen Powered Carpet Cleaner Spray - Spot Cleaner for Upholstery, Couch, Laundry, Rug, Clothes, Car Seat, Mattress, Sofa, and More",
        "Sunbrella Clean Multi-Purpose Fabric Cleaner | All-in-One Solution for Water-Safe Fabrics and Vinyl | Upholstery Cleaner, Removes Stains & Spills | Non-PFAS | 16 fl oz",
        "protectME Fabric Protector and Stain Resistant Spray - Upholstery Fabric Spray for Carpet, Shoes, Couch, Sofa - Non Toxic Water Based Furniture Protector - 25.4 Fl. Oz.",
    ],
    "laundry_softener": [
        "Downy Fabric Softener Liquid, April Fresh Scent, 140 fl oz, 190 Loads, HE Compatible",
        "Downy Fabric Softener Liquid, Cool Cotton Scent, 140 fl oz, 190 Loads",
        "Downy Ultra Soft Fabric Softener Liquid, Calm, Lavender and Vanilla Bean, 56 fl oz, 83 Loads, Pack of 2",
        "Downy Free & Gentle Fabric Softener, Fabric Conditioner, Hypoallergenic, 190 Loads, 140 fl oz",
        "Gain Fabric Softener, Original Scent, 140 fl oz, 190 Loads, HE Compatible",
        "Gain + Odor Defense Liquid Fabric Softener, Super Fresh Blast Scent, 140 oz 190 Loads, HE Compatible",
        "Downy Rinse & Refresh Laundry Odor Remover And Fabric Softener, Cool Cotton, 48 Fl Oz, HE Compatible",
    ],
    "kitchen_home": [
        "Owala FreeSip Insulated Stainless Steel Water Bottle with Straw, BPA-Free Sports Water Bottle, Great for Travel, 24 Oz, Denim",
        "Alpha Grillers Meat Thermometer Digital - Instant Read Food Thermometer for Cooking, Grilling, Air Fryer, Griddle",
        "Etekcity Food Kitchen Scale, Digital Grams and Ounces for Weight Loss, Baking, Cooking, Keto and Meal Prep",
        "Amazon Basics Digital Kitchen Scale with LCD Display, Batteries Included, Weighs up to 11 pounds, Black and Stainless Steel",
        "HydroJug Traveler - 40 oz Water Bottle with Handle & Flip Straw - Fits in Cup Holder, Leak Resistant Tumbler",
    ],
}

FOOD_QUOTAS = {
    "grocery_general": 6,
    "granola_bars": 5,
    "granola_cereal": 5,
    "whole_coffee_beans": 5,
    "sunflower_seeds": 5,
    "whey_protein": 5,
    "collagen": 5,
    "mct_oil": 5,
    "candy_and_energy_bars": 4,
    "bonus_mix": 5,
}

NONFOOD_QUOTAS = {
    "baby_everyday": 10,
    "baby_walkers": 8,
    "clothing_and_wearables": 5,
    "sports_and_hydration": 5,
    "fabric_cleaners": 7,
    "laundry_softener": 7,
    "kitchen_home": 5,
    "bonus_mix": 3,
}


def sample_titles(pool: list[str], count: int, rng: random.Random) -> list[str]:
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


def build_question(segment: str, title: str, category: str) -> str:
    if segment == "food":
        return (
            f"A user found this Amazon product: '{title}'. "
            f"They want a cautious consumer-safety explanation focused on ingredients, additives, processing-related concerns, "
            f"possible Prop 65 links, regional additive rules, and whether occasional use is probably low concern or worth limiting. "
            f"Category hint: {category}."
        )
    return (
        f"A user found this Amazon product: '{title}'. "
        f"They want a cautious consumer-safety explanation focused on likely materials, coatings, plasticizers, heavy metals, "
        f"PFAS, formaldehyde, flame retardants, or other relevant chemical concerns, plus what official sources would be worth checking next. "
        f"Category hint: {category}."
    )


def generate_rows() -> list[dict[str, str]]:
    rng = random.Random(20260503)
    rows: list[dict[str, str]] = []

    food_bonus_pool = (
        FOOD_POOLS["granola_bars"][5:]
        + FOOD_POOLS["granola_cereal"][5:]
        + FOOD_POOLS["whole_coffee_beans"][5:]
        + FOOD_POOLS["sunflower_seeds"][5:]
        + FOOD_POOLS["whey_protein"][5:]
        + FOOD_POOLS["collagen"][5:]
    )

    for category, quota in FOOD_QUOTAS.items():
        if category == "bonus_mix":
            selected = sample_titles(food_bonus_pool, quota, rng)
            source_category = "bonus_food_mix"
        else:
            selected = sample_titles(FOOD_POOLS[category], quota, rng)
            source_category = category
        for title in selected:
            rows.append(
                {
                    "segment": "food",
                    "category_group": source_category,
                    "amazon_seed_title": title,
                }
            )

    nonfood_bonus_pool = (
        NONFOOD_POOLS["baby_everyday"][10:]
        + NONFOOD_POOLS["baby_walkers"][8:]
        + NONFOOD_POOLS["sports_and_hydration"][5:]
        + NONFOOD_POOLS["fabric_cleaners"][5:]
        + NONFOOD_POOLS["laundry_softener"][5:]
    )

    for category, quota in NONFOOD_QUOTAS.items():
        if category == "bonus_mix":
            selected = sample_titles(nonfood_bonus_pool, quota, rng)
            source_category = "bonus_nonfood_mix"
        else:
            selected = sample_titles(NONFOOD_POOLS[category], quota, rng)
            source_category = category
        for title in selected:
            rows.append(
                {
                    "segment": "non_food",
                    "category_group": source_category,
                    "amazon_seed_title": title,
                }
            )

    assert sum(1 for row in rows if row["segment"] == "food") == 50
    assert sum(1 for row in rows if row["segment"] == "non_food") == 50

    final_rows = []
    for idx, row in enumerate(rows, start=1):
        final_rows.append(
            {
                "benchmark_id": f"amazon_{idx:03d}",
                "source_marketplace": "Amazon",
                "source_type": "amazon_seed_title",
                "segment": row["segment"],
                "category_group": row["category_group"],
                "amazon_seed_title": row["amazon_seed_title"],
                "benchmark_question": build_question(
                    row["segment"], row["amazon_seed_title"], row["category_group"]
                ),
            }
        )
    return final_rows


def main() -> None:
    rows = generate_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "benchmark_id",
                "source_marketplace",
                "source_type",
                "segment",
                "category_group",
                "amazon_seed_title",
                "benchmark_question",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

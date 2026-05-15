from app_shared import (
    canonicalize_product_url,
    extract_amazon_ingredients,
    extract_ingredient_text_from_readable,
)


def test_amazon_url_normalization_from_search_link():
    url = (
        "https://www.amazon.com/Nutella-Biscuits-Hazelnut-Sandwich-20-Count/dp/"
        "B0C449R6PX/ref=sr_1_8?keywords=desserts&th=1"
    )
    assert canonicalize_product_url(url) == "https://www.amazon.com/dp/B0C449R6PX"


def test_amazon_url_normalization_drops_slug_and_tracking_query():
    url = (
        "https://www.amazon.com/GTS-ENLIGHTENED-KOMBUCHA-Trilogy-48/dp/B078MFX69J"
        "?pd_rd_w=QsoRm&content-id=amzn1.sym.d77fc71d-50de-409a-abeb-03b0a5133383"
        "&pd_rd_i=B078MFX69J&psc=1&ref_=pd_bap_d_grid_rp_0_1_ec_pr_i"
    )
    assert canonicalize_product_url(url) == "https://www.amazon.com/dp/B078MFX69J"


def test_extract_dropdown_style_ingredients_from_readable_text():
    text = """
    Nutella Biscuits with Hazelnut Cream
    About this item
    Ingredients
    Wheat flour, sugar, palm oil, hazelnuts, skim milk powder, cocoa, soy lecithin,
    baking powder, salt, natural flavor.
    Top highlights
    20-count resealable bag.
    """
    ingredients = extract_ingredient_text_from_readable(text)
    assert "Wheat flour" in ingredients
    assert "palm oil" in ingredients
    assert "Top highlights" not in ingredients


def test_extract_ingredients_from_jsonish_amazon_html():
    html = r'''
    <script>
      {"ingredientStatement":"Wheat flour, sugar, palm oil, hazelnuts, skim milk powder, cocoa, soy lecithin. Contains: wheat, milk, soy, hazelnuts."}
    </script>
    '''
    ingredients = extract_amazon_ingredients(html)
    assert "Wheat flour" in ingredients
    assert "Contains: wheat" in ingredients

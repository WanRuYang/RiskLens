import sys
import types


fake_mlx = types.ModuleType("mlx_engine")
fake_mlx.run_classifier_agent = lambda text: {}
fake_mlx.run_scope_guard_agent = lambda text: "IN_SCOPE_PRODUCT_SAFETY"
fake_mlx.run_scribe_agent = lambda paths: ""
fake_mlx.verify_category_vlm = lambda category, paths: True
sys.modules.setdefault("mlx_engine", fake_mlx)

from app import SessionState, _looks_corrupted_ocr, collect_mode_input


OREO_LABEL_TEXT = """
Nutrition Facts / Valeur nutritive
Per 1 package / pour 1 sachet
Calories 100
Fat / Lipides 4.5 g
Carbohydrate / Glucides 16 g
Sugars / Sucres 9 g
Protein / Proteines 1 g
Sodium 85 mg
OREO
Ingredients: Sugars (sucres), wheat flour, modified palm oil, vegetable oil,
cocoa, corn starch, sodium bicarbonate, salt, soy lecithin.
"""


def test_dense_bilingual_label_text_is_not_treated_as_corrupt() -> None:
    assert not _looks_corrupted_ocr(OREO_LABEL_TEXT, is_screenshot=True)


def test_obvious_repetition_loop_is_still_rejected() -> None:
    assert _looks_corrupted_ocr("內容物：水、食鹽、" + ("乙酸" * 40), is_screenshot=True)


def test_good_label_evidence_survives_one_repetitive_ocr_fragment() -> None:
    state = SessionState(input_mode="image", image_paths=["front.png", "label.png"])
    loop_text = "PRODUCT:\n" + ("OREO " * 40)
    fake_ocr = f"{loop_text}\n\n{OREO_LABEL_TEXT}"

    import app

    original_run_scribe_agent = app.run_scribe_agent
    try:
        app.run_scribe_agent = lambda paths: fake_ocr
        ok, intake_text = collect_mode_input(state)
    finally:
        app.run_scribe_agent = original_run_scribe_agent

    assert ok
    assert "Nutrition Facts" in intake_text
    assert "Ingredients" in intake_text


if __name__ == "__main__":
    test_dense_bilingual_label_text_is_not_treated_as_corrupt()
    test_obvious_repetition_loop_is_still_rejected()
    test_good_label_evidence_survives_one_repetitive_ocr_fragment()
    print("ocr corruption gate: ok")

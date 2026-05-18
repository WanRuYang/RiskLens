from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.service import _resolve_canonical_matches_from_rows, normalize_chemical_mention


APP_DATA_DIR = PROJECT_ROOT / "data" / "app_data"


def _alias_rows() -> list[dict[str, str]]:
    substances: dict[str, dict[str, str]] = {}
    with (APP_DATA_DIR / "canonical_substances.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            substances[row["canonical_id"]] = row

    rows: list[dict[str, str]] = []
    with (APP_DATA_DIR / "canonical_aliases.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            substance = substances[row["canonical_id"]]
            rows.append(
                {
                    **row,
                    "normalized_alias": normalize_chemical_mention(row["alias"]),
                    "preferred_name": substance["preferred_name"],
                    "substance_type": substance["substance_type"],
                    "chemical_family": substance["chemical_family"],
                }
            )
    return rows


def _ids(text: str) -> list[str]:
    matches = _resolve_canonical_matches_from_rows(
        _alias_rows(),
        product_text=text,
        ingredients_text="",
        warning_text="",
        category_text="",
    )
    return [match.canonical_id for match in matches]


def test_fd_and_c_red_no_3_resolves_to_erythrosine() -> None:
    matches = _resolve_canonical_matches_from_rows(
        _alias_rows(),
        product_text="FD and C Red No. 3",
        ingredients_text="",
        warning_text="",
        category_text="",
    )
    assert [match.canonical_id for match in matches] == ["COLOR_RED3_ERYTHROSINE"]
    assert normalize_chemical_mention("FD&C Red No. 3") == "fd&c red 3"


def test_e129_resolves_to_red40_not_red3() -> None:
    ids = _ids("E 129")
    assert ids == ["COLOR_RED40_ALLURA"]
    assert "COLOR_RED3_ERYTHROSINE" not in ids


def test_teflon_nonstick_pan_keeps_ptfe_separate_from_pfas_acids() -> None:
    ids = _ids("Teflon nonstick pan")
    assert ids == ["PTFE_POLYMER"]
    assert "PFOA_PARENT" not in ids
    assert "PFOS_PARENT" not in ids


def test_pfoa_related_compounds_keep_parent_identity() -> None:
    ids = _ids("PFOA, its salts and PFOA-related compounds")
    assert ids == ["PFOA_PARENT"]


def test_dinp_allows_mixture_identity() -> None:
    assert _ids("DINP") == ["DINP_MIXTURE"]


def test_titanium_dioxide_e171_keeps_food_grade_scope() -> None:
    ids = _ids("Titanium dioxide E171")
    assert ids == ["TIO2_FOOD_GRADE"]


def test_airborne_titanium_dioxide_prefers_route_scoped_record() -> None:
    ids = _ids("Titanium dioxide airborne unbound particles of respirable size")
    assert ids == ["TIO2_AIRBORNE_RESPIRABLE_SCOPE"]


def test_microplastics_support_class_without_cas() -> None:
    assert _ids("microplastics") == ["MICROPLASTICS_CLASS"]


def test_mosh_moah_resolves_to_contaminant_class() -> None:
    assert _ids("MOSH/MOAH") == ["MOSH_MOAH_CLASS"]


def test_styrene_does_not_collapse_into_polystyrene() -> None:
    ids = _ids("styrene")
    assert ids == ["STYRENE_PARENT"]
    assert "POLYSTYRENE_POLYMER" not in ids

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DATA = PROJECT_ROOT / "data" / "app_data"
FILES = [
    APP_DATA / "chemical_master.csv",
    APP_DATA / "priority_chemical_overrides.csv",
]

PRIORITY_TERMS = [
    "Melamine",
    "Formaldehyde",
    "Cyanuric acid",
    "Ammeline",
    "Ammelide",
    "Hexamethylenetetramine",
    "Phthalic anhydride",
    "Zinc stearate",
    "Polybrominated diphenyl ethers",
    "Pentabromodiphenyl ether",
    "Octabromodiphenyl ether",
    "Decabromodiphenyl ether",
    "Tetrabromobisphenol A",
    "Tris(1,3-dichloro-2-propyl) phosphate",
    "Tris(2-chloroethyl) phosphate",
    "Antimony trioxide",
    "Polycyclic aromatic hydrocarbons",
    "Polytetrafluoroethylene",
    "Tetrafluoroethylene",
    "Per- and polyfluoroalkyl substances",
    "Hexafluoropropylene oxide dimer acid",
    "Perfluorononanoic acid",
    "Perfluorohexane sulfonic acid",
    "Plasticizers",
    "Phthalates",
    "Diethyl phthalate",
    "Dimethyl phthalate",
    "Di(2-ethylhexyl) adipate",
    "Diisononyl cyclohexane-1,2-dicarboxylate",
    "Acetyl tributyl citrate",
    "Epoxidized soybean oil",
    "Bisphenol A",
    "Bisphenol S",
    "Bisphenol F",
    "Synthetic food colorants",
    "Allura Red AC",
    "Erythrosine",
    "Ponceau 4R",
    "Azorubine / Carmoisine",
    "Tartrazine",
    "Sunset Yellow FCF",
    "Brilliant Blue FCF",
    "Indigo Carmine",
    "Patent Blue V",
]


def rows() -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for path in FILES:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            merged.extend(csv.DictReader(handle))
    return merged


def normalize(value: str) -> str:
    return " ".join((value or "").lower().split())


def main() -> None:
    chemical_rows = rows()
    for term in PRIORITY_TERMS:
        matches = [
            row
            for row in chemical_rows
            if normalize(term) in normalize(row.get("preferred_name", ""))
            or normalize(term) in normalize(row.get("synonyms", ""))
        ]
        status = "present" if matches else "missing"
        aliases = matches[0].get("synonyms", "") if matches else ""
        print(f"{status:7} | {term} | {aliases}")


if __name__ == "__main__":
    main()

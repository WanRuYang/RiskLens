from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


DISCLAIMER = (
    "This analysis is for informational screening only and does not determine whether a product is legally unsafe "
    "or medically harmful. Actual risk depends on dose, frequency, individual sensitivity, and exposure route."
)

SOURCE_BUCKETS = ("FDA", "WHO/IARC", "EU/EFSA/ECHA", "CA Prop 65", "EPA")
ETHOXYLATED_SURFACTANT_RE = re.compile(
    r"(^|\b)(peg-\d+|ppg-\d+|polysorbate\s*\d*|sodium\s+laureth\s+sulfate|"
    r"[a-z]*laureth-\d+|laureth\b|ceteareth-\d+|ceteareth\b|steareth-\d+|steareth\b|"
    r"oleth-\d+|oleth\b|xynol-\d+|xynol\b|ethoxylated\s+alcohols?)",
    re.I,
)
APEO_SURFACTANT_RE = re.compile(
    r"\b(nonylphenol\s+ethoxylate|nonylphenol\s+ethoxylates|octylphenol\s+ethoxylate|"
    r"octylphenol\s+ethoxylates|npe\b|ope\b|apeo\b|alkylphenol\s+ethoxylate|alkylphenol\s+ethoxylates)\b",
    re.I,
)
IRRITANT_SURFACTANT_RE = re.compile(
    r"\b(sls|sles|sodium\s+lauryl\s+sulfate|sodium\s+laureth\s+sulfate|"
    r"cocamidopropyl\s+betaine|capb\b|benzalkonium\s+chloride|quaternium-\d+|"
    r"polyquaternium-\d+|quaternary\s+ammonium)\b",
    re.I,
)
REFINED_OIL_RE = re.compile(
    r"\b(refined\s+vegetable\s+oil|vegetable\s+oil|palm\s+oil|palmolein|canola\s+oil|rapeseed\s+oil|"
    r"soybean\s+oil|sunflower\s+oil|corn\s+oil|cottonseed\s+oil|safflower\s+oil)\b",
    re.I,
)
HIGH_TEMP_FOOD_RE = re.compile(
    r"\b(fried|deep[-\s]?fried|baked|cookie|cookies|cracker|crackers|chips|crisps|roasted|toast|toasted|"
    r"coffee|french\s+fries|potato\s+chips)\b",
    re.I,
)
SMOKED_CURED_MEAT_RE = re.compile(
    r"\b(smoked|cured|bacon|ham|salami|pepperoni|sausage|hot\s+dog|processed\s+meat|red\s+meat|grilled\s+meat|barbecue|bbq)\b",
    re.I,
)
PLASTICIZER_MATERIAL_RE = re.compile(
    r"\b(pvc|vinyl|soft\s+plastic|flexible\s+plastic|plasticizer|plasticiser|phthalate|dehp|dbp|bbp|dinp|didp|dnop|"
    r"shower\s+curtain|inflatable|flexible\s+toy|plastic\s+toy|food\s+container|plastic\s+packaging|plastic\s+wrap)\b",
    re.I,
)
PFAS_MATERIAL_RE = re.compile(
    r"\b(teflon|non[-\s]?stick|ptfe|pfoa|pfos|pfhxs|pfna|genx|hfpo[-\s]?da|waterproof|stain[-\s]?resistant|"
    r"grease[-\s]?resistant|microwave\s+popcorn\s+bag|popcorn\s+bag|food\s+wrapper|takeout\s+container)\b",
    re.I,
)
CORN_SYRUP_RE = re.compile(r"\b(corn\s+syrup|high[-\s]?fructose\s+corn\s+syrup|glucose\s+syrup)\b", re.I)
FORMALDEHYDE_MATERIAL_RE = re.compile(
    r"\b(composite\s+wood|pressed\s+wood|particleboard|mdf|medium[-\s]?density\s+fiberboard|plywood|"
    r"engineered\s+wood|wrinkle[-\s]?free|permanent\s+press|formaldehyde)\b",
    re.I,
)
AZO_DYE_TEXTILE_RE = re.compile(
    r"\b(azo\s+dye|azodye|aromatic\s+amine|dyed\s+(textile|leather)|textile\s+dye|colored\s+leather)\b",
    re.I,
)
FLAME_RETARDANT_RE = re.compile(
    r"\b(flame\s+retardant|fire\s+retardant|treated\s+foam|upholstered\s+foam|polyurethane\s+foam|mattress\s+foam)\b",
    re.I,
)

IdentificationMethod = Literal[
    "listed ingredient",
    "likely process-derived",
    "category-based risk",
    "packaging/contact material",
]
CautionLevel = Literal[
    "low concern",
    "use with caution",
    "limit frequent exposure",
    "avoid for sensitive groups",
    "avoid if allergic",
]
Confidence = Literal["low", "medium", "high", "explicit", "likely", "possible", "weak inference"]


@dataclass
class RiskSource:
    source: str
    is_listed_or_warned: bool
    risk_reason: str = ""
    source_summary: str = ""
    citation_url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SURFACTANT_1_4_DIOXANE_SOURCES = [
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="1,4-dioxane is listed by California Proposition 65 for cancer; ethoxylated surfactants may indicate possible residual contamination, not intentional addition.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
    RiskSource(
        source="California DTSC",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="California DTSC has addressed 1,4-dioxane in consumer products such as personal care and cleaning products; actual residual level requires testing or supplier disclosure.",
        citation_url="https://dtsc.ca.gov/scp/",
    ),
]
SURFACTANT_APEO_SOURCES = [
    RiskSource(
        source="EPA",
        is_listed_or_warned=True,
        risk_reason="aquatic toxicity; environmental persistence; endocrine-disrupting concern",
        source_summary="Alkylphenol ethoxylates such as nonylphenol ethoxylates are associated with aquatic toxicity and endocrine-disrupting environmental concerns.",
        citation_url="https://www.epa.gov/",
    ),
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="aquatic toxicity; environmental persistence; endocrine-disrupting concern",
        source_summary="EU REACH restrictions apply to nonylphenol and nonylphenol ethoxylates in relevant uses.",
        citation_url="https://echa.europa.eu/substances-restricted-under-reach",
    ),
]
SURFACTANT_IRRITANT_SOURCES = [
    RiskSource(
        source="FDA",
        is_listed_or_warned=False,
        risk_reason="skin/eye irritation; allergy / sensitization",
        source_summary="Common surfactants are not automatically hazardous; concern depends on the specific ingredient, concentration, product type, and exposure route.",
        citation_url="",
    ),
]
OIL_PROCESS_CONTAMINANT_SOURCES = [
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="cancer; organ toxicity",
        source_summary="EFSA has evaluated glycidyl fatty acid esters and 3-MCPD/3-MCPD esters as process contaminants associated with refined vegetable oils and fats; concern depends on contaminant level and exposure.",
        citation_url="https://www.efsa.europa.eu/",
    ),
    RiskSource(
        source="WHO/IARC",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="Glycidol has IARC carcinogenic-hazard classification; this is relevant to glycidyl ester contaminant pathways, not proof that a specific oil contains a high level.",
        citation_url="https://monographs.iarc.who.int/",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="Glycidol is listed under California Proposition 65. Glycidyl esters in refined oils are a possible process-contaminant pathway, not an intentionally listed ingredient.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
]
ACRYLAMIDE_SOURCES = [
    RiskSource(
        source="FDA",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="FDA has guidance and monitoring related to acrylamide formation in certain high-temperature cooked foods.",
        citation_url="https://www.fda.gov/food/process-contaminants-food/acrylamide",
    ),
    RiskSource(
        source="WHO/IARC",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="IARC classifies acrylamide as a carcinogenic hazard; product-specific exposure depends on formation level and consumption frequency.",
        citation_url="https://monographs.iarc.who.int/",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="Acrylamide is listed under California Proposition 65. This is usually a process-derived compound in foods, not a label-listed ingredient.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
]
PHTHALATE_SOURCES = [
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="reproductive toxicity; developmental toxicity; endocrine disruption",
        source_summary="EU REACH restricts several phthalates such as DEHP, DBP, BBP, and DIBP in many articles; relevance depends on material and migration/exposure.",
        citation_url="https://echa.europa.eu/substances-restricted-under-reach",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="reproductive toxicity; developmental toxicity",
        source_summary="Several phthalates including DEHP, DBP, BBP, DINP, DIDP, and DNOP have California Proposition 65 listings or warning relevance.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
    RiskSource(
        source="EPA",
        is_listed_or_warned=True,
        risk_reason="developmental toxicity; endocrine disruption",
        source_summary="EPA has assessed phthalates as a chemical class of concern; exposure depends on plastic material, migration, contact, and use pattern.",
        citation_url="https://www.epa.gov/assessing-and-managing-chemicals-under-tsca/phthalates",
    ),
]
PFAS_SOURCES = [
    RiskSource(
        source="EPA",
        is_listed_or_warned=True,
        risk_reason="developmental toxicity; liver/kidney toxicity; endocrine disruption",
        source_summary="EPA identifies PFAS as persistent chemicals with health concerns; relevance to a product depends on the specific PFAS, coating, migration, and use conditions.",
        citation_url="https://www.epa.gov/pfas",
    ),
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="persistence; developmental toxicity; liver toxicity",
        source_summary="EU authorities have restricted or proposed broad restrictions for PFAS uses; non-stick and grease-resistant materials may be relevant exposure contexts.",
        citation_url="https://echa.europa.eu/hot-topics/perfluoroalkyl-chemicals-pfas",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer; developmental toxicity",
        source_summary="Some PFAS such as PFOA and PFOS have California Proposition 65 relevance; PTFE/non-stick wording alone does not confirm PFOA/PFOS presence.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
]
NITROSAMINE_PAH_SOURCES = [
    RiskSource(
        source="WHO/IARC",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="IARC has evaluated processed meat and several PAHs/nitrosamines as carcinogenic hazards. Product-specific risk depends on processing, cooking intensity, dose, and frequency.",
        citation_url="https://monographs.iarc.who.int/",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="Several PAHs and nitrosamines are California Proposition 65-listed chemicals; smoked/cured/grilled meat is a process-pathway signal, not a measured concentration.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
]
METABOLIC_SOURCES = [
    RiskSource(
        source="FDA",
        is_listed_or_warned=False,
        risk_reason="metabolic concern",
        source_summary="Corn syrup/high-fructose corn syrup is a nutrition/metabolic screening concern when frequent intake is high; it is not treated here as a direct Prop 65/EPA/EU chemical warning.",
        citation_url="https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/added-sugars-nutrition-facts-label",
    )
]
FORMALDEHYDE_SOURCES = [
    RiskSource(
        source="EPA",
        is_listed_or_warned=True,
        risk_reason="cancer; respiratory irritation",
        source_summary="EPA regulates formaldehyde emissions from composite wood products under TSCA Title VI; relevance depends on material, emissions, ventilation, and use context.",
        citation_url="https://www.epa.gov/formaldehyde",
    ),
    RiskSource(
        source="CA Prop 65",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="Formaldehyde is listed under California Proposition 65 for cancer. Composite wood or resin clues are exposure-pathway signals, not measured emissions.",
        citation_url="https://oehha.ca.gov/proposition-65/proposition-65-list",
    ),
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="cancer; sensitization",
        source_summary="EU chemical rules include classification and restrictions relevant to formaldehyde and formaldehyde-releasing materials.",
        citation_url="https://echa.europa.eu/",
    ),
]
AZO_DYE_SOURCES = [
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="cancer",
        source_summary="EU REACH restricts certain azo dyes that can release listed aromatic amines in textile and leather articles.",
        citation_url="https://echa.europa.eu/substances-restricted-under-reach",
    )
]
FLAME_RETARDANT_SOURCES = [
    RiskSource(
        source="EPA",
        is_listed_or_warned=True,
        risk_reason="developmental toxicity; endocrine disruption; organ toxicity",
        source_summary="EPA has evaluated flame-retardant chemicals as a group of concern; relevance depends on the specific chemical and product material.",
        citation_url="https://www.epa.gov/assessing-and-managing-chemicals-under-tsca/flame-retardants",
    ),
    RiskSource(
        source="EU/EFSA/ECHA",
        is_listed_or_warned=True,
        risk_reason="developmental toxicity; persistence",
        source_summary="EU rules restrict selected flame-retardant substances in consumer articles. Foam or flame-retardant wording is a material clue, not a measured concentration.",
        citation_url="https://echa.europa.eu/substances-restricted-under-reach",
    ),
]


@dataclass
class DetectedRisk:
    chemical_name: str
    identification_method: IdentificationMethod
    evidence_from_product: str
    dose_context: str
    risk_sources: list[RiskSource] = field(default_factory=list)
    consumer_explanation: str = ""
    caution_level: CautionLevel = "low concern"
    detection_basis: str = ""
    confidence_level: str = ""
    user_recommendation: str = ""
    sensitive_groups: list[str] = field(default_factory=list)
    confidence: Confidence = "low"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_sources"] = [source.as_dict() for source in self.risk_sources]
        data["detection_basis"] = self.detection_basis or self.identification_method
        data["confidence_level"] = self.confidence_level or str(self.confidence)
        data["user_recommendation"] = self.user_recommendation or self.caution_level
        return data


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", safe_text(value).lower()).strip()


def split_ingredients(ingredients_text: str | None) -> list[str]:
    raw = safe_text(ingredients_text)
    if not raw:
        return []
    return [part.strip(" .;:-\t") for part in re.split(r"[,;|]\s*", raw) if part.strip(" .;:-\t")]


def source_bucket(source_authority: str | None, source_type: str | None = "", citation_title: str | None = "") -> str:
    text = normalize_text(" ".join([source_authority or "", source_type or "", citation_title or ""]))
    if any(token in text for token in ["oehha", "prop 65", "proposition 65", "california"]):
        return "CA Prop 65"
    if any(token in text for token in ["iarc", "who"]):
        return "WHO/IARC"
    if any(token in text for token in ["efsa", "echa", "european", "eu ", "cosing"]):
        return "EU/EFSA/ECHA"
    if any(token in text for token in ["epa", "environmental protection agency", "tsca"]):
        return "EPA"
    if "fda" in text or "food and drug" in text:
        return "FDA"
    return source_authority or "Other"


def risk_reason_from_text(*parts: str | None) -> str:
    text = normalize_text(" ".join(part for part in parts if part))
    reasons: list[str] = []
    if any(token in text for token in ["cancer", "carcinogen", "carcinogenic", "carcinogenicity"]):
        reasons.append("cancer")
    if any(token in text for token in ["reproductive", "fertility"]):
        reasons.append("reproductive toxicity")
    if any(token in text for token in ["developmental", "birth defect", "development"]):
        reasons.append("developmental toxicity")
    if any(token in text for token in ["allergy", "allergen", "sensitization", "sensitisation", "skin sensit"]):
        reasons.append("allergy / sensitization")
    if "endocrine" in text or "hormone" in text:
        reasons.append("endocrine disruption")
    if any(token in text for token in ["neuro", "nervous system"]):
        reasons.append("neurotoxicity")
    if any(token in text for token in ["liver", "kidney", "organ", "respiratory"]):
        reasons.append("organ toxicity")
    if not reasons and text:
        reasons.append("other relevant concern")
    return "; ".join(dict.fromkeys(reasons))


def source_summary(row: dict[str, Any]) -> str:
    status = safe_text(row.get("regulatory_status"))
    hazard = safe_text(row.get("hazard_basis"))
    title = safe_text(row.get("regulation_or_list_name")) or safe_text(row.get("citation_title"))
    pieces = [piece for piece in [status, hazard, title] if piece]
    return "; ".join(pieces)[:350]


def build_source_checks(
    source_rows: list[dict[str, Any]],
    *,
    include_negative_checks: bool = True,
) -> list[RiskSource]:
    by_bucket: dict[str, RiskSource] = {}
    for row in source_rows:
        bucket = source_bucket(row.get("source_authority"), row.get("source_type"), row.get("citation_title"))
        current = by_bucket.get(bucket)
        candidate = RiskSource(
            source=bucket,
            is_listed_or_warned=True,
            risk_reason=risk_reason_from_text(
                row.get("hazard_basis"),
                row.get("regulatory_status"),
                row.get("regulation_or_list_name"),
                row.get("citation_title"),
            ),
            source_summary=source_summary(row),
            citation_url=safe_text(row.get("citation_url")),
        )
        if current is None:
            by_bucket[bucket] = candidate
        else:
            current.risk_reason = current.risk_reason or candidate.risk_reason
            current.source_summary = current.source_summary or candidate.source_summary
            current.citation_url = current.citation_url or candidate.citation_url

    if include_negative_checks:
        for bucket in SOURCE_BUCKETS:
            by_bucket.setdefault(
                bucket,
                RiskSource(
                    source=bucket,
                    is_listed_or_warned=False,
                    source_summary="No matching warning/listing was found in the currently loaded source matches.",
                ),
            )
    return [by_bucket[bucket] for bucket in SOURCE_BUCKETS if bucket in by_bucket] + [
        source for bucket, source in by_bucket.items() if bucket not in SOURCE_BUCKETS
    ]


def ingredient_position_context(chemical_name: str, matched_text: str, ingredients_text: str | None) -> str:
    ingredients = split_ingredients(ingredients_text)
    if not ingredients:
        return "Dose or concentration is not available from the current label text."

    needle = normalize_text(matched_text or chemical_name)
    for index, ingredient in enumerate(ingredients, start=1):
        if needle and (needle in normalize_text(ingredient) or normalize_text(ingredient) in needle):
            if index > max(3, len(ingredients) // 2):
                return "Appears to be present in a small amount based on label order."
            if index <= 3:
                return "Appears relatively early in the ingredient list; exact dose is still not provided."
            return "Appears mid-list; exact dose is not provided."
    return "Listed ingredient/order could not be confidently located in the parsed ingredient list."


def caution_level_for_risk(
    *,
    identification_method: str,
    source_rows: list[dict[str, Any]],
    dose_context: str,
    sensitive_groups: list[str],
) -> CautionLevel:
    source_text = normalize_text(" ".join(str(row) for row in source_rows))
    dose_text = normalize_text(dose_context)
    if "allerg" in source_text or "sensit" in source_text:
        return "avoid if allergic"
    if sensitive_groups and any(token in source_text for token in ["reproductive", "developmental", "birth defect"]):
        return "avoid for sensitive groups"
    if identification_method == "category-based risk":
        return "low concern"
    if identification_method == "likely process-derived":
        return "limit frequent exposure"
    if any(token in source_text for token in ["ban", "restricted", "proposition 65", "prop 65", "carcinogen"]):
        return "use with caution" if "small amount" in dose_text else "limit frequent exposure"
    return "low concern"


def confidence_for_method(identification_method: str, source_rows: list[dict[str, Any]]) -> Confidence:
    if identification_method == "listed ingredient" and source_rows:
        return "high"
    if identification_method == "likely process-derived":
        return "medium"
    return "low"


def consumer_explanation_for_risk(
    *,
    chemical_name: str,
    identification_method: str,
    evidence_from_product: str,
    risk_sources: list[RiskSource],
    dose_context: str,
) -> str:
    warned_sources = [source.source for source in risk_sources if source.is_listed_or_warned]
    if identification_method == "listed ingredient":
        basis = f"{chemical_name} appears to match a listed ingredient or ingredient-derived database match."
    elif identification_method == "likely process-derived":
        basis = f"{chemical_name} is not necessarily listed on the label; it is associated with the product/process clue: {evidence_from_product}."
    else:
        basis = f"{chemical_name} is a category-based concern, not a confirmed ingredient in this product."
    source_text = f" Matching source groups: {', '.join(warned_sources)}." if warned_sources else " No major source warning was matched in the loaded data."
    return f"{basis} {dose_context} Exposure depends on dose, frequency, and route.{source_text}"


def detected_risk_from_chemical_match(
    chemical_match: dict[str, Any],
    *,
    regulatory_rows: list[dict[str, Any]],
    ingredients_text: str | None,
    include_negative_source_checks: bool = True,
) -> DetectedRisk:
    chemical_id = chemical_match.get("chemical_id")
    chemical_name = safe_text(chemical_match.get("preferred_name")) or safe_text(chemical_match.get("matched_text"))
    source_rows = [
        row for row in regulatory_rows
        if not chemical_id or not row.get("chemical_id") or row.get("chemical_id") == chemical_id
    ]
    dose_context = ingredient_position_context(
        chemical_name,
        safe_text(chemical_match.get("matched_text")),
        ingredients_text,
    )
    risk_sources = build_source_checks(source_rows, include_negative_checks=include_negative_source_checks)
    sensitive_groups = sensitive_groups_from_sources(source_rows)
    caution_level = caution_level_for_risk(
        identification_method="listed ingredient",
        source_rows=source_rows,
        dose_context=dose_context,
        sensitive_groups=sensitive_groups,
    )
    return DetectedRisk(
        chemical_name=chemical_name or "Unknown chemical",
        identification_method="listed ingredient",
        evidence_from_product=safe_text(chemical_match.get("matched_text")) or chemical_name,
        dose_context=dose_context,
        risk_sources=risk_sources,
        consumer_explanation=consumer_explanation_for_risk(
            chemical_name=chemical_name or "Unknown chemical",
            identification_method="listed ingredient",
            evidence_from_product=safe_text(chemical_match.get("matched_text")) or chemical_name,
            risk_sources=risk_sources,
            dose_context=dose_context,
        ),
        caution_level=caution_level,
        sensitive_groups=sensitive_groups,
        confidence=confidence_for_method("listed ingredient", source_rows),
    )


def process_derived_risk(
    chemical_name: str,
    *,
    process_clue: str,
    source_rows: list[dict[str, Any]] | None = None,
    include_negative_source_checks: bool = True,
) -> DetectedRisk:
    source_rows = source_rows or []
    risk_sources = build_source_checks(source_rows, include_negative_checks=include_negative_source_checks)
    dose_context = "Exposure level is uncertain because this compound would be process-derived and is not directly listed on the label."
    sensitive_groups = sensitive_groups_from_sources(source_rows)
    caution_level = caution_level_for_risk(
        identification_method="likely process-derived",
        source_rows=source_rows,
        dose_context=dose_context,
        sensitive_groups=sensitive_groups,
    )
    return DetectedRisk(
        chemical_name=chemical_name,
        identification_method="likely process-derived",
        evidence_from_product=process_clue,
        dose_context=dose_context,
        risk_sources=risk_sources,
        consumer_explanation=consumer_explanation_for_risk(
            chemical_name=chemical_name,
            identification_method="likely process-derived",
            evidence_from_product=process_clue,
            risk_sources=risk_sources,
            dose_context=dose_context,
        ),
        caution_level=caution_level,
        sensitive_groups=sensitive_groups,
        confidence=confidence_for_method("likely process-derived", source_rows),
    )


def category_based_risk(
    chemical_name: str,
    *,
    category_clue: str,
    source_rows: list[dict[str, Any]] | None = None,
    include_negative_source_checks: bool = True,
) -> DetectedRisk:
    source_rows = source_rows or []
    risk_sources = build_source_checks(source_rows, include_negative_checks=include_negative_source_checks)
    dose_context = "Exposure level is uncertain because this is category-based context, not a confirmed product ingredient or measurement."
    sensitive_groups = sensitive_groups_from_sources(source_rows)
    return DetectedRisk(
        chemical_name=chemical_name,
        identification_method="category-based risk",
        evidence_from_product=category_clue,
        dose_context=dose_context,
        risk_sources=risk_sources,
        consumer_explanation=consumer_explanation_for_risk(
            chemical_name=chemical_name,
            identification_method="category-based risk",
            evidence_from_product=category_clue,
            risk_sources=risk_sources,
            dose_context=dose_context,
        ),
        caution_level="low concern",
        sensitive_groups=sensitive_groups,
        confidence=confidence_for_method("category-based risk", source_rows),
    )


def product_exposure_context(product_category: str, warning_text: str | None = "") -> str:
    text = normalize_text(" ".join([product_category, warning_text or ""]))
    notes: list[str] = []
    if any(token in text for token in ["conditioner", "shampoo", "body wash", "rinse", "personal_care"]):
        notes.append("For rinse-off products, exposure is usually shorter than leave-on products.")
    if any(token in text for token in ["spray", "aerosol", "mist"]):
        notes.append("For spray or aerosol products, inhalation exposure may matter more.")
    if any(token in text for token in ["children", "baby", "kid"]):
        notes.append("Extra caution is reasonable for products used by children.")
    return " ".join(notes)


def surfactant_dose_context(
    *,
    ingredient: str,
    ingredients_text: str | None,
    product_category: str,
    warning_text: str | None = "",
    process_derived: bool = False,
) -> str:
    if process_derived:
        base = (
            "Exposure level is uncertain because this is a possible residual contaminant, not an intentionally listed ingredient; "
            "actual level requires lab testing or supplier disclosure."
        )
    else:
        base = ingredient_position_context(ingredient, ingredient, ingredients_text)
    exposure = product_exposure_context(product_category, warning_text)
    return " ".join(part for part in [base, exposure] if part)


def surfactant_sensitive_groups(product_category: str, warning_text: str | None = "") -> list[str]:
    text = normalize_text(" ".join([product_category, warning_text or ""]))
    groups = ["frequent users"]
    if any(token in text for token in ["children", "baby", "kid"]):
        groups.append("children")
    if any(token in text for token in ["fragrance", "parfum", "allerg", "sensit"]):
        groups.append("people with fragrance/allergy sensitivity")
    groups.append("eczema-prone users")
    return list(dict.fromkeys(groups))


def surfactant_risks_from_ingredients(
    ingredients_text: str | None,
    *,
    product_category: str,
    warning_text: str | None = "",
) -> list[DetectedRisk]:
    ingredients = split_ingredients(ingredients_text)
    if not ingredients:
        return []

    risks: list[DetectedRisk] = []
    seen_keys: set[str] = set()
    category_text = normalize_text(product_category)

    for ingredient in ingredients:
        normalized_ingredient = normalize_text(ingredient)
        if normalized_ingredient == "surfactant" or normalized_ingredient == "surfactants":
            continue

        if ETHOXYLATED_SURFACTANT_RE.search(ingredient) and "possible_1_4_dioxane" not in seen_keys:
            seen_keys.add("possible_1_4_dioxane")
            dose_context = surfactant_dose_context(
                ingredient=ingredient,
                ingredients_text=ingredients_text,
                product_category=product_category,
                warning_text=warning_text,
                process_derived=True,
            )
            risk_sources = [RiskSource(**source.as_dict()) for source in SURFACTANT_1_4_DIOXANE_SOURCES]
            risks.append(
                DetectedRisk(
                    chemical_name="1,4-dioxane (possible residual contaminant)",
                    identification_method="likely process-derived",
                    evidence_from_product=f"Ethoxylated surfactant clue: {ingredient}",
                    dose_context=dose_context,
                    risk_sources=risk_sources,
                    consumer_explanation=(
                        f"{ingredient} may indicate ethoxylated surfactant chemistry. That can be associated with possible "
                        "1,4-dioxane residual contamination, but 1,4-dioxane is not intentionally added and is not confirmed "
                        "without lab testing or supplier disclosure. Risk depends on concentration, product type, exposure route, and frequency of use."
                    ),
                    caution_level="use with caution",
                    sensitive_groups=surfactant_sensitive_groups(product_category, warning_text),
                    confidence="medium" if any(term in normalized_ingredient for term in ["laureth", "ceteareth", "steareth", "polysorbate", "peg", "ppg"]) else "low",
                )
            )

        if APEO_SURFACTANT_RE.search(ingredient) and "apeo" not in seen_keys:
            seen_keys.add("apeo")
            dose_context = surfactant_dose_context(
                ingredient=ingredient,
                ingredients_text=ingredients_text,
                product_category=product_category,
                warning_text=warning_text,
            )
            risk_sources = [RiskSource(**source.as_dict()) for source in SURFACTANT_APEO_SOURCES]
            caution = "limit frequent exposure" if any(token in category_text for token in ["cleaner", "textile", "industrial", "household"]) else "use with caution"
            risks.append(
                DetectedRisk(
                    chemical_name="Alkylphenol ethoxylates / nonylphenol ethoxylates",
                    identification_method="listed ingredient",
                    evidence_from_product=ingredient,
                    dose_context=dose_context,
                    risk_sources=risk_sources,
                    consumer_explanation=(
                        f"{ingredient} appears to indicate an alkylphenol ethoxylate surfactant family. Concern is mainly "
                        "environmental: aquatic toxicity, persistence, and endocrine-disrupting concern. This is not the same as saying all surfactants are hazardous."
                    ),
                    caution_level=caution,
                    sensitive_groups=["frequent users"],
                    confidence="high" if re.search(r"nonylphenol|octylphenol", normalized_ingredient) else "medium",
                )
            )

        if IRRITANT_SURFACTANT_RE.search(ingredient):
            key = f"irritant::{normalized_ingredient}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            dose_context = surfactant_dose_context(
                ingredient=ingredient,
                ingredients_text=ingredients_text,
                product_category=product_category,
                warning_text=warning_text,
            )
            risk_sources = [RiskSource(**source.as_dict()) for source in SURFACTANT_IRRITANT_SOURCES]
            risks.append(
                DetectedRisk(
                    chemical_name=ingredient,
                    identification_method="listed ingredient",
                    evidence_from_product=ingredient,
                    dose_context=dose_context,
                    risk_sources=risk_sources,
                    consumer_explanation=(
                        f"{ingredient} is a surfactant or quaternary ammonium-type ingredient that may be irritating or sensitizing "
                        "for some users depending on concentration, product type, exposure route, and frequency. Do not interpret this as a carcinogenic warning unless a specific carcinogenic contaminant or listed chemical is detected."
                    ),
                    caution_level="avoid if allergic",
                    sensitive_groups=surfactant_sensitive_groups(product_category, warning_text),
                    confidence="medium",
                )
            )

    return risks


def clone_sources(sources: list[RiskSource]) -> list[RiskSource]:
    return [RiskSource(**source.as_dict()) for source in sources]


def contains_child_context(text: str) -> bool:
    return any(token in normalize_text(text) for token in ["infant", "baby", "children", "child", "kids", "toy", "teether"])


def inferred_risk(
    *,
    chemical_name: str,
    identification_method: IdentificationMethod,
    detection_basis: str,
    evidence_from_product: str,
    dose_context: str,
    risk_sources: list[RiskSource],
    consumer_explanation: str,
    caution_level: CautionLevel,
    confidence_level: str,
    sensitive_groups: list[str] | None = None,
) -> DetectedRisk:
    return DetectedRisk(
        chemical_name=chemical_name,
        identification_method=identification_method,
        evidence_from_product=evidence_from_product,
        dose_context=dose_context,
        risk_sources=risk_sources,
        consumer_explanation=consumer_explanation,
        caution_level=caution_level,
        detection_basis=detection_basis,
        confidence_level=confidence_level,
        user_recommendation=caution_level,
        sensitive_groups=sensitive_groups or ["frequent users"],
        confidence=confidence_level if confidence_level in {"explicit", "likely", "possible", "weak inference"} else "possible",
    )


def oil_and_food_processing_risks(
    *,
    product_name: str,
    ingredients_text: str | None,
    product_category: str,
) -> list[DetectedRisk]:
    text = " ".join([product_name, ingredients_text or "", product_category])
    risks: list[DetectedRisk] = []
    oil_match = REFINED_OIL_RE.search(text)
    high_temp_match = HIGH_TEMP_FOOD_RE.search(text)
    child_context = contains_child_context(text)

    if oil_match:
        oil_text = oil_match.group(0)
        risks.append(
            inferred_risk(
                chemical_name="Glycidyl esters / 3-MCPD esters",
                identification_method="likely process-derived",
                detection_basis="processing derivative",
                evidence_from_product=f"Refined oil clue: {oil_text}",
                dose_context=(
                    "Possible process-derived contaminants associated with refined vegetable oils/fats. "
                    "This does not mean the oil itself is toxic, and confirmation requires contaminant testing or supplier data."
                ),
                risk_sources=clone_sources(OIL_PROCESS_CONTAMINANT_SOURCES),
                consumer_explanation=(
                    f"{oil_text} can be a clue for refined-oil process contaminants such as glycidyl esters or 3-MCPD esters. "
                    "The ingredient is broad, so the app treats this as a possible processing-pathway signal rather than a confirmed chemical in the product."
                ),
                caution_level="avoid for sensitive groups" if child_context else "use with caution",
                confidence_level="possible",
                sensitive_groups=["infants/children", "pregnant people", "frequent users"] if child_context else ["frequent users"],
            )
        )

    if high_temp_match:
        clue = high_temp_match.group(0)
        risks.append(
            inferred_risk(
                chemical_name="Acrylamide",
                identification_method="likely process-derived",
                detection_basis="processing derivative",
                evidence_from_product=f"High-temperature food clue: {clue}",
                dose_context=(
                    "Exposure level is uncertain because acrylamide is process-derived and not directly listed on the label. "
                    "Levels depend on recipe, cooking temperature, browning, and frequency of consumption."
                ),
                risk_sources=clone_sources(ACRYLAMIDE_SOURCES),
                consumer_explanation=(
                    f"{clue} suggests possible high-temperature cooking. Acrylamide may form in some baked, fried, or roasted carbohydrate-rich foods; "
                    "this is not the same as saying the product is unsafe."
                ),
                caution_level="limit frequent exposure",
                confidence_level="likely" if re.search(r"fried|chips|coffee|roasted", clue, re.I) else "possible",
                sensitive_groups=["children", "pregnant people", "frequent users"] if child_context else ["frequent users"],
            )
        )

    if CORN_SYRUP_RE.search(text):
        corn_syrup = CORN_SYRUP_RE.search(text).group(0)
        risks.append(
            inferred_risk(
                chemical_name="Added sugars / corn syrup",
                identification_method="listed ingredient",
                detection_basis="ingredient",
                evidence_from_product=corn_syrup,
                dose_context=ingredient_position_context("corn syrup", corn_syrup, ingredients_text)
                if ingredients_text else "Amount depends on nutrition facts and serving size; this is a nutrition context, not a chemical-hazard listing.",
                risk_sources=clone_sources(METABOLIC_SOURCES),
                consumer_explanation=(
                    f"{corn_syrup} is treated as a nutrition/metabolic screening point, especially for frequent intake. "
                    "It is not being labeled as a Prop 65, EPA, or EU carcinogenic chemical warning."
                ),
                caution_level="low concern",
                confidence_level="explicit",
                sensitive_groups=["frequent users"],
            )
        )

    if SMOKED_CURED_MEAT_RE.search(text):
        clue = SMOKED_CURED_MEAT_RE.search(text).group(0)
        risks.append(
            inferred_risk(
                chemical_name="PAHs / nitrosamines",
                identification_method="likely process-derived",
                detection_basis="processing derivative",
                evidence_from_product=f"Processed/smoked/cured meat clue: {clue}",
                dose_context="Exposure level is uncertain; process-derived levels depend on curing, smoking, grilling, charring, formulation, dose, and frequency.",
                risk_sources=clone_sources(NITROSAMINE_PAH_SOURCES),
                consumer_explanation=(
                    f"{clue} suggests a possible smoked, cured, grilled, or processed-meat pathway. PAHs or nitrosamines may be relevant, "
                    "but the product-specific level is not known without formulation and testing data."
                ),
                caution_level="limit frequent exposure",
                confidence_level="likely",
                sensitive_groups=["children", "pregnant people", "frequent users"],
            )
        )

    return risks


def packaging_and_material_risks(
    *,
    product_name: str,
    ingredients_text: str | None,
    product_category: str,
) -> list[DetectedRisk]:
    text = " ".join([product_name, ingredients_text or "", product_category])
    normalized = normalize_text(text)
    risks: list[DetectedRisk] = []

    if PLASTICIZER_MATERIAL_RE.search(text):
        match = PLASTICIZER_MATERIAL_RE.search(text).group(0)
        child_context = contains_child_context(text)
        strong_pvc = any(token in normalized for token in ["pvc", "vinyl", "soft plastic", "flexible plastic", "shower curtain"])
        risks.append(
            inferred_risk(
                chemical_name="Phthalates such as DEHP, DBP, BBP, DINP, DIDP, DNOP",
                identification_method="packaging/contact material",
                detection_basis="packaging/contact material" if any(token in normalized for token in ["container", "packaging", "wrap"]) else "product category",
                evidence_from_product=f"Plasticizer/material clue: {match}",
                dose_context=(
                    "This is an inferred material/contact pathway. Confirmation requires label material details, supplier disclosure, or testing; "
                    "migration depends on material, food/contact type, time, heat, and use pattern."
                ),
                risk_sources=clone_sources(PHTHALATE_SOURCES),
                consumer_explanation=(
                    f"{match} suggests a flexible plastic, PVC/vinyl, packaging, toy, or contact-material pathway where phthalates can be relevant. "
                    "The app does not claim phthalates are present unless the label or testing confirms them."
                ),
                caution_level="avoid for sensitive groups" if child_context or strong_pvc else "use with caution",
                confidence_level="likely" if strong_pvc else "possible",
                sensitive_groups=["children", "pregnant people", "frequent users"] if child_context else ["pregnant people", "children", "frequent users"],
            )
        )

    if PFAS_MATERIAL_RE.search(text):
        match = PFAS_MATERIAL_RE.search(text).group(0)
        explicit = any(token in normalized for token in ["ptfe", "pfoa", "pfos", "pfhxs", "pfna", "genx", "hfpo"])
        packaging = any(token in normalized for token in ["grease", "popcorn bag", "wrapper", "packaging", "food container"])
        risks.append(
            inferred_risk(
                chemical_name="PFAS/PTFE-related coating or fluorinated chemistry",
                identification_method="packaging/contact material",
                detection_basis="packaging/contact material" if packaging else "product category",
                evidence_from_product=f"PFAS/non-stick clue: {match}",
                dose_context=(
                    "This is a coating/material inference. PTFE/non-stick or grease-resistant wording does not confirm PFOA/PFOS/PFAS exposure; "
                    "risk depends on the exact chemistry, condition of coating, heat, migration, and use frequency."
                ),
                risk_sources=clone_sources(PFAS_SOURCES),
                consumer_explanation=(
                    f"{match} suggests a non-stick, fluorinated, waterproof/stain-resistant, or grease-resistant material pathway. "
                    "Treat this as a material-screening signal unless a specific PFAS is listed or disclosed."
                ),
                caution_level="limit frequent exposure" if packaging or explicit else "use with caution",
                confidence_level="explicit" if explicit else "possible",
                sensitive_groups=["children", "pregnant people", "frequent users"],
            )
        )

    return risks


def eu_strict_material_risks(
    *,
    product_name: str,
    ingredients_text: str | None,
    product_category: str,
) -> list[DetectedRisk]:
    text = " ".join([product_name, ingredients_text or "", product_category])
    risks: list[DetectedRisk] = []

    if FORMALDEHYDE_MATERIAL_RE.search(text):
        match = FORMALDEHYDE_MATERIAL_RE.search(text).group(0)
        explicit = re.search(r"\bformaldehyde\b", text, re.I) is not None
        risks.append(
            inferred_risk(
                chemical_name="Formaldehyde / formaldehyde emissions",
                identification_method="listed ingredient" if explicit else "category-based risk",
                detection_basis="ingredient" if explicit else "product category",
                evidence_from_product=f"Formaldehyde/composite-material clue: {match}",
                dose_context=(
                    "If formaldehyde is explicitly listed, dose depends on concentration and product use. "
                    "If inferred from composite wood, foam, textile finishing, or resin material, confirmation requires label, certification, emission data, or testing."
                ),
                risk_sources=clone_sources(FORMALDEHYDE_SOURCES),
                consumer_explanation=(
                    f"{match} can be relevant to formaldehyde exposure pathways, especially composite wood, resin, or treated-textile materials. "
                    "This is a screening signal unless the label directly lists formaldehyde or provides emission data."
                ),
                caution_level="use with caution",
                confidence_level="explicit" if explicit else "possible",
                sensitive_groups=["children", "pregnant people", "people with respiratory sensitivity", "frequent users"],
            )
        )

    if AZO_DYE_TEXTILE_RE.search(text):
        match = AZO_DYE_TEXTILE_RE.search(text).group(0)
        explicit = re.search(r"\b(azo\s+dye|azodye|aromatic\s+amine)\b", text, re.I) is not None
        risks.append(
            inferred_risk(
                chemical_name="Azo dyes / aromatic amines",
                identification_method="listed ingredient" if explicit else "category-based risk",
                detection_basis="ingredient" if explicit else "product category",
                evidence_from_product=f"Dyed textile/leather clue: {match}",
                dose_context=(
                    "Azo-dye concern depends on the specific dye and whether restricted aromatic amines are released. "
                    "Confirmation requires material disclosure or testing."
                ),
                risk_sources=clone_sources(AZO_DYE_SOURCES),
                consumer_explanation=(
                    f"{match} suggests a dyed textile or leather pathway. EU restrictions apply to certain azo dyes/aromatic amines, "
                    "but a dyed product is not automatically unsafe."
                ),
                caution_level="use with caution",
                confidence_level="explicit" if explicit else "weak inference",
                sensitive_groups=["children", "people with allergies", "frequent users"],
            )
        )

    if FLAME_RETARDANT_RE.search(text):
        match = FLAME_RETARDANT_RE.search(text).group(0)
        explicit = re.search(r"\b(flame\s+retardant|fire\s+retardant)\b", text, re.I) is not None
        risks.append(
            inferred_risk(
                chemical_name="Flame-retardant chemicals",
                identification_method="category-based risk",
                detection_basis="product category",
                evidence_from_product=f"Flame-retardant/foam clue: {match}",
                dose_context=(
                    "This is a material-use inference. Concern depends on the exact flame-retardant chemistry, whether it is additive or reactive, "
                    "dust/contact exposure, product age, and frequency of use."
                ),
                risk_sources=clone_sources(FLAME_RETARDANT_SOURCES),
                consumer_explanation=(
                    f"{match} can be relevant to flame-retardant screening in foam, upholstery, and treated products. "
                    "The app does not identify a specific flame retardant unless the product discloses it."
                ),
                caution_level="use with caution",
                confidence_level="likely" if explicit else "possible",
                sensitive_groups=["children", "pregnant people", "frequent users"],
            )
        )

    return risks


def sensitive_groups_from_sources(source_rows: list[dict[str, Any]]) -> list[str]:
    text = normalize_text(" ".join(str(row) for row in source_rows))
    groups: list[str] = []
    if any(token in text for token in ["developmental", "birth defect", "child", "children"]):
        groups.append("children")
    if any(token in text for token in ["reproductive", "pregnan", "birth defect", "developmental"]):
        groups.append("pregnant people")
    if any(token in text for token in ["allerg", "sensit"]):
        groups.append("people with allergies")
    if source_rows:
        groups.append("frequent users")
    return list(dict.fromkeys(groups))


def overall_risk_level(risks: list[DetectedRisk], uncertainties: list[str]) -> str:
    if not risks:
        return "low" if not uncertainties else "uncertain"
    caution_rank = {
        "low concern": 1,
        "use with caution": 2,
        "limit frequent exposure": 3,
        "avoid for sensitive groups": 3,
        "avoid if allergic": 3,
    }
    max_rank = max(caution_rank.get(risk.caution_level, 1) for risk in risks)
    if max_rank >= 3:
        return "moderate"
    if max_rank == 2:
        return "moderate"
    return "low"


def overall_recommendation(risks: list[DetectedRisk], uncertainties: list[str]) -> str:
    if not risks:
        if any("inferred from product name and category" in normalize_text(item) for item in uncertainties):
            return (
                "No major risk warnings were identified from the available information. "
                "Ingredient/material details are unknown, so this is inferred from product name and category rather than a label-confirmed ingredient/material review."
            )
        return "No major risk warnings were identified from the available ingredient and category information."
    if any(risk.caution_level in {"avoid for sensitive groups", "avoid if allergic"} for risk in risks):
        return "Review the matched concern(s), especially for sensitive groups, allergies, pregnancy, children, or frequent use."
    if any(risk.caution_level == "limit frequent exposure" for risk in risks):
        return "Occasional use may be reasonable for many consumers, but consider limiting frequent repeated exposure."
    if uncertainties:
        return "Use the result as a screening signal and verify the label or manufacturer details if this product will be used frequently."
    return "No major high-confidence concern was identified; use normal product-specific judgment."


def build_product_risk_output(
    *,
    product_name: str,
    product_category: str,
    analysis_basis: list[str],
    identified_risks: list[DetectedRisk] | list[dict[str, Any]],
    notable_uncertainties: list[str] | None = None,
    ingredient_material_status: str = "",
) -> dict[str, Any]:
    risk_objects = [
        risk if isinstance(risk, DetectedRisk) else risk_from_dict(risk)
        for risk in identified_risks
    ]
    risk_objects = dedupe_risks(risk_objects)
    uncertainties = notable_uncertainties or []
    final_guidance = overall_recommendation(risk_objects, uncertainties)
    return {
        "product_summary": {
            "product_name": product_name,
            "product_category": product_category,
            "analysis_basis": analysis_basis,
            "ingredient_material_status": ingredient_material_status,
            "overall_risk_level": overall_risk_level(risk_objects, uncertainties),
            "overall_recommendation": final_guidance,
        },
        "identified_risks": [risk.as_dict() for risk in risk_objects],
        "notable_uncertainties": uncertainties,
        "final_consumer_guidance": final_guidance,
        "disclaimer": DISCLAIMER,
    }


def dedupe_risks(risks: list[DetectedRisk]) -> list[DetectedRisk]:
    deduped: list[DetectedRisk] = []
    seen: set[tuple[str, str, str]] = set()
    for risk in risks:
        key = (
            normalize_text(risk.chemical_name),
            normalize_text(risk.detection_basis or risk.identification_method),
            normalize_text(risk.evidence_from_product)[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(risk)
    return deduped


def risk_from_dict(data: dict[str, Any]) -> DetectedRisk:
    return DetectedRisk(
        chemical_name=safe_text(data.get("chemical_name")),
        identification_method=data.get("identification_method", "category-based risk"),
        evidence_from_product=safe_text(data.get("evidence_from_product")),
        dose_context=safe_text(data.get("dose_context")),
        risk_sources=[
            source if isinstance(source, RiskSource) else RiskSource(
                source=safe_text(source.get("source")),
                is_listed_or_warned=bool(source.get("is_listed_or_warned")),
                risk_reason=safe_text(source.get("risk_reason")),
                source_summary=safe_text(source.get("source_summary")),
                citation_url=safe_text(source.get("citation_url")),
            )
            for source in data.get("risk_sources", [])
        ],
        consumer_explanation=safe_text(data.get("consumer_explanation")),
        caution_level=data.get("caution_level", "low concern"),
        detection_basis=safe_text(data.get("detection_basis")),
        confidence_level=safe_text(data.get("confidence_level")),
        user_recommendation=safe_text(data.get("user_recommendation")),
        sensitive_groups=[safe_text(group) for group in data.get("sensitive_groups", []) if safe_text(group)],
        confidence=data.get("confidence", "low"),
    )


def processing_risks_from_profile(
    food_processing_profile: dict[str, Any] | None,
    *,
    category_level_rows: list[dict[str, Any]],
) -> list[DetectedRisk]:
    profile = food_processing_profile or {}
    processing_level = safe_text(profile.get("processing_level"))
    rationale = safe_text(profile.get("rationale"))
    if processing_level in {"", "unknown", "food_processing_unknown", "minimally_processed_raw_meat"}:
        return []

    process_map = {
        "baked": "Acrylamide",
        "fried": "Acrylamide",
        "roasted_coffee": "Acrylamide",
        "smoked": "PAHs",
        "grilled": "PAHs",
        "cured": "Nitrosamines",
        "processed_or_formula_food": "",
    }
    matched: list[DetectedRisk] = []
    normalized = normalize_text(" ".join([processing_level, rationale]))
    for clue, chemical in process_map.items():
        if chemical and clue in normalized:
            matched.append(
                process_derived_risk(
                    chemical,
                    process_clue=rationale or processing_level,
                    source_rows=category_level_rows,
                )
            )
    return matched


def risk_output_from_api_result(
    api_result: dict[str, Any],
    *,
    product_name: str | None = None,
    ingredients_text: str | None = None,
) -> dict[str, Any]:
    url_context = api_result.get("url_context") or {}
    inferred = api_result.get("inferred_category") or {}
    name = safe_text(product_name) or safe_text(url_context.get("product_text"))
    category = " / ".join(
        part for part in [
            safe_text(inferred.get("product_use_category")),
            safe_text(inferred.get("material_subcategory")),
        ]
        if part and part != "unknown"
    ) or safe_text(url_context.get("category")) or "unknown"
    ingredients = safe_text(ingredients_text) or safe_text(url_context.get("ingredients_text"))
    warning_text = safe_text(api_result.get("warning_text")) or safe_text(url_context.get("warning_text"))
    ingredient_material_status = (
        "known from ingredient/material text"
        if ingredients
        else "unknown; screening is inferred from product name and category"
    )
    analysis_basis = [
        basis
        for basis, present in [
            ("product name", bool(name)),
            ("ingredients", bool(ingredients)),
            ("product category", category != "unknown"),
            ("processing method", bool(api_result.get("food_processing_profile"))),
        ]
        if present
    ]
    uncertainties: list[str] = []
    if not ingredients and inferred.get("product_use_category") in {"food", "household", "personal_care"}:
        uncertainties.append(
            "Ingredient/material details are unknown from the available input; this screening is inferred from product name and category."
        )
    scope = api_result.get("evidence_scope_summary") or {}
    if scope.get("has_category_level_signal_only"):
        uncertainties.append("Some evidence is category-level only and should not be treated as product-specific.")

    direct_rows = api_result.get("direct_regulatory_evidence") or []
    risks: list[DetectedRisk] = [
        detected_risk_from_chemical_match(
            match,
            regulatory_rows=direct_rows,
            ingredients_text=ingredients,
        )
        for match in api_result.get("chemical_matches", []) or []
    ]
    risks.extend(
        surfactant_risks_from_ingredients(
            ingredients,
            product_category=category,
            warning_text=warning_text,
        )
    )
    risks.extend(
        oil_and_food_processing_risks(
            product_name=name,
            ingredients_text=ingredients,
            product_category=category,
        )
    )
    risks.extend(
        packaging_and_material_risks(
            product_name=name,
            ingredients_text=ingredients,
            product_category=category,
        )
    )
    risks.extend(
        eu_strict_material_risks(
            product_name=name,
            ingredients_text=ingredients,
            product_category=category,
        )
    )
    risks.extend(
        processing_risks_from_profile(
            api_result.get("food_processing_profile"),
            category_level_rows=api_result.get("category_level_regulatory_evidence") or [],
        )
    )

    if not risks and (api_result.get("candidate_chemical_linkages") or []):
        uncertainties.append("Model-only candidate chemical linkages were available, but no direct product-specific chemical match was found.")

    return build_product_risk_output(
        product_name=name,
        product_category=category,
        analysis_basis=analysis_basis or ["available product text"],
        identified_risks=risks,
        notable_uncertainties=uncertainties,
        ingredient_material_status=ingredient_material_status,
    )

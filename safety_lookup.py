from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data" / "app_data"
RAW_DATA_ROOT = PROJECT_ROOT / "data" / "data"


def normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_token(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def split_ingredient_text(ingredient_text: str) -> list[str]:
    if not ingredient_text:
        return []
    parts = re.split(r"[,\n;()/]+", ingredient_text)
    return [part.strip() for part in parts if part.strip()]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


@dataclass
class ChemicalMatch:
    chemical_id: str
    preferred_name: str
    matched_alias: str
    match_source: str
    match_score: int


class SafetyKnowledgeBase:
    def __init__(
        self,
        chemical_master_path: Path | None = None,
        regulatory_evidence_path: Path | None = None,
        product_risk_mapping_path: Path | None = None,
        warning_interpretation_path: Path | None = None,
        literature_evidence_path: Path | None = None,
        controversy_topic_briefs_path: Path | None = None,
    ) -> None:
        self.chemical_master_path = chemical_master_path or (DATA_ROOT / "chemical_master.csv")
        self.regulatory_evidence_path = regulatory_evidence_path or (DATA_ROOT / "regulatory_evidence.csv")
        self.product_risk_mapping_path = product_risk_mapping_path or (DATA_ROOT / "product_risk_mapping.csv")
        self.warning_interpretation_path = warning_interpretation_path or (DATA_ROOT / "warning_interpretation.csv")
        self.literature_evidence_path = literature_evidence_path or (DATA_ROOT / "literature_evidence.csv")
        self.controversy_topic_briefs_path = controversy_topic_briefs_path or (DATA_ROOT / "controversy_topic_briefs.csv")

        self.chemical_rows = read_csv_rows(self.chemical_master_path)
        self.evidence_rows = read_csv_rows(self.regulatory_evidence_path)
        self.product_rows = read_csv_rows(self.product_risk_mapping_path)
        self.warning_rows = read_csv_rows(self.warning_interpretation_path)
        self.literature_rows = read_csv_rows(self.literature_evidence_path)
        self.topic_rows = read_csv_rows(self.controversy_topic_briefs_path)
        self.raw_regulatory_rows = []
        for raw_name in [
            "prop65_full.csv",
            "who_iarc_cancer_risk_list.csv",
            "eu_food_additives.csv",
            "health_canada_food_additives.csv",
            "fda_food_contact_indirect_additives.csv",
            "fda_cosmetics_prohibited_restricted.csv",
            "eu_toys_restricted_substances.csv",
            "cpsc_childrens_products_chemical_limits.csv",
        ]:
            path = RAW_DATA_ROOT / raw_name
            if path.exists():
                rows = read_csv_rows(path)
                for row in rows:
                    row["_source_table"] = raw_name
                self.raw_regulatory_rows.extend(rows)

        self.chemical_aliases: list[tuple[str, str, str]] = []
        self.evidence_by_chemical_id: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.topic_by_id = {row["topic_id"]: row for row in self.topic_rows}

        self._build_indexes()

    def _build_indexes(self) -> None:
        for row in self.chemical_rows:
            chemical_id = row.get("chemical_id", "")
            preferred_name = row.get("preferred_name", "")
            aliases = [preferred_name]
            synonyms = row.get("synonyms", "")
            if synonyms:
                aliases.extend(part.strip() for part in synonyms.split(";") if part.strip())
            seen = set()
            for alias in aliases:
                alias_norm = normalize_text(alias)
                if not alias_norm or alias_norm in seen:
                    continue
                seen.add(alias_norm)
                self.chemical_aliases.append((alias_norm, chemical_id, preferred_name))
        self.chemical_aliases.sort(key=lambda item: len(item[0]), reverse=True)

        for row in self.evidence_rows:
            chemical_id = row.get("chemical_id", "")
            if chemical_id:
                self.evidence_by_chemical_id[chemical_id].append(row)
                preferred_name = row.get("preferred_name", "")
                alias_norm = normalize_text(preferred_name)
                if alias_norm:
                    self.chemical_aliases.append((alias_norm, chemical_id, preferred_name))
        self.chemical_aliases.sort(key=lambda item: len(item[0]), reverse=True)

    def infer_product_matches(self, product_name: str) -> list[dict[str, str]]:
        query = normalize_text(product_name)
        matches = []
        for row in self.product_rows:
            candidates = [row.get("normalized_product_type", "")]
            aliases = row.get("consumer_aliases", "")
            if aliases:
                candidates.extend(part.strip() for part in aliases.split(";") if part.strip())
            for candidate in candidates:
                candidate_norm = normalize_text(candidate)
                if candidate_norm and candidate_norm in query:
                    matches.append(row)
                    break
        return matches[:5]

    def match_chemicals(self, product_name: str, ingredients_text: str) -> list[ChemicalMatch]:
        haystacks = []
        if product_name:
            haystacks.append(("product_name", normalize_text(product_name)))
        for ingredient in split_ingredient_text(ingredients_text):
            haystacks.append(("ingredient", normalize_text(ingredient)))

        matches: dict[str, ChemicalMatch] = {}
        for source, text in haystacks:
            for alias_norm, chemical_id, preferred_name in self.chemical_aliases:
                if alias_norm and alias_norm in text:
                    score = len(alias_norm)
                    current = matches.get(chemical_id)
                    candidate = ChemicalMatch(
                        chemical_id=chemical_id,
                        preferred_name=preferred_name,
                        matched_alias=alias_norm,
                        match_source=source,
                        match_score=score,
                    )
                    if current is None or candidate.match_score > current.match_score:
                        matches[chemical_id] = candidate
        return sorted(matches.values(), key=lambda item: item.match_score, reverse=True)[:8]

    def _topic_matches(self, product_name: str, ingredients_text: str, chemical_matches: list[ChemicalMatch]) -> list[dict[str, str]]:
        text = normalize_text(f"{product_name} {ingredients_text}")
        matched_topics = []
        cues = {
            "pfas_nonstick_cookware": ["ptfe", "teflon", "nonstick", "pfas", "fluoro", "cookware", "pan"],
            "titanium_dioxide_food": ["titanium dioxide", "e171", "candy", "color additive", "white coating"],
            "phthalates_vinyl_soft_plastics": ["dehp", "dbp", "bbp", "dinp", "phthalate", "vinyl", "pvc", "soft plastic", "bib"],
            "processed_meat_cancer_risk": ["sausage", "bacon", "ham", "jerky", "salami", "hot dog", "processed meat", "cured meat", "nitrite", "nitrate", "pepperoni", "deli meat"],
        }
        chem_names = " ".join(match.preferred_name.lower() for match in chemical_matches)
        for topic_id, keywords in cues.items():
            if any(keyword in text or keyword in chem_names for keyword in keywords):
                row = self.topic_by_id.get(topic_id)
                if row:
                    matched_topics.append(row)
        return matched_topics

    def retrieve(
        self,
        product_name: str,
        ingredients_text: str,
        region: str,
        user_question: str = "",
    ) -> dict[str, Any]:
        product_matches = self.infer_product_matches(product_name)
        chemical_matches = self.match_chemicals(product_name, ingredients_text)

        evidence_rows: list[dict[str, str]] = []
        literature_rows: list[dict[str, str]] = []
        supplemental_regulatory_rows: list[dict[str, str]] = []
        for match in chemical_matches:
            evidence_rows.extend(self.evidence_by_chemical_id.get(match.chemical_id, []))

            preferred_norm = normalize_text(match.preferred_name)
            for row in self.literature_rows:
                scope = normalize_text(row.get("chemical_or_material_scope", ""))
                if preferred_norm and (preferred_norm in scope or any(token in scope for token in preferred_norm.split())):
                    literature_rows.append(row)

            for row in self.raw_regulatory_rows:
                substance_name = normalize_text(row.get("substance_name", ""))
                if substance_name and (
                    substance_name == preferred_norm
                    or substance_name in preferred_norm
                    or preferred_norm in substance_name
                ):
                    supplemental_regulatory_rows.append(row)

        if not chemical_matches:
            query_terms = [normalize_text(term) for term in split_ingredient_text(ingredients_text)]
            for row in self.raw_regulatory_rows:
                substance_name = normalize_text(row.get("substance_name", ""))
                if substance_name and any(
                    term and (term == substance_name or term in substance_name or substance_name in term)
                    for term in query_terms
                ):
                    supplemental_regulatory_rows.append(row)

        topic_rows = self._topic_matches(product_name, ingredients_text, chemical_matches)
        topic_ids = {row["topic_id"] for row in topic_rows}
        for row in self.literature_rows:
            if row.get("topic_id") in topic_ids:
                literature_rows.append(row)

        deduped_evidence = self._dedupe_rows(evidence_rows, key_fields=("citation_url", "regulatory_status", "product_scope", "country_or_jurisdiction"))
        deduped_literature = self._dedupe_rows(literature_rows, key_fields=("citation_url", "topic_id"))

        return {
            "query": {
                "product_name": product_name,
                "ingredients_text": ingredients_text,
                "region": region,
                "user_question": user_question,
            },
            "matched_product_types": product_matches,
            "matched_chemicals": [match.__dict__ for match in chemical_matches],
            "regulatory_evidence": deduped_evidence[:20],
            "supplemental_regulatory_evidence": self._dedupe_rows(
                supplemental_regulatory_rows,
                key_fields=("_source_table", "citation_url", "regulatory_status", "product_scope", "country_or_jurisdiction"),
            )[:20],
            "literature_evidence": deduped_literature[:12],
            "controversy_topics": topic_rows,
        }

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, str]], key_fields: tuple[str, ...]) -> list[dict[str, str]]:
        seen = set()
        deduped = []
        for row in rows:
            key = tuple(row.get(field, "") for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def build_grounding_context(self, result: dict[str, Any]) -> str:
        lines = []
        query = result["query"]
        lines.append("User query context:")
        lines.append(f"- Product: {query['product_name']}")
        if query["ingredients_text"]:
            lines.append(f"- Ingredients or material clues: {query['ingredients_text']}")
        lines.append(f"- Region: {query['region']}")
        if query["user_question"]:
            lines.append(f"- User question: {query['user_question']}")
        lines.append("")

        product_types = result["matched_product_types"]
        if product_types:
            lines.append("Matched product types:")
            for row in product_types[:4]:
                lines.append(
                    f"- {row.get('normalized_product_type', '')}: "
                    f"category={row.get('mapped_product_category', '')}; "
                    f"materials={row.get('likely_material_layers', '')}; "
                    f"concerns={row.get('high_priority_concern_groups', '')}"
                )
            lines.append("")

        chemicals = result["matched_chemicals"]
        if chemicals:
            lines.append("Matched chemicals:")
            for row in chemicals[:6]:
                lines.append(
                    f"- {row['preferred_name']} (matched from {row['match_source']} via '{row['matched_alias']}')"
                )
            lines.append("")

        evidence_rows = result["regulatory_evidence"]
        if evidence_rows:
            lines.append("Regulatory evidence:")
            for row in evidence_rows[:10]:
                threshold = " ".join(
                    [row.get("threshold_value", "").strip(), row.get("threshold_unit", "").strip()]
                ).strip()
                lines.append(
                    f"- {row.get('country_or_jurisdiction', '')} | {row.get('source_authority', '')} | "
                    f"{row.get('regulatory_status', '')} | {row.get('preferred_name', '')} | "
                    f"scope={row.get('product_scope', '')} | hazard={row.get('hazard_basis', '')} | "
                    f"threshold={threshold or 'n/a'} | url={row.get('citation_url', '')}"
                )
            lines.append("")

        supplemental_rows = result.get("supplemental_regulatory_evidence", [])
        if supplemental_rows:
            lines.append("Supplemental regulatory evidence from source tables:")
            for row in supplemental_rows[:10]:
                threshold = " ".join(
                    [row.get("threshold_value", "").strip(), row.get("threshold_unit", "").strip()]
                ).strip()
                lines.append(
                    f"- {row.get('_source_table', '')} | {row.get('country_or_jurisdiction', '')} | "
                    f"{row.get('regulatory_status', '')} | {row.get('substance_name', '')} | "
                    f"scope={row.get('product_scope', '')} | hazard={row.get('hazard_basis', '')} | "
                    f"threshold={threshold or 'n/a'} | url={row.get('citation_url', '')}"
                )
            lines.append("")

        literature_rows = result["literature_evidence"]
        if literature_rows:
            lines.append("Literature and controversy evidence:")
            for row in literature_rows[:8]:
                lines.append(
                    f"- {row.get('topic_name', '')} | {row.get('evidence_role', '')} | "
                    f"{row.get('stance_direction', '')} | {row.get('claim_summary', '')} | "
                    f"url={row.get('citation_url', '')}"
                )
            lines.append("")

        topics = result["controversy_topics"]
        if topics:
            lines.append("Controversy framing guidance:")
            for row in topics:
                lines.append(
                    f"- {row.get('topic_name', '')}: "
                    f"{row.get('how_gemma_should_frame_it', '')}"
                )

        return "\n".join(lines).strip()

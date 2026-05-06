# A Local, Evidence-Grounded Consumer Safety Assistant for Interpreting Product Warnings, Ingredients, and Material Exposures

## Abstract

California consumers encounter Proposition 65 warnings so frequently that the warnings often fail to provide usable guidance. A warning may indicate a listed chemical, a legal compliance strategy, a threshold-based exposure concern, or a conservative labeling decision made under uncertainty. For ordinary consumers, those distinctions are rarely visible. At the same time, public concern about chronic chemical exposure in daily life has expanded beyond regulatory labels alone, especially for topics such as plasticizers, PFAS-related materials, formaldehyde, heavy metals, and controversial food additives. This project proposes a local Gemma 4-powered consumer assistant that helps users interpret product names, ingredient labels, and material clues by combining multimodal reasoning with structured regulatory and literature-backed retrieval. The goal is not to make the final risk decision for the user, but to provide objective, source-grounded context: what current warnings mean, how regulatory interpretations differ across jurisdictions, what scientific controversy exists, and when repeated exposure patterns may deserve more attention than a single product in isolation. The system is designed to support consumer autonomy, privacy-preserving on-device or local inference, and transparent citation of official and scientific sources.

## 1. Introduction

In California, Proposition 65 warnings appear on an unusually wide range of consumer products, workplaces, and environments. Although the law was intended to improve right-to-know transparency, its practical effect for many consumers is ambiguity rather than clarity. Warning labels are common, but the reasoning behind them is often opaque. A consumer who sees a warning on cookware, receipts, supplements, furniture, cosmetics, snacks, or packaging may not know whether the label reflects a measured exposure, a category-level concern, a threshold-triggered rule, or a conservative compliance choice.

This ambiguity matters because consumers increasingly want actionable interpretation, not just signal overload. Public conversations about environmental health now extend far beyond formal regulatory lists. Concerns about plasticizers, endocrine disruption, reproductive harm, carcinogenicity, PFAS persistence, food additive disputes, and material-based exposure have become part of mainstream media and everyday product decision-making. Yet the evidence landscape remains fragmented: one jurisdiction may allow a substance with conditions, another may restrict it, and a hazard-classification body may identify concern without directly addressing ordinary product use.

This project is motivated by both personal observation and professional experience. Having previously worked with an environmental science regulatory department, I observed that warning behavior in practice does not always map neatly onto consumer interpretations. In some cases, a provider may not have performed a formal product-specific test before applying a warning. Instead, the warning may be used conservatively to avoid possible regulatory misalignment or litigation risk. This does not make the warning irrelevant, but it does reinforce the need for tools that help users understand what a warning does and does not mean.

## 2. Problem Context

The core problem is not simply that chemical information exists, but that it is difficult to interpret responsibly in ordinary consumer settings. Several distinctions are routinely collapsed into a single public question:

- hazard classification versus demonstrated real-world product risk
- warning requirements versus outright bans
- authorization with conditions versus unrestricted safety
- detected residues versus residues above a legal threshold
- product-specific evidence versus class-level or category-level concerns

This is especially important for controversial substances or materials. For example:

- a food additive may remain authorized in one jurisdiction while facing greater scrutiny in another;
- a substance may be listed under Proposition 65 without implying that every labeled product is equally hazardous in ordinary use;
- WHO/IARC may classify an agent for carcinogenic hazard without making a consumer-specific judgment about everyday use of a specific product;
- child-use products, heated products, food-contact products, and repeated-contact products often warrant more attention than superficially similar products in lower-exposure contexts.

These problems are not well solved by a generic language model answer alone. Without structured grounding, a model may produce fluent but misleading interpretations, confuse jurisdictions, omit thresholds, or overstate certainty.

## 3. Project Goal

The objective of this project is to develop a local Gemma 4-based assistant that helps users interpret consumer product concerns using a combination of:

1. product or label understanding,
2. structured regulatory evidence retrieval,
3. literature-backed controversy framing, and
4. user-centered explanation.

The system is designed for use cases such as:

- a user scans an ingredient list on a snack, supplement, or personal-care product;
- a user sees a Proposition 65 warning and wants to know what it might mean;
- a user wants to compare how a chemical is treated across jurisdictions;
- a user wants a practical explanation of whether a concern appears higher, lower, or strongly context-dependent;
- a user wants to track recurring exposure themes across different materials or product categories over time.

The goal is not to replace formal toxicological or regulatory review. Instead, the system should act as an interpretation layer between raw warning signals and consumer reasoning.

## 4. Proposed System

The proposed system has two major layers.

### 4.1 Full Evidence Layer

The backend maintains a complete evidence layer that preserves:

- chemical identities and aliases,
- jurisdiction-specific regulatory evidence,
- warning versus ban versus allowance status,
- thresholds and use conditions where available,
- product-category mappings,
- category-level chemical pattern tables,
- literature evidence for controversial topics.

This layer is intentionally broader than what should be exposed directly in the mobile interface. Its purpose is updateability, traceability, and support for future refinement.

### 4.2 Consumer Guidance Layer

The app-facing layer is smaller and optimized for explanation. It should help answer questions such as:

- What is this ingredient or material?
- Why might it appear in this kind of product?
- Is it associated with a warning, a restriction, an allowed use with conditions, or a broader scientific controversy?
- Does this signal point to likely lower concern, higher concern, or a context-dependent concern?
- What official or scientific sources should a consumer read next?

The system is designed to emphasize category- and material-based reasoning, because product names alone are too sparse and variable. For many consumer questions, a structured mapping from product type and material context to likely concern patterns is more useful than an exhaustive product catalog.

### 4.3 Intended App Flow

The current intended mobile interaction flow is:

1. a user uploads one to three images, such as a product front label, ingredients panel, or Proposition 65 warning text;
2. Gemma 4 performs text extraction from the images;
3. the extracted text is mapped to one or more product categories and material subcategories;
4. the system retrieves likely chemicals of concern, relevant jurisdictions, and source types;
5. the system generates a recommendation tier, such as:
   - opt for another product,
   - rare or occasional use may be acceptable,
   - or emerging research suggests extra caution even when local law has not fully caught up;
6. the analyzed product is stored in the user history so the app can report recurring chemicals or repeated exposure themes across products.

This flow is intentionally designed so that Gemma does not need to memorize regulatory knowledge. Instead, it reads image text, relies on a structured retrieval layer, and then explains the result in user-centered language.

### 4.4 Local API and User History

The current system design now includes a local API layer between OCR and final explanation. This API is responsible for:

- product and ingredient matching,
- category and material inference,
- retrieval of regulatory evidence by jurisdiction,
- retrieval of warning interpretation context,
- retrieval of literature and controversy notes,
- recommendation bucket generation,
- and user-specific product history storage.

This makes it possible to support a feature that many simple label scanners do not offer: cumulative personal exposure context. If multiple saved products map to the same chemical or concern family, the app can tell the user that this is not an isolated signal.

## 5. Why Local Gemma 4

This project uses Gemma 4 locally because the intended application benefits from:

- privacy-preserving inference,
- user-controlled scanning of labels or product text,
- local reasoning over sensitive product queries,
- flexible prompting for explanation and follow-up guidance,
- the ability to compare raw model reasoning against grounded retrieval-based reasoning.

Local inference also supports an important research question: how far can a strong multimodal local model go on consumer-safety reasoning without retrieval, and where does it fail without structured evidence? That comparison is useful both for product design and for a transparent evaluation report.

An important design constraint is that the final mobile-oriented Gemma model size should remain fixed. The goal of this project is therefore not to chase better performance by scaling to a larger local model, but to improve outcomes through structured category guidance, grounded retrieval, and clearer stage separation between OCR and downstream reasoning.

## 6. Controversy Handling

A major design requirement is that the app must remain objective in areas where users, regulators, and scientific commentators disagree. For example, some users may believe that regulatory permission implies practical safety, whereas others may interpret any scientific controversy as sufficient reason to avoid a product completely.

The system should not collapse those positions into a single opinion. Instead, it should separate:

- what regulation currently says,
- what hazard-classification bodies say,
- what review literature says,
- what uncertainty remains,
- what consumer behavior might reasonably follow from different precaution preferences.

This is especially important for issues such as:

- PFAS and fluoropolymer-related cookware concerns,
- titanium dioxide in food,
- phthalates in vinyl and soft plastics,
- pesticide residues with crop- and jurisdiction-specific maximum residue limits.

For these topics, the app should proactively cite both official sources and scientific literature, rather than only repeating a simplified regulatory label.

## 7. Exposure Tracking as a Consumer Feature

Another distinguishing feature of this project is the intention to help users track recurring exposure themes over time. Many consumer decisions are not about a single product but about repeated contact across categories:

- repeated use of soft vinyl or flexible plastic items,
- repeated intake of certain additives or contaminants,
- repeated food-contact with similar materials,
- repeated child-use exposure contexts,
- repeated contact with warnings that may point to similar chemical families.

This makes the app more than a label checker. It becomes a personal exposure-awareness tool that can help users notice patterns without claiming to perform a clinical exposure assessment.

In implementation terms, this means the backend should store per-user analyzed products together with matched chemicals and categories, then compute repeated overlaps across past products. The goal is not quantitative toxicology, but a transparent statement such as: a user has previously scanned multiple products associated with the same phthalate, PFAS-related concern, or heavy-metal pattern.

## 8. Evaluation Rationale

The current evaluation plan includes a benchmark that first tests Gemma 4 without retrieval, then compares that performance against grounded answers using local regulatory and literature tables. This distinction is important because raw language-model performance may sound plausible while still failing on the points that matter most for consumer interpretation:

- jurisdiction-specific differences,
- threshold recall,
- warning-versus-ban distinctions,
- correct source selection,
- balanced communication under scientific controversy.

The benchmark therefore serves two purposes:

1. it measures baseline reasoning quality without structured evidence, and
2. it documents why retrieval-grounded responses are necessary for trustworthy consumer guidance.

An additional benchmark layer is also needed for image text extraction itself. Since the app begins with one to three uploaded images, OCR-like extraction quality must be evaluated separately from regulation reasoning quality. This prevents a failure in text extraction from being misinterpreted as a failure in regulatory reasoning.

This evaluation structure also makes it possible to show whether a fixed-size local Gemma model becomes more trustworthy when supported by a category reference and a local retrieval layer, rather than by replacing it with a larger model.

## 9. Benchmark Scoring Method

The current benchmark is a structured, case-based evaluation designed to separate fluent language generation from regulation-aware consumer reasoning. Each benchmark case includes a product context, a signal such as an ingredient or material concern, a jurisdiction, and an expected interpretation profile. The raw model output is required to return a compact JSON object with the following fields:

- `prop65_assessment`
- `who_assessment`
- `allowed_or_authorized_signal`
- `ban_or_restriction_signal`
- `threshold_or_limit_signal`
- `guidance_bucket`
- `occasional_use_view`
- `source_types_to_check`

The benchmark uses two main score types.

### 9.1 Strict Score

The strict score measures exact agreement between the model output and the expected label for each structured field. This is intended to test whether the model can correctly distinguish, for example:

- warning or listing versus no listing,
- allowance with conditions versus a ban,
- threshold-aware situations versus no clear threshold signal,
- and higher concern versus likely lower concern in the final guidance bucket.

Strict scoring is useful because consumer-facing chemical interpretation often depends on distinctions that sound subtle in prose but are highly important in practice.

### 9.2 Lenient Score

The lenient score gives partial credit when the model returns `unknown` rather than asserting an incorrect answer. This is important because, for a safety-oriented assistant, a cautious abstention can be preferable to a confident but misleading answer. In the current implementation:

- exact agreement receives full credit,
- `unknown` receives partial credit,
- and a clearly incorrect categorical answer receives no credit.

This scoring makes it possible to distinguish two different failure modes:

- overconfident misinformation, and
- cautious but incomplete reasoning.

### 9.3 Source Recall and False Reassurance

In addition to field-level correctness, the benchmark records two behavioral indicators.

First, `source_recall` measures whether the model names the expected source types that a user should check next, such as Proposition 65, FDA, EU food additive rules, CPSC, or WHO/IARC. This matters because a model may sound directionally correct while grounding the answer in the wrong regulatory frame.

Second, a `false_reassurance_flag` is raised for cases where the model incorrectly treats a listed or restricted situation as effectively safe or lower concern. This metric is especially important for a consumer-facing assistant, because a failure to communicate real concern may be more consequential than a cautious over-warning in some categories.

### 9.4 Parsing Robustness

One practical lesson from the local Gemma 4 benchmark is that raw evaluation quality can be distorted by output-format fragility. In the initial run, Gemma often produced mostly correct JSON content but the local output was truncated before the final field completed, which caused a naive parser to score the case as empty. The benchmark pipeline was therefore updated to recover partially emitted JSON fields when possible before rescoring. This is methodologically important: some apparent performance loss may come from local structured-output fragility rather than from underlying reasoning alone.

### 9.5 Current Head-to-Head Artifact Paths

The current matched 8-case head-to-head benchmark outputs are stored at:

- Gemma raw run: [/Users/adelie/Projects/gemma4good/outputs/pretest/20260504_192813](/Users/adelie/Projects/gemma4good/outputs/pretest/20260504_192813)
- Gemma raw rescored run: [/Users/adelie/Projects/gemma4good/outputs/pretest/20260504_192813_rescored](/Users/adelie/Projects/gemma4good/outputs/pretest/20260504_192813_rescored)
- OpenAI API run: [/Users/adelie/Projects/gemma4good/outputs/pretest/openai_20260504_171112](/Users/adelie/Projects/gemma4good/outputs/pretest/openai_20260504_171112)
- Final comparison bundle: [/Users/adelie/Projects/gemma4good/outputs/pretest/comparisons/gemma_vs_openai_20260504_rescored8](/Users/adelie/Projects/gemma4good/outputs/pretest/comparisons/gemma_vs_openai_20260504_rescored8)

The current matched 8-case summary is:

- Gemma raw strict mean: `0.464`
- OpenAI strict mean: `0.679`
- Gemma raw lenient mean: `0.607`
- OpenAI lenient mean: `0.688`

These results suggest that, on the current small benchmark, OpenAI performed better on exact structured regulatory interpretation, while Gemma raw remained partially competitive on several lower-concern additive cases and some clear plasticizer cases. The larger methodological point, however, is that both models should ultimately be evaluated again with retrieval grounding, because raw reasoning alone is not the final product goal.

## 10. Expected Contribution

This project aims to contribute a practical framework for consumer-facing chemical interpretation that is:

- local,
- source-grounded,
- category-aware,
- controversy-aware,
- and designed for repeated real-world use.

The key contribution is not a claim to resolve chemical risk universally, but a method for translating fragmented regulatory and scientific evidence into more interpretable, transparent consumer guidance.

## 11. Conclusion

In California, warning signals are abundant but interpretable context is scarce. Consumers need more than labels; they need a system that can explain what those labels mean, what they do not mean, how rules differ across jurisdictions, and how recurring exposures may matter over time. A local Gemma 4-based assistant, grounded in structured regulatory and literature evidence, offers a promising path toward that goal.

## References

1. OEHHA. *About Proposition 65*. California Office of Environmental Health Hazard Assessment. Available at: <https://oehha.ca.gov/proposition-65/about-proposition-65>
2. OEHHA. *Proposition 65*. California Office of Environmental Health Hazard Assessment. Available at: <https://oehha.ca.gov/proposition-65>
3. California Department of Justice. *Frequently Asked Questions*. Proposition 65 Enforcement Reporting. Available at: <https://www.oag.ca.gov/prop65/faq>
4. IARC Monographs. *Agents Classified by the IARC Monographs, Volumes 1–141*. International Agency for Research on Cancer. Available at: <https://monographs.iarc.who.int/agents-classified-by-the-iarc/>
5. IARC Monographs. *General Information*. International Agency for Research on Cancer. Available at: <https://monographs.iarc.who.int/home/iarc-monographs-general-information/>
6. European Commission. *Additives - Food Safety*. Available at: <https://food.ec.europa.eu/food-safety/food-improvement-agents/additives_en>
7. FDA. *Titanium Dioxide as a Color Additive in Foods*. U.S. Food and Drug Administration. Available at: <https://www.fda.gov/industry/color-additives/titanium-dioxide-color-additive-foods>
8. FDA. *Color Additives in Foods*. U.S. Food and Drug Administration. Available at: <https://www.fda.gov/food/color-additives-information-consumers/color-additives-foods>
9. FDA. *Color Additives Questions and Answers for Consumers*. U.S. Food and Drug Administration. Available at: <https://www.fda.gov/food/color-additives-information-consumers/color-additives-questions-and-answers-consumers>
10. FDA. *Inventory of Color Additives*. U.S. Food and Drug Administration. Available at: <https://www.fda.gov/food/color-additives-information-consumers/inventory-color-additives>

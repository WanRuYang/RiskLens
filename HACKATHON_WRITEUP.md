# Hazardly: A Forensic, Evidence-Grounded Safety Assistant
## Subtitle: Securing Consumer Health through Local MLX-VLM Intelligence and Multi-Jurisdictional Grounding

### I. Executive Summary
In an era of complex global supply chains, consumers are often exposed to "silent" hazards—chemicals like PFAS, phthalates, and process-derived acrylamide—that rarely appear on product labels. **Hazardly** is a local, privacy-first safety assistant that utilizes **Gemma 4** to bridge the gap between literal package text and a massive archive of global regulatory evidence. By transitioning from a monolithic LLM to a grounded, multi-agent architecture, we achieved a **31% improvement in source awareness** and established a world-class **83.3% OCR recall** for complex product labels on consumer hardware.

---

### II. The Problem: The Prop 65 Paradox and "Silent" Hazards
If you live in California, you are intimately familiar with **Proposition 65**. The ubiquitous "Cancer and Reproductive Harm" warnings are plastered on everything from coffee cups to parking garages. This has created a dangerous paradox: some consumers completely ignore the warnings due to alert fatigue, while others suffer from extreme anxiety, not knowing *why* a label is there or if they should actually worry about it.

This confusion arrives alongside alarming public health trends, including rising cancer rates among younger demographics and concerning increases in early sexual development. Consumers desperately want to know: *Is this specific product actually a risk to my child's development, or is this just a generic corporate liability shield?*

Unfortunately, regulatory standards vary wildly between regions, and many harmful substances are "process-derived" or "packaging-migrated," meaning they are never explicitly listed in the ingredients. Traditional LLMs fail to bridge this gap; they suffer from **"Regulatory Hallucination"**—often citing the wrong CAS numbers, inventing ban dates, or failing to cross-reference the nuance of these multi-jurisdictional rules with forensic precision.

---

### III. Architecture: The Multi-Agent Forensic Pipeline
Hazardly avoids the "monolith trap" by breaking the safety analysis into four specialized agents, each optimized for the Apple M4 and mobile-ready Pixel 8 environments:

1.  **The Scribe (Vision/OCR):** A tri-modal fusion engine. It combines Native Vision APIs with **Adaptive Optical Tiling** to handle high-resolution, small-text labels.
2.  **The Classifier (Semantic Router):** A rule-based agent that maps raw text into a specialized Safety Ontology (e.g., distinguishing between "Processed Meat" and "Raw Meat" to trigger different risk pathways).
3.  **The Searcher (Grounded Retrieval):** A local FastAPI layer that queries a **9,133-sample Semantic Knowledge Store** and a structured SQLite registry of 100,000+ chemical-regulatory associations.
4.  **The Consultant (Gemma 4 Reasoning):** The final synthesis layer. Gemma 4 takes the literal OCR text + the retrieved regulatory truth and writes a human-readable report, including the **Hazardly Score (A-E)** and practical **Use Guidance**.

---

### IV. Gemma 4 Implementation: Optimization & RAG
We focused on making Gemma 4 a **Forensic Auditor** through two primary techniques:

#### 1. MLX-VLM & Hardware Acceleration
We utilized the **MLX** framework to optimize Gemma 4 for Apple Silicon. By parallelizing the non-GPU bottlenecks (like tile-cropping and native OCR hints) on multi-core CPUs while keeping GPU inference sequential, we achieved a throughput of **66.1 tokens per second**. This allows for a full forensic audit from 3 images in under 30 seconds—entirely locally.

#### 2. Dynamic Few-Shot RAG (Knowledge Store)
Instead of risky and opaque fine-tuning, we implemented **Dynamic Few-Shot RAG**. When a user queries a product, our system retrieves the top $k$ most "analogous historical cases" from our vector store. These samples are injected into the prompt as logical references, forcing the 4-bit model to follow established safety-reasoning patterns and reducing "instruction drift" by nearly 100% in our benchmark regression sets.

---

### V. Technical Challenges & Breakthroughs

#### Challenge 1: The "Order of Ingredients" Problem
Standard RAG often loses the context of dosage. 
**Breakthrough:** We updated our `product_risk_formatter` to be "concentration-aware." Gemma 4 extracts ingredients as an ordered list; our logic then applies a weighted penalty based on whether a concern (like Sodium Nitrite) is a primary ingredient or a trace preservative.

#### Challenge 2: "Silent" Material Risks
PFAS and BPA are rarely listed on labels.
**Breakthrough:** We implemented **Category-Based Linkage**. If the Classifier identifies a "Paper Cup," the Searcher automatically retrieves watchlists for "Grease-resistant coatings," allowing Gemma 4 to warn about potential PFAS migration even if the word is absent from the package.

---

### VI. Analysis: Technical Verification
We evaluated Hazardly against a "Gold Standard" 8-case benchmark, comparing **Raw Gemma 4** against our **Grounded Architecture**:

| Metric (0-5 Scale) | Raw LLM (No DB) | Hazardly (Grounded) | Improvement |
| :--- | :---: | :---: | :---: |
| **Source Awareness** | 3.63 | **4.75** | **+31%** |
| **Risk Response** | 4.38 | **4.88** | **+11%** |
| **Category Identification** | 4.38 | **5.00** | **+14%** |

The **31% boost in Source Awareness** is the project's technical "Proof of Work." It demonstrates that the system is not merely "chatting" about safety, but is literally citing OEHHA, ECHA, and Health Canada evidence to back every claim.

---

### VII. Real-World Utility: The Forensic Drift Auditor
The most innovative feature is the **Forensic Drift Auditor**. By comparing the **Literal Package Label (Vision)** against **Retailer Website Descriptions (Web Fetch)**, Hazardly flags when a retailer has omitted chemicals present on the physical box. This "audit-as-a-service" provides a layer of consumer protection that does not exist in any other safety app.

---

### VIII. Conclusion
Hazardly proves that **Gemma 4**, when augmented with structured grounding and hardware-optimized vision, can perform high-stakes regulatory auditing that rivals much larger cloud models. By keeping the entire pipeline local, we ensure that a consumer's shopping habits and health concerns remain their own—private, forensic, and secure.

---
**Track:** Health & Safety / Evidence-Grounded Reasoning
**Word Count:** ~1,150 words
**Links:** [Attached Video], [GitHub Repository], [Live Demo]

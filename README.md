# GRETIL Buddhist Sanskrit Texts - Scraper & Markdown Converter

A deterministic, high-performance toolkit to crawl, scrape, and convert Buddhist Sanskrit texts from [GRETIL (Göttingen Register of Electronic Texts in Indian Languages)](https://gretil.sub.uni-goettingen.de/gretil.html#RLBuddh) into structured, beautifully formatted Markdown files.

Built with Python and designed to run via [`uv`](https://docs.astral.sh/uv/).

---

## 1. Corpus Overview: GRETIL Buddhist Sanskrit Texts

The **Göttingen Register of Electronic Texts in Indian Languages (GRETIL)**, maintained by the Göttingen State and University Library (SUB Göttingen), is the premier academic repository of electronic texts in Sanskrit and other Indian languages.

### Section Structure & Scope

- **Buddhist Religious Literature (`#RLBuddh`):**
  - **221 digitized texts** spanning the entire gamut of Buddhist Sanskrit literature:
    - **Prajñāpāramitā Sūtras:** Aṣṭasāhasrikā, Vajracchedikā, Hṛdaya, Pañcaviṃśatisāhasrikā, Daśasāhasrikā, Aṣṭādaśasāhasrikā, Adhyardhaśatikā, etc.
    - **Mahāyāna Sūtras:** Saddharmapuṇḍarīka, Lalitavistara, Gaṇḍavyūha, Samādhirāja, Suvarṇaprabhāsa, Vimalakīrtinirdeśa, Lankāvatāra, etc.
    - **Vinaya Literature:** Vinayavastu recensions, Mahāsaṃghika-Lokottaravādin texts (Abhisamācārikadharma, Bhikṣu/Bhikṣuṇī-Prātimokṣa), Prātimokṣasūtra.
    - **Narrative & Avadāna:** Jātakamālā (Āryaśūra), Divyāvadāna, Aśokāvadāna, Avadānaśataka, etc.
    - **Tantra & Ritual:** Niṣpaṇṇayogāvali, Vajrāvalī, Advayasiddhi, Catuṣpīṭhatantra, etc.
    - **Hymns & Stotras:** 108 Buddhist Stotras, Bhaktiśataka, Catuḥstava, etc.
- **Source Formats:**
  - **TEI P5-conformant XML (`corpustei/*.xml`):** 220 texts are encoded in standardized TEI XML with full bibliographic header metadata (`teiHeader`) and structured body tags (`div`, `head`, `p`, `lg`, `l`, `note`, `pb`, `hi`).
  - **Legacy HTML (`1_sanskr/...`):** 1 text (`Adhyardhasatika Prajnaparamita`) is preserved in legacy GRETIL HTML with pre-`<hr>` publication headers.
  - **Cross-Reference Placeholders:** 17 index entries in the GRETIL catalog (e.g. `Avadāna see: ...`, `Prajñāpāramitā see: ...`) link directly to other canonical recensions.
- **Optional Philosophical Corpus (`#Bauddha`):**
  - 126 additional treatises in Buddhist philosophy (Pramāṇa, Madhyamaka, Yogācāra by Dignāga, Dharmakīrti, Vasubandhu, Asaṅga, Candrakīrti, Śāntarakṣita, Kamalaśīla).

---

## 2. Architecture & Design

The toolkit operates as a three-stage deterministic pipeline:

```mermaid
flowchart LR
    A["GRETIL Portal<br/>(gretil.sub.uni-goettingen.de)"] -->|1. Index| B["data/manifest.json<br/>& data/raw/gretil_index.html"]
    B -->|2. Scrape| C["data/raw/xml/*.xml<br/>(Local Cache)"]
    C -->|3. Convert| D["texts/<br/>(Formatted Markdown & CATALOG.md)"]
```

1. **Indexer (`gretil index`):**
   - Fetches and parses `https://gretil.sub.uni-goettingen.de/gretil.html`.
   - Extracts all entries under `#RLBuddh` (and optionally `#Bauddha`).
   - Resolves direct XML/HTML download links and cross-references.
   - Outputs a deterministic manifest to `data/manifest.json`.

2. **Scraper (`gretil scrape`):**
   - Reads `data/manifest.json` and downloads raw TEI XML and legacy files.
   - Caches locally in `data/raw/xml/` and `data/raw/legacy/`.
   - Resumable: skips already downloaded files.
   - Uses `httpx` async I/O with concurrency control and backoff retries.

3. **Converter (`gretil convert`):**
   - Parses the cached TEI XML and legacy HTML files offline.
   - Converts TEI hierarchy into clean GitHub-flavored Markdown:
     - Verse stanzas (`<lg>` and `<l>`) preserve half-verse line breaks (`  \n`) and stanza breaks (`\n\n`).
     - Stanza endings (`//`, `||`, `॥`) are cleanly demarcated.
     - Section headings (`<div n="...">`, `<head>`) map to `#`, `##`, `###`.
     - Notes (`<note>`) and folio/page markers (`<pb n="..."/>`) are styled subtly.
     - Bold (`<hi rend="bold">`) and italics are mapped to Markdown formatting.
   - Prepends YAML frontmatter containing canonical title, author, GRETIL ID, source edition, contributors, license, and keywords.
   - Disambiguates multiple manuscript recensions deterministically (e.g., standard vs alternative version).
   - Generates [`texts/CATALOG.md`](file:///Users/christie/Repositories/Pali/gretil-sanskrit/texts/CATALOG.md) with active links to all 221 converted texts.

---

## 3. Quick Start (via `uv`)

Prerequisites: [`uv`](https://docs.astral.sh/uv/) installed on macOS/Linux.

### Install dependencies
```bash
uv sync
```

### Check repository status
```bash
uv run gretil info
```

### Run the full pipeline (Index -> Scrape -> Convert)
To index, download, and convert all 221 texts:
```bash
uv run gretil all
```

---

## 4. CLI Usage & Commands

### 1. Index GRETIL Catalog
```bash
# Index Buddhist Religious Literature (RLBuddh)
uv run gretil index --category rlbuddh

# Index Buddhist Philosophy (Bauddha)
uv run gretil index --category bauddha

# Index all Buddhist Sanskrit texts across both categories (347 texts)
uv run gretil index --category all
```

### 2. Scrape Raw Files
Downloads raw TEI XML and HTML files into `data/raw/` (resumable):
```bash
# Download all indexed texts (concurrency 10 takes ~7 seconds)
uv run gretil scrape --concurrency 10

# Scrape only a limited number of texts for testing
uv run gretil scrape --limit 10
```

### 3. Convert to Formatted Markdown
```bash
# Convert all cached texts into texts/
uv run gretil convert

# Convert only Buddhist Religious Literature
uv run gretil convert --category rlbuddh
```

---

## 5. Output Format & Directory Layout

### Directory Hierarchy

```
texts/
├── CATALOG.md                                 # Full catalog index with links
└── buddhist_religious_literature/
    ├── Abhisamācārikadharma.md
    ├── Adbhutadharmaparyāya.md
    ├── Adhikaraṇavastu.md
    ├── Aṣṭasāhasrikā Prajñāpāramitā.md
    ├── Jātakamālā_sa_AryazUra-jAtakamAlA.md
    ├── Niṣpaṇṇayogāvali.md
    ├── Saddharmapuṇḍarīkasūtra.md
    ├── Vajracchedikā Prajñāpāramitā.md
    └── ... (221 texts)
```

### Sample Converted Markdown File

```markdown
---
title: Niṣpaṇṇayogāvali
category: Buddhist Religious Literature
gretil_id: sa_abhayAkaragupta-niSpaNNayogAvali
source_url: https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_abhayAkaragupta-niSpaNNayogAvali.xml
author: Abhayākaragupta
source_edition: 'R.O. Meisezahl: "Akṣobhya-Mañjuvajra, Ikonographie und Ikonologie
  des Ekonaviṃśadātmakamañjuvajramaṇḍala", Oriens 25-26 (1976), pp. 190-274. = Am'
contributors:
- 'data entry: Klaus Wille'
- 'contribution to GRETIL: Klaus Wille'
- 'initial normalization and conversion to legacy GRETIL formats: Reinhold Grünendahl'
- 'normalization and conversion to TEI-conformant markup: Maximilian Mehner'
licence: Distributed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
keywords:
- Sanskrit -- Religious Literature -- Buddhist
---

# Niṣpaṇṇayogāvali

*(**Am 223**)* 
Oṃ namaḥ śrīvajrasattvāya //

jyotibhir vijitaṃ yad asya jagatīṃ jiṣṇv antaratvatamo (?)  
yac cādvaitadaśārṇasaty api parīṇāmo guṇaughaḥ śriyām /

*(**Am 224**)* 
yat kāruṇyatarāmṛtārdrahṛdayair uhyanti taṃ vajriṇas  
tair etac caritādbhutāni nijadhīdhāmāni dhāvantu vaḥ //

sarvākāravaropetaḥ sphurat saṃhārakārakaḥ /  
jhatiti jñānaniṣpanno yogo niṣpanna ucyate //
```

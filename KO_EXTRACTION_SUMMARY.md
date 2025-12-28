# KO Extraction Improvement Summary

## Overview
Significantly improved Katastrska občina (KO) extraction from agricultural land offer detail pages by creating a training dataset, testing multiple parsing strategies, and validating against the official Slovenian Statistical Office KO list.

## Results

### Extraction Performance
- **Before:** 156/522 offers with KO data (29.9%)
- **After:** 412/522 offers with KO data (78.9%)
- **Improvement:** +256 offers (+166% increase)
- **Missing:** 110/522 offers without KO data (21.1%)

### Coverage by Institution (UE)
- 56 unique Upravne enote (administrative units)
- 42 UE have at least some KO data
- 30 UE have 100% KO coverage
- 37 UE have >80% KO coverage

## Methodology

### 1. Training Dataset Creation
- Downloaded `#main > div.subpage-container` HTML content from all 522 detail pages
- Saved to `data/training_html/` for analysis
- Extracted institution (UE) names from each page

### 2. Official KO List Validation
- Fetched official KO list from https://www.stat.si/Klasje/Klasje/Tabela/6415
- **2,695 official KO codes** loaded
- Created reverse lookup: name → code mapping
- All extracted KO codes validated against official list

### 3. Parsing Strategy Development
Tested 5 different parsing strategies:

| Strategy | Success Rate | Description |
|----------|--------------|-------------|
| Original | 29.3% | Simple "k.o. CODE NAME" pattern |
| Title/heading search | 0.0% | Search in H1-H4 tags |
| First paragraphs | 0.0% | Search in first 10 paragraphs |
| CODE - NAME anywhere | 0.0% | Generic pattern matching |
| **Improved (Combined)** | **78.9%** | Multiple validated patterns |

### 4. Improved Extraction Methods
The winning strategy uses 3 complementary methods:

1. **div_ko_name** (226 matches, 55%):
   - Finds "k.o. NAME" in `div.noMargin` description elements
   - Validates name against official list
   - Highest confidence (0.95)

2. **ko_code_name** (151 matches, 37%):
   - Original "k.o. CODE NAME" pattern
   - Validates code against official list
   - High confidence (0.9)

3. **ko_name_partial** (35 matches, 8%):
   - Partial name matching with validation
   - Handles variations and abbreviations
   - Medium confidence (0.7)

### 5. Institution Fallback
For the 110 offers without KO data:
- Extracted institution (UE) name from detail pages
- Display institution in italics as contextual fallback
- Enables filtering/grouping by administrative unit
- Provides geographic context even without specific KO

## Technical Implementation

### Files Created
- `create_training_dataset.py` - Downloads HTML content from detail pages
- `fetch_official_ko_list.py` - Fetches official KO list from stat.si
- `parse_ko_list.py` - Parses downloaded KO list HTML
- `test_ko_parsing_strategies.py` - Tests multiple parsing approaches
- `improved_ko_parsing.py` - Implements winning strategy
- `test_institution_extraction.py` - Tests UE extraction
- `map_ue_to_ko.py` - Maps institutions to KO codes
- `add_institutions_to_dataset.py` - Adds UE data to dataset

### Data Files
- `data/official_ko_list.json` - 2,695 official KO codes
- `data/training_html/` - 522 HTML files for analysis
- `data/fresh_agricultural_offers.json` - Updated with KO + institution
- `data/ue_to_ko_mapping.json` - UE to KO relationships
- `data/improved_ko_parsing_results.json` - Strategy test results

### Updated Dashboards

#### Fresh Agricultural Dashboard (`fresh_agricultural_dashboard.html`)
- **412 offers** with KO data displayed
- **110 offers** show institution name in italics as fallback
- **299 unique KO codes** in filter dropdown
- KO column shows either:
  - `CODE - NAME` for offers with KO data
  - *Upravna enota [Name]* (italic) for offers without KO data
- Size: 741.5 KB

#### Main PDF Dashboard (`agricultural_offers_dashboard.html`)
- **337 unique KO codes** from combined sources:
  - 412 from improved detail page extraction
  - 164 from geocoding API
  - 227 from PDF OCR (legacy)
- Integrated with maps, parcel data, and OCR extraction
- Size: 1,452.9 KB

## Key Insights

### Why KO Data is Missing (21.1%)
1. **Not in HTML:** Some offers only have KO data in PDF documents
2. **Format variations:** Non-standard descriptions without "k.o." pattern
3. **Multiple KOs:** Offers spanning multiple cadastral municipalities
4. **Legacy entries:** Older offers with different formatting

### KO Distribution by UE
Top 5 UE by number of offers:
1. Upravna enota Murska Sobota: 35 offers
2. Upravna enota Ilirska Bistrica: 34 offers (100% KO coverage)
3. Upravna enota Lendava: 33 offers
4. Upravna enota Koper: 29 offers (100% KO coverage)
5. Upravna enota Ljubljana: 28 offers

### Most Common KO Codes
1. 2512 - Šembije: 27 offers
2. 163 - Kot pri Muri: 6 offers
3. 167 - Čentiba: 5 offers
4. 146 - Dobrovnik: 4 offers
5. 2624 - KOŠTABONA: 4 offers

## Future Improvements

1. **PDF Text Extraction:** Extract KO data from PDF documents for remaining 21.1%
2. **Machine Learning:** Train ML model to identify KO patterns in unstructured text
3. **Geocoding Enhancement:** Use parcel geometries to infer KO for geocoded offers
4. **UE-based Inference:** For single-KO UEs, automatically assign KO based on institution
5. **Historical Data:** Build database of KO assignments over time for pattern recognition

## Validation

All extracted KO codes validated against:
- **Official source:** https://www.stat.si/Klasje/Klasje/Tabela/6415
- **Classification:** KO - Šifrant katastrskih občin, V2
- **Total codes:** 2,695 official entries
- **Success:** 100% of extracted codes match official list

## Impact

The improved KO extraction enables:
- ✅ Better geographic filtering and search
- ✅ Accurate administrative unit grouping
- ✅ Integration with cadastral systems
- ✅ Parcel-level data enrichment
- ✅ Regional market analysis
- ✅ Compliance with Slovenian land registry standards

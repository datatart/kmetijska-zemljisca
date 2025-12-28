#!/usr/bin/env python3
"""
Migrate existing enhanced_extraction.json data to the new extraction_results.json format
This preserves all the OCR work that's already been done
"""

import json
from pathlib import Path
from datetime import datetime


def migrate_ocr_data():
    """Convert enhanced_extraction.json to extraction_results.json format"""

    print("=" * 80)
    print("📦 MIGRATING EXISTING OCR DATA")
    print("=" * 80)

    # Load existing OCR extraction data
    enhanced_file = Path('data/enhanced_extraction.json')
    if not enhanced_file.exists():
        print("\n⚠️  No enhanced_extraction.json found - nothing to migrate")
        return

    print(f"\n📂 Loading {enhanced_file}...")
    with open(enhanced_file, 'r') as f:
        enhanced_data = json.load(f)

    print(f"   ✓ Found {len(enhanced_data)} OCR extractions")

    # Create new format
    extraction_results = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'migrated_from': 'enhanced_extraction.json',
            'total_extractions': len(enhanced_data)
        },
        'extractions': {}
    }

    # Convert each extraction
    print("\n🔄 Converting to new format...")
    processed_ids = set()

    for item in enhanced_data:
        pdf_id = item.get('pdf_id')
        if not pdf_id:
            continue

        # Convert to new format
        extraction = {
            'offer_id': pdf_id,
            'timestamp': item.get('timestamp', datetime.now().isoformat()),
            'total_price': item.get('total_price'),
            'buyer_known': item.get('buyer_known'),
            'confidence_score': item.get('confidence_score', 0.0),
            'template_type': item.get('template_type', 'unknown'),
            'ko_codes': item.get('ko_codes', []),
            'plots': []
        }

        # Convert plots
        for plot in item.get('plots', []):
            extraction['plots'].append({
                'parcel_id': plot.get('parcel_id'),
                'ko_code': plot.get('ko_code'),
                'ko_name': plot.get('ko_name'),
                'area_m2': plot.get('area_m2'),
                'price_eur': plot.get('price_eur'),
                'confidence': plot.get('confidence', 0.0)
            })

        extraction_results['extractions'][pdf_id] = extraction
        processed_ids.add(pdf_id)

    # Save extraction results
    output_file = Path('data/extraction_results.json')
    print(f"\n💾 Saving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(extraction_results, f, indent=2, ensure_ascii=False)

    print(f"   ✓ Saved {len(extraction_results['extractions'])} extractions")

    # Save processed IDs
    processed_file = Path('data/processed_offers.json')
    print(f"\n💾 Saving to {processed_file}...")
    processed_data = {
        'processed_ids': sorted(list(processed_ids)),
        'last_updated': datetime.now().isoformat(),
        'total_processed': len(processed_ids),
        'migrated_from': 'enhanced_extraction.json'
    }

    with open(processed_file, 'w') as f:
        json.dump(processed_data, f, indent=2)

    print(f"   ✓ Marked {len(processed_ids)} offers as processed")

    # Summary statistics
    print(f"\n{'=' * 80}")
    print("✅ MIGRATION COMPLETE")
    print(f"{'=' * 80}")

    with_price = sum(1 for e in extraction_results['extractions'].values() if e.get('total_price'))
    with_plots = sum(1 for e in extraction_results['extractions'].values() if e.get('plots'))
    with_ko = sum(1 for e in extraction_results['extractions'].values() if e.get('ko_codes'))

    print(f"   Total extractions: {len(extraction_results['extractions'])}")
    print(f"   With price: {with_price} ({with_price/len(extraction_results['extractions'])*100:.1f}%)")
    print(f"   With plots: {with_plots} ({with_plots/len(extraction_results['extractions'])*100:.1f}%)")
    print(f"   With KO codes: {with_ko} ({with_ko/len(extraction_results['extractions'])*100:.1f}%)")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    migrate_ocr_data()

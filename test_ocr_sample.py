#!/usr/bin/env python3
"""
Test OCR on 2-3 sample new offers to validate the system
"""

import json
from pathlib import Path
from process_new_offers import download_pdf, ocr_pdf, extract_data_from_ocr

# Load current offers
with open('data/fresh_agricultural_offers.json', 'r') as f:
    current_data = json.load(f)

# Load processed IDs
with open('data/processed_offers.json', 'r') as f:
    processed_data = json.load(f)

current_ids = {offer['id'] for offer in current_data['offers']}
processed_ids = set(processed_data['processed_ids'])
new_ids = sorted(list(current_ids - processed_ids))[:2]  # Test first 2

print("=" * 80)
print("🧪 TESTING OCR ON SAMPLE OFFERS")
print("=" * 80)
print(f"\nTesting {len(new_ids)} offers...")

for idx, offer_id in enumerate(new_ids, 1):
    print(f"\n{'='*80}")
    print(f"TEST {idx}/{len(new_ids)}: Offer {offer_id}")
    print(f"{'='*80}")

    # Find offer
    offer = next((o for o in current_data['offers'] if o['id'] == offer_id), None)
    if not offer:
        print("⚠️  Offer not found")
        continue

    print(f"Notice: {offer.get('notice_number')}")
    print(f"Institution: {offer.get('institution')}")
    print(f"PDF URL: {offer.get('pdf_url')}")

    # Download PDF
    pdf_path = download_pdf(offer.get('pdf_url'), offer_id)
    if not pdf_path:
        continue

    try:
        # Run OCR
        ocr_text = ocr_pdf(pdf_path, offer_id)
        if not ocr_text:
            print("⚠️  OCR failed")
            continue

        print(f"\n📝 OCR Text Preview (first 500 chars):")
        print("-" * 80)
        print(ocr_text[:500])
        print("-" * 80)

        # Extract data
        print(f"\n🔍 Extracting structured data...")
        extraction = extract_data_from_ocr(ocr_text, offer_id)

        print(f"\n✅ EXTRACTION RESULTS:")
        print(f"   Template: {extraction.get('template_type', 'unknown')}")
        print(f"   Confidence: {extraction.get('confidence_score', 0):.2f}")
        print(f"   Total Price: €{extraction.get('total_price', 'N/A')}")
        print(f"   Buyer Known: {extraction.get('buyer_known', 'N/A')}")
        print(f"   Plots: {len(extraction.get('plots', []))}")

        if extraction.get('plots'):
            print(f"\n   📍 Plot Details:")
            for plot in extraction['plots'][:5]:  # Show first 5
                print(f"      - Parcel: {plot.get('parcel_id', 'N/A')}")
                print(f"        Area: {plot.get('area_m2', 'N/A')} m²")
                print(f"        Price: €{plot.get('price_eur', 'N/A')}")
                print(f"        Share: {plot.get('share', '1/1')}")

    finally:
        # Cleanup
        if pdf_path and pdf_path.exists():
            pdf_path.unlink()

print(f"\n{'='*80}")
print("✅ TEST COMPLETE")
print(f"{'='*80}\n")

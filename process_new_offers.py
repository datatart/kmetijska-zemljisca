#!/usr/bin/env python3
"""
Incremental PDF processing: Only OCR new offers that haven't been processed yet
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import subprocess
import tempfile
import time
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

# Import existing extractor
import sys
sys.path.append(str(Path(__file__).parent))
from enhanced_extractor import EnhancedExtractor


def load_processed_offers():
    """Load set of already-processed offer IDs"""
    processed_file = Path('data/processed_offers.json')
    if processed_file.exists():
        with open(processed_file, 'r') as f:
            data = json.load(f)
            return set(data.get('processed_ids', []))
    return set()


def save_processed_offers(processed_ids):
    """Save updated set of processed offer IDs"""
    processed_file = Path('data/processed_offers.json')
    data = {
        'processed_ids': sorted(list(processed_ids)),
        'last_updated': datetime.now().isoformat(),
        'total_processed': len(processed_ids)
    }
    with open(processed_file, 'w') as f:
        json.dump(data, f, indent=2)


def load_extraction_results():
    """Load existing extraction results database"""
    results_file = Path('data/extraction_results.json')
    if results_file.exists():
        with open(results_file, 'r') as f:
            return json.load(f)
    return {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'total_extractions': 0
        },
        'extractions': {}
    }


def save_extraction_results(results):
    """Save updated extraction results"""
    results['metadata']['last_updated'] = datetime.now().isoformat()
    results['metadata']['total_extractions'] = len(results['extractions'])

    results_file = Path('data/extraction_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def download_pdf(pdf_url, offer_id, max_retries=3):
    """Download PDF to temporary location with retry logic"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                print(f"   Retry {attempt}/{max_retries} after {wait_time}s...", end=' ')
                time.sleep(wait_time)
            else:
                print(f"   Downloading PDF for {offer_id}...", end=' ')

            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()

            # Save to temporary file
            pdf_path = Path(tempfile.gettempdir()) / f"{offer_id}.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ ({len(response.content) / 1024:.1f} KB)")
            return pdf_path

        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                print(f"✗ Connection error, retrying...")
                continue
            else:
                print(f"✗ Failed after {max_retries} attempts (Connection error)")
                return None
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                print(f"✗ Timeout, retrying...")
                continue
            else:
                print(f"✗ Failed after {max_retries} attempts (Timeout)")
                return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None

    return None


def ocr_pdf(pdf_path, offer_id):
    """Convert PDF to images and run Tesseract OCR"""
    try:
        print(f"   Running OCR on {offer_id}...", end=' ', flush=True)
        start_time = time.time()

        # Convert PDF to images (300 DPI for good quality)
        images = convert_from_path(
            pdf_path,
            dpi=300,
            fmt='jpeg',
            thread_count=2
        )

        # Run OCR on each page
        ocr_text = ""
        for i, image in enumerate(images, 1):
            # Use Slovenian language pack
            page_text = pytesseract.image_to_string(
                image,
                lang='slv',  # Slovenian
                config='--psm 1'  # Automatic page segmentation with OSD
            )
            ocr_text += f"\n--- Page {i} ---\n{page_text}\n"

        elapsed = time.time() - start_time
        print(f"✓ ({len(images)} pages, {elapsed:.1f}s)")

        return ocr_text

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def extract_data_from_ocr(ocr_text, offer_id):
    """Extract structured data from OCR text using enhanced extractor"""
    try:
        extractor = EnhancedExtractor()
        result = extractor.extract_from_ocr_text(ocr_text, pdf_id=offer_id)

        # Convert to serializable dict
        extraction = {
            'offer_id': offer_id,
            'timestamp': datetime.now().isoformat(),
            'total_price': result.total_price,
            'buyer_known': result.buyer_known,
            'confidence_score': result.confidence_score,
            'template_type': result.template_type,
            'plots': [
                {
                    'parcel_id': p.parcel_id,
                    'area_m2': p.area_m2,
                    'price_eur': p.price_eur,
                    'share': p.share,
                    'confidence': p.confidence
                }
                for p in result.plots
            ]
        }

        return extraction

    except Exception as e:
        print(f"   ⚠️  Extraction error: {e}")
        return {
            'offer_id': offer_id,
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'confidence_score': 0.0
        }


def process_new_offers():
    """Main function: Process only new offers that haven't been OCR'd yet"""

    print("=" * 80)
    print("🔄 INCREMENTAL PDF OCR PROCESSING")
    print("=" * 80)

    # Step 1: Load current offers from fresh dataset
    print("\n📋 Loading current offers...")
    with open('data/fresh_agricultural_offers.json', 'r') as f:
        current_data = json.load(f)

    current_offers = current_data['offers']
    current_ids = {offer['id'] for offer in current_offers}
    print(f"   ✓ Found {len(current_ids)} current offers")

    # Step 2: Load already-processed offers
    print("\n📂 Loading processed offers history...")
    processed_ids = load_processed_offers()
    print(f"   ✓ Already processed: {len(processed_ids)} offers")

    # Step 3: Find NEW offers
    new_ids = current_ids - processed_ids
    print(f"\n🆕 New offers to process: {len(new_ids)}")

    if not new_ids:
        print("   ✓ No new offers - all up to date!")
        return

    # Step 4: Load existing extraction results
    extraction_results = load_extraction_results()

    # Step 5: Process each new offer
    print(f"\n🔧 Processing {len(new_ids)} new offers...")
    print("-" * 80)

    successful = 0
    failed = 0

    for idx, offer_id in enumerate(sorted(new_ids), 1):
        print(f"\n[{idx}/{len(new_ids)}] Processing offer {offer_id}")

        # Find offer data
        offer = next((o for o in current_offers if o['id'] == offer_id), None)
        if not offer:
            print(f"   ⚠️  Offer not found in dataset")
            failed += 1
            continue

        pdf_url = offer.get('pdf_url')
        if not pdf_url:
            print(f"   ⚠️  No PDF URL available")
            failed += 1
            processed_ids.add(offer_id)  # Mark as processed anyway
            continue

        # Download PDF
        pdf_path = download_pdf(pdf_url, offer_id)
        if not pdf_path:
            failed += 1
            continue

        try:
            # Run OCR
            ocr_text = ocr_pdf(pdf_path, offer_id)
            if not ocr_text:
                failed += 1
                continue

            # Extract structured data
            print(f"   Extracting data...", end=' ')
            extraction = extract_data_from_ocr(ocr_text, offer_id)

            # Show results
            if extraction.get('total_price'):
                print(f"✓ Price: €{extraction['total_price']:,.2f}")
            elif extraction.get('plots'):
                print(f"✓ {len(extraction['plots'])} plots")
            else:
                print(f"⚠️  No data extracted (confidence: {extraction.get('confidence_score', 0):.2f})")

            # Save extraction result
            extraction_results['extractions'][offer_id] = extraction

            # Mark as processed
            processed_ids.add(offer_id)
            successful += 1

        finally:
            # Clean up temporary PDF
            if pdf_path and pdf_path.exists():
                pdf_path.unlink()

        # Add delay between offers to avoid overwhelming the server
        if idx < len(new_ids):
            time.sleep(2)  # 2 second delay between offers

    # Step 6: Save updated data
    print(f"\n💾 Saving results...")
    save_extraction_results(extraction_results)
    save_processed_offers(processed_ids)

    print(f"\n{'=' * 80}")
    print("✅ PROCESSING COMPLETE")
    print(f"{'=' * 80}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Total processed (all time): {len(processed_ids)}")
    print(f"   Extraction database size: {len(extraction_results['extractions'])} offers")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    process_new_offers()

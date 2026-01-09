#!/usr/bin/env python3
"""
Fresh scraper for e-uprava agricultural land offers
Creates a clean dashboard from scratch
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path
from datetime import datetime
import time


def load_official_ko_list():
    """Load official KO list for validation and name lookup"""
    ko_list_file = Path('data/official_ko_list.json')
    if not ko_list_file.exists():
        return {}, {}

    with open(ko_list_file, 'r', encoding='utf-8') as f:
        ko_list = json.load(f)

    # Create reverse lookup: name -> code
    name_to_code = {}
    for code, name in ko_list.items():
        try:
            code_int = str(int(code))
            name_to_code[name.upper()] = code_int
        except:
            pass

    return ko_list, name_to_code


def normalize_ko_code(code):
    """Normalize KO code by removing leading zeros"""
    try:
        return str(int(code))
    except:
        return code


def fetch_rss_feed(max_retries=3, retry_delay=5):
    """Fetch RSS feed and return agricultural offers with retry logic"""
    rss_url = "https://e-uprava.gov.si/rss/?generatorName=oglasnaDeska&siteRoot=%2Fsi%2Fe-uprava%2Foglasnadeska"

    print(f"📡 Fetching RSS feed from: {rss_url}")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(rss_url, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            items = root.findall('.//item')

            # Filter for agricultural offers
            agri_offers = []
            for item in items:
                title = item.find('title')
                if title is not None and 'kmetijsko' in title.text.lower():
                    link = item.find('link')
                    guid = item.find('guid')
                    pubDate = item.find('pubDate')
                    description = item.find('description')

                    agri_offers.append({
                        'title': title.text,
                        'detail_url': link.text if link is not None else '',
                        'guid': guid.text if guid is not None else '',
                        'rss_published': pubDate.text if pubDate is not None else '',
                        'description': description.text if description is not None else ''
                    })

            print(f"   ✓ Found {len(agri_offers)} agricultural land offers")
            return agri_offers

        except requests.exceptions.HTTPError as e:
            last_error = e
            if attempt < max_retries:
                print(f"   ⚠️  Attempt {attempt}/{max_retries} failed: {e}")
                print(f"   ⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"   ❌ All {max_retries} attempts failed")
                raise

        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries:
                print(f"   ⚠️  Attempt {attempt}/{max_retries} failed: {e}")
                print(f"   ⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"   ❌ All {max_retries} attempts failed")
                raise

    raise last_error


def extract_id_from_url(url):
    """Extract offer ID from URL"""
    match = re.search(r'id=(\d+)', url)
    return match.group(1) if match else None


def extract_ko_improved(soup, ko_list, name_to_code):
    """
    Improved KO extraction using multiple strategies
    Returns: (code, name, confidence, method)
    """
    results = []
    text = soup.get_text(separator=' ')

    # Method 1: "k.o. CODE NAME" pattern
    matches = re.findall(
        r'k\.?\s*o\.?\s*(\d{3,4})(?:\s*[-–]\s*|\s+)([A-ZČŠŽĆĐ][^\n,]{2,40})',
        text,
        re.IGNORECASE
    )
    for code, name in matches:
        if normalize_ko_code(code) in ko_list:
            results.append((code, name.strip(), 0.9, 'ko_code_name'))

    # Method 2: "k.o. NAME" pattern (lookup name in official list)
    # Improved regex to stop before common words like "parc", "parcela"
    matches = re.findall(
        r'k\.?\s*o\.?\s+([A-ZČŠŽĆĐ][A-ZČŠŽĆĐ\s]{2,40}?)(?:\s+parc|\s+parcela|[,\.\n]|$)',
        text,
        re.IGNORECASE
    )
    for name in matches:
        name_clean = name.strip()
        name_upper = name_clean.upper()

        if name_upper in name_to_code:
            code = name_to_code[name_upper]
            results.append((code, name_clean, 0.85, 'ko_name_only'))
        else:
            # Try partial match - but with stricter rules to avoid false matches
            # Avoid short names (<=5 chars) to prevent "IG" matching "MAREZIGE"
            if len(name_upper) > 5:
                for official_name, official_code in name_to_code.items():
                    # Only match if extracted name STARTS the official name
                    # This prevents "IG" from matching "MAREZIGE"
                    if official_name.startswith(name_upper):
                        results.append((official_code, official_name, 0.7, 'ko_name_partial'))
                        break

    # Method 3: Look in div.noMargin
    no_margin_divs = soup.find_all('div', class_='noMargin')
    for div in no_margin_divs:
        div_text = div.get_text()

        # Same improved regex to stop before "parc", "parcela"
        matches = re.findall(
            r'k\.?\s*o\.?\s+([A-ZČŠŽĆĐ][A-ZČŠŽĆĐ\s]{2,40}?)(?:\s+parc|\s+parcela|[,\.\n]|$)',
            div_text,
            re.IGNORECASE
        )
        for name in matches:
            name_clean = name.strip()
            name_upper = name_clean.upper()

            if name_upper in name_to_code:
                code = name_to_code[name_upper]
                results.append((code, name_clean, 0.95, 'div_ko_name'))

    # Return best match by confidence
    if results:
        seen = {}
        for code, name, confidence, method in results:
            key = normalize_ko_code(code)
            if key not in seen or seen[key][2] < confidence:
                seen[key] = (code, name, confidence, method)

        best = max(seen.values(), key=lambda x: x[2])
        return best[0], best[1]

    return None, None


def scrape_detail_page(url, offer_id, ko_list, name_to_code):
    """Scrape detail page for metadata"""
    print(f"   Scraping {offer_id}...", end=' ')

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        data = {
            'id': offer_id,
            'municipality': '',
            'institution': '',  # UE name
            'notice_number': '',
            'published_date': '',
            'valid_until': '',
            'pdf_url': '',
            'ko_code': '',
            'ko_name': ''
        }

        # Extract KO using improved method
        ko_code, ko_name = extract_ko_improved(soup, ko_list, name_to_code)
        if ko_code:
            data['ko_code'] = normalize_ko_code(ko_code)
            data['ko_name'] = ko_name or ''

        # Find all <p> tags for metadata
        all_p = soup.find_all('p')

        for i, p in enumerate(all_p):
            text = p.get_text(strip=True)

            # Extract institution/municipality (look for <a> tag after "Institucija")
            if text == 'Institucija':
                # Find the next <a> tag (it contains the institution name)
                parent = p.parent
                if parent:
                    link = parent.find('a')
                    if link:
                        institution_name = link.get_text(strip=True)
                        data['institution'] = institution_name
                        data['municipality'] = institution_name  # Keep for backward compatibility

            # Extract notice number
            if text == 'Št. dokumenta' and i + 1 < len(all_p):
                data['notice_number'] = all_p[i + 1].get_text(strip=True)

            # Extract dates
            if text == 'Datum in število dni objave' and i + 1 < len(all_p):
                date_text = all_p[i + 1].get_text(strip=True)
                # Parse dates from format: "24. 12. 2025 (objava do 8. 1. 2026)"
                pub_match = re.search(r'(\d+\.\s*\d+\.\s*\d{4})', date_text)
                if pub_match:
                    data['published_date'] = pub_match.group(1).strip()

                valid_match = re.search(r'objava do\s+(\d+\.\s*\d+\.\s*\d{4})', date_text)
                if valid_match:
                    data['valid_until'] = valid_match.group(1).strip()

        # Extract PDF download URL
        pdf_link = soup.find('a', href=re.compile(r'/\.download/oglasna/datoteka'))
        if pdf_link:
            pdf_path = pdf_link.get('href')
            if pdf_path and not pdf_path.startswith('http'):
                data['pdf_url'] = 'https://e-uprava.gov.si' + pdf_path
            else:
                data['pdf_url'] = pdf_path or ''

        print("✓")
        return data

    except Exception as e:
        print(f"⚠️  Error: {e}")
        return {
            'id': offer_id,
            'municipality': '',
            'institution': '',
            'notice_number': '',
            'published_date': '',
            'valid_until': '',
            'pdf_url': '',
            'ko_code': '',
            'ko_name': '',
            'error': str(e)
        }


def scrape_all_offers(offers, ko_list, name_to_code, max_offers=None):
    """Scrape detail pages for all offers"""
    print(f"\n📋 Scraping detail pages...")

    if max_offers:
        offers = offers[:max_offers]
        print(f"   (Limited to {max_offers} offers for testing)")

    enriched = []
    for idx, offer in enumerate(offers, 1):
        offer_id = extract_id_from_url(offer['detail_url'])
        if not offer_id:
            continue

        print(f"   [{idx}/{len(offers)}]", end=' ')

        # Scrape detail page
        detail_data = scrape_detail_page(offer['detail_url'], offer_id, ko_list, name_to_code)

        # Merge with RSS data
        combined = {
            **offer,
            **detail_data
        }

        enriched.append(combined)

        # Rate limiting
        if idx < len(offers):
            time.sleep(0.5)

    return enriched


def parse_slovenian_date(date_str):
    """Parse Slovenian date format to datetime"""
    try:
        parts = date_str.replace('.', '').strip().split()
        if len(parts) == 3:
            day, month, year = parts
            return datetime(int(year), int(month), int(day))
    except:
        pass
    return None


def filter_active_offers(offers):
    """Filter to only active (non-expired) offers"""
    now = datetime.now()
    active = []

    for offer in offers:
        if offer.get('valid_until'):
            dt = parse_slovenian_date(offer['valid_until'])
            if dt and dt >= now:
                active.append(offer)
        else:
            # If no expiry date, include it
            active.append(offer)

    return active


def save_dataset(offers, filename='fresh_agricultural_offers.json'):
    """Save offers to JSON file"""
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'total_offers': len(offers),
            'source': 'https://e-uprava.gov.si/si/e-uprava/oglasnadeska.html',
            'type': 'agricultural_land_offers'
        },
        'offers': offers
    }

    output_path = Path('data') / filename
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved {len(offers)} offers to: {output_path}")
    print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    print("="*80)
    print("🌾 FRESH E-UPRAVA AGRICULTURAL LAND OFFERS SCRAPER")
    print("="*80)

    # Step 0: Load official KO list for improved extraction
    print("\n📋 Loading official KO list...")
    ko_list, name_to_code = load_official_ko_list()
    if ko_list:
        print(f"   ✓ Loaded {len(set(str(int(c)) for c in ko_list.keys() if c.isdigit()))} unique KO codes")
    else:
        print("   ⚠️  No KO list found - KO extraction will be limited")

    # Step 1: Fetch RSS feed
    offers = fetch_rss_feed()

    # Step 2: Scrape detail pages
    enriched_offers = scrape_all_offers(offers, ko_list, name_to_code)

    # Step 3: Filter active offers
    active_offers = filter_active_offers(enriched_offers)
    print(f"\n✓ Filtered to {len(active_offers)} active offers (from {len(enriched_offers)} total)")

    # Step 4: Save to JSON
    save_dataset(active_offers)

    # Statistics
    print(f"\n📊 Statistics:")
    print(f"   Total scraped: {len(enriched_offers)}")
    print(f"   Active offers: {len(active_offers)}")
    print(f"   Expired: {len(enriched_offers) - len(active_offers)}")

    # Count KO data
    offers_with_ko = sum(1 for offer in active_offers if offer.get('ko_code'))
    print(f"   Offers with KO data: {offers_with_ko} ({offers_with_ko/len(active_offers)*100:.1f}%)")

    # Count by institution
    institutions = {}
    for offer in active_offers:
        inst = offer.get('institution', 'Unknown')
        institutions[inst] = institutions.get(inst, 0) + 1

    print(f"   Unique institutions (UE): {len(institutions)}")

    # Show top institutions
    top_institutions = sorted(institutions.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\n   Top institutions:")
    for inst, count in top_institutions:
        print(f"     - {inst}: {count} offers")

    print("\n" + "="*80)
    print("✅ SCRAPING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

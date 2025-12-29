#!/usr/bin/env python3
"""
Fetch parcel geometries from GURS (Geodetska uprava RS) public API
Only fetches geometries for parcels we don't have yet (incremental)
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import time


def load_existing_geometries():
    """Load existing parcel geometry cache"""
    geom_file = Path('data/parcel_geometries.json')
    if geom_file.exists():
        with open(geom_file, 'r') as f:
            return json.load(f)
    return {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'total_parcels': 0
        },
        'geometries': {}
    }


def save_geometries(geometries_data):
    """Save parcel geometries to cache"""
    geometries_data['metadata']['last_updated'] = datetime.now().isoformat()
    geometries_data['metadata']['total_parcels'] = len(geometries_data['geometries'])

    geom_file = Path('data/parcel_geometries.json')
    with open(geom_file, 'w') as f:
        json.dump(geometries_data, f, indent=2, ensure_ascii=False)


def fetch_parcel_geometry(ko_code, parcel_id):
    """
    Fetch parcel geometry from GURS OGC API

    Uses the OGC Features API from GURS:
    https://ipi.eprostor.gov.si/
    """
    try:
        # GURS OGC API endpoint for parcels
        api_url = "https://ipi.eprostor.gov.si/wfs-si-gurs-kn/ogc/features/collections/SI.GURS.KN:PARCELE/items"

        # Filter for KO code and parcel number
        # NAZIV is like "143 KO_NAME" so we need to match exactly to avoid "1432", "1433", etc.
        params = {
            'limit': 100,
            'f': 'json',
            'filter': f"NAZIV LIKE '{ko_code} %' AND ST_PARCELE = '{parcel_id}'",
            'filter-lang': 'cql-text'
        }

        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check if we got features
        features = data.get('features', [])
        if not features:
            return None

        # Get the first feature (should be unique match)
        feature = features[0]
        geometry = feature.get('geometry')
        properties = feature.get('properties', {})

        # Get area from POVRSINA property
        area_m2 = properties.get('POVRSINA')
        ko_name = properties.get('NAZIV', '').replace(f'{ko_code} ', '')

        return {
            'geometry': geometry,
            'area_m2': area_m2,
            'properties': {
                'ko_code': ko_code,
                'parcel_id': parcel_id,
                'ko_name': ko_name,
                'povrsina_m2': area_m2,
            },
            'fetched_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"      ⚠️  Error fetching {ko_code}/{parcel_id}: {e}")
        return None


def collect_parcels_to_fetch():
    """Collect all parcels from extraction results that need geometries"""

    # Load extraction results
    extraction_file = Path('data/extraction_results.json')
    if not extraction_file.exists():
        print("⚠️  No extraction_results.json found")
        return []

    with open(extraction_file, 'r') as f:
        extractions = json.load(f)

    # Load offers to get KO codes
    offers_file = Path('data/fresh_agricultural_offers.json')
    if not offers_file.exists():
        print("⚠️  No fresh_agricultural_offers.json found")
        return []

    with open(offers_file, 'r') as f:
        offers_data = json.load(f)

    # Create offer ID to KO code mapping
    offer_ko_map = {}
    for offer in offers_data.get('offers', []):
        offer_id = str(offer.get('id'))
        ko_code = offer.get('ko_code')
        if ko_code:
            offer_ko_map[offer_id] = ko_code

    # Collect unique parcels
    parcels = {}
    for offer_id, extraction in extractions.get('extractions', {}).items():
        # Get KO code from offer data
        ko_code = offer_ko_map.get(str(offer_id))

        if not ko_code:
            continue

        for plot in extraction.get('plots', []):
            parcel_id = plot.get('parcel_id')

            if parcel_id:
                key = f"{ko_code}/{parcel_id}"
                if key not in parcels:
                    parcels[key] = {
                        'ko_code': ko_code,
                        'parcel_id': parcel_id,
                        'offer_ids': [offer_id]
                    }
                else:
                    parcels[key]['offer_ids'].append(offer_id)

    return list(parcels.values())


def fetch_geometries_incremental():
    """Fetch geometries for parcels we don't have yet"""

    print("=" * 80)
    print("📍 FETCHING PARCEL GEOMETRIES")
    print("=" * 80)

    # Load existing geometries
    print("\n📂 Loading existing geometries...")
    geometries_data = load_existing_geometries()
    existing = set(geometries_data['geometries'].keys())
    print(f"   ✓ Already have: {len(existing)} parcels")

    # Collect parcels that need geometries
    print("\n🔍 Collecting parcels from extraction results...")
    all_parcels = collect_parcels_to_fetch()
    print(f"   ✓ Found {len(all_parcels)} unique parcels in extractions")

    # Filter to only new parcels
    new_parcels = [p for p in all_parcels if f"{p['ko_code']}/{p['parcel_id']}" not in existing]
    print(f"   🆕 Need to fetch: {len(new_parcels)} parcels")

    if not new_parcels:
        print("\n   ✓ All parcels already have geometries!")
        return

    # Fetch geometries
    print(f"\n🌍 Fetching geometries from GURS API...")
    print("-" * 80)

    successful = 0
    failed = 0

    for idx, parcel in enumerate(new_parcels, 1):
        ko_code = parcel['ko_code']
        parcel_id = parcel['parcel_id']
        key = f"{ko_code}/{parcel_id}"

        print(f"[{idx}/{len(new_parcels)}] {key}...", end=' ', flush=True)

        # Fetch geometry
        geometry_data = fetch_parcel_geometry(ko_code, parcel_id)

        if geometry_data:
            geometries_data['geometries'][key] = geometry_data
            area = geometry_data.get('area_m2', 'N/A')
            print(f"✓ ({area} m²)")
            successful += 1
        else:
            print(f"✗ Not found")
            failed += 1

        # Rate limiting - be nice to the API
        if idx < len(new_parcels):
            time.sleep(0.5)  # 500ms between requests

    # Save geometries
    print(f"\n💾 Saving geometries...")
    save_geometries(geometries_data)

    print(f"\n{'=' * 80}")
    print("✅ GEOMETRY FETCH COMPLETE")
    print(f"{'=' * 80}")
    print(f"   New geometries: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Total in cache: {len(geometries_data['geometries'])}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    fetch_geometries_incremental()

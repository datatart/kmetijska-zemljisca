#!/usr/bin/env python3
"""
Generate a fresh, simple dashboard from scraped e-uprava data
"""

import json
from pathlib import Path
from datetime import datetime


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


def generate_dashboard():
    """Generate HTML dashboard"""

    # Load data
    dataset_file = Path("data/fresh_agricultural_offers.json")
    with open(dataset_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    offers = data['offers']
    now = datetime.now()

    # Load extraction results (OCR data)
    extraction_file = Path("data/extraction_results.json")
    extractions = {}
    if extraction_file.exists():
        with open(extraction_file, 'r', encoding='utf-8') as f:
            extraction_data = json.load(f)
            extractions = extraction_data.get('extractions', {})

    # Load parcel geometries (for area calculation)
    geometry_file = Path("data/parcel_geometries.json")
    geometries = {}
    if geometry_file.exists():
        with open(geometry_file, 'r', encoding='utf-8') as f:
            geometry_data = json.load(f)
            geometries = geometry_data.get('geometries', {})

    # Calculate statistics
    active_count = 0
    for offer in offers:
        if offer.get('valid_until'):
            dt = parse_slovenian_date(offer['valid_until'])
            if dt and dt >= now:
                active_count += 1

    # Calculate statistics
    offers_with_ko = sum(1 for offer in offers if offer.get('ko_code'))
    offers_with_price = sum(1 for offer in offers if str(offer['id']) in extractions and extractions[str(offer['id'])].get('total_price'))

    html = f'''<!DOCTYPE html>
<html lang="sl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ponudbe za kmetijska zemljišča - e-Uprava</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .offer-row:hover {{
            background-color: #f9fafb;
        }}
    </style>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Header with Statistics -->
        <header class="bg-gradient-to-r from-green-600 to-green-700 text-white shadow-lg">
            <div class="max-w-7xl mx-auto px-4 py-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-white bg-opacity-10 backdrop-blur-sm rounded-lg p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-green-100 text-sm font-medium">Aktivne ponudbe</p>
                                <p class="text-3xl font-bold text-white mt-2">{len(offers)}</p>
                            </div>
                            <div class="text-4xl">📊</div>
                        </div>
                    </div>

                    <div class="bg-white bg-opacity-10 backdrop-blur-sm rounded-lg p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-green-100 text-sm font-medium">S podatki o KO</p>
                                <p class="text-3xl font-bold text-white mt-2">{offers_with_ko}</p>
                            </div>
                            <div class="text-4xl">📍</div>
                        </div>
                    </div>

                    <div class="bg-white bg-opacity-10 backdrop-blur-sm rounded-lg p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-green-100 text-sm font-medium">S podatki o ceni</p>
                                <p class="text-3xl font-bold text-white mt-2">{offers_with_price}</p>
                            </div>
                            <div class="text-4xl">💰</div>
                        </div>
                    </div>
                </div>
            </div>
        </header>

        <div class="max-w-7xl mx-auto px-4 py-6">

            <!-- Filters -->
            <div class="bg-white rounded-lg shadow p-6 mb-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">Filtriranje</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Filtriraj po upravni enoti</label>
                        <select
                            id="ueFilter"
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        >
                            <option value="">Vse upravne enote</option>
'''

    # Get unique institutions
    institutions = set()
    for offer in offers:
        institution = offer.get('institution', '')
        if institution:
            institutions.add(institution)

    # Add institution filter options (sorted)
    for institution in sorted(institutions):
        # Remove "Upravna enota " prefix for display
        display_name = institution.replace('Upravna enota ', '')
        html += f'                            <option value="{institution}">{display_name}</option>\n'

    html += '''                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Iskanje</label>
                        <input
                            type="text"
                            id="koFilter"
                            placeholder="Išči po upravni enoti ali katastrski občini..."
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        >
                    </div>
                </div>
'''

    html += f'''
                <div class="mt-4 flex items-center justify-between">
                    <p class="text-sm text-gray-600">
                        Prikazujem <span id="visibleCount" class="font-semibold">{len(offers)}</span> od {len(offers)} ponudb
                    </p>
                    <button
                        id="resetBtn"
                        class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                    >
                        Ponastavi filtre
                    </button>
                </div>
            </div>'''

    html += '''
            <!-- Table -->
            <div class="bg-white rounded-lg shadow overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Številka dokumenta</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Upravna enota</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Katastrska občina</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cena</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Površina</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Parcele</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Objavljeno</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Veljavno do</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Povezave</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody" class="bg-white divide-y divide-gray-200">
'''

    # Build table rows
    for idx, offer in enumerate(offers, 1):
        notice_num = offer.get('notice_number', '')
        published = offer.get('published_date', '')
        valid_until = offer.get('valid_until', '')
        pdf_url = offer.get('pdf_url', '')
        ko_code = offer.get('ko_code', '')
        ko_name = offer.get('ko_name', '')
        institution = offer.get('institution', '')

        # Format KO display - only show if available
        if ko_code:
            ko_display = f"{ko_code} - {ko_name}" if ko_name else ko_code
        else:
            ko_display = "-"

        # Format institution display - remove "Upravna enota " prefix
        if institution:
            institution_display = institution.replace('Upravna enota ', '')
        else:
            institution_display = "-"

        # Change disposition from attachment to inline so PDF opens in browser
        if pdf_url and 'disposition=attachment' in pdf_url:
            pdf_url = pdf_url.replace('disposition=attachment', 'disposition=inline')

        detail_url = offer.get('detail_url', '')
        offer_id = offer.get('id', '')

        # Create searchable KO text (code + name)
        ko_search = f"{ko_code} {ko_name}".lower() if ko_code else ""

        # Create searchable UE text (without "Upravna enota" prefix)
        ue_search = institution.replace('Upravna enota ', '').lower() if institution else ""

        # Get extraction data for this offer
        extraction = extractions.get(str(offer_id), {})

        # Format price
        total_price = extraction.get('total_price')
        if total_price:
            price_display = f"€{total_price:,.2f}"
        else:
            price_display = "-"

        # Calculate total area from parcel geometries
        plots = extraction.get('plots', [])
        total_area_m2 = 0
        parcels_with_area = 0

        for plot in plots:
            parcel_id = plot.get('parcel_id', '')
            # Try to find geometry (format: "KO_CODE/PARCEL_ID")
            if ko_code and parcel_id:
                geom_key = f"{ko_code}/{parcel_id}"
                geom_data = geometries.get(geom_key, {})
                area = geom_data.get('area_m2')
                if area:
                    total_area_m2 += area
                    parcels_with_area += 1

        # Format area display
        if total_area_m2 > 0:
            # Convert to hectares if > 10,000 m²
            if total_area_m2 >= 10000:
                area_ha = total_area_m2 / 10000
                area_display = f"{area_ha:,.2f} ha"
            else:
                area_display = f"{total_area_m2:,.0f} m²"
        else:
            area_display = "-"

        # Format parcel count
        num_parcels = len(plots)
        if num_parcels > 0:
            parcels_display = str(num_parcels)
        else:
            parcels_display = "-"

        html += f'''
                            <tr class="offer-row" data-notice="{notice_num.lower()}" data-ko="{ko_code}" data-ko-search="{ko_search}" data-ue-search="{ue_search}" data-institution="{institution}">
                                <td class="px-4 py-3 text-sm text-gray-900">{idx}</td>
                                <td class="px-4 py-3 text-sm">
                                    <a href="{detail_url}" target="_blank" class="text-blue-600 hover:text-blue-800 hover:underline font-medium">
                                        {notice_num}
                                    </a>
                                </td>
                                <td class="px-4 py-3 text-sm text-gray-600">{institution_display}</td>
                                <td class="px-4 py-3 text-sm text-gray-600">{ko_display}</td>
                                <td class="px-4 py-3 text-sm font-medium text-gray-900">{price_display}</td>
                                <td class="px-4 py-3 text-sm text-gray-600">{area_display}</td>
                                <td class="px-4 py-3 text-sm text-gray-600">{parcels_display}</td>
                                <td class="px-4 py-3 text-sm text-gray-600">{published}</td>
                                <td class="px-4 py-3 text-sm text-gray-600">{valid_until}</td>
                                <td class="px-4 py-3 text-sm">
                                    <a href="{pdf_url}" target="_blank" class="inline-flex items-center px-3 py-1 bg-green-100 text-green-700 text-xs font-medium rounded hover:bg-green-200 transition">
                                        📄 PDF
                                    </a>
                                </td>
                            </tr>
'''

    html += '''
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Filter functionality
        const ueFilter = document.getElementById('ueFilter');
        const koFilter = document.getElementById('koFilter');
        const resetBtn = document.getElementById('resetBtn');
        const visibleCount = document.getElementById('visibleCount');
        const rows = document.querySelectorAll('.offer-row');

        function applyFilters() {
            const selectedUE = ueFilter.value;
            const searchTerm = koFilter.value.toLowerCase();
            let visible = 0;

            rows.forEach(row => {
                const institution = row.getAttribute('data-institution');
                const koSearch = row.getAttribute('data-ko-search');
                const ueSearch = row.getAttribute('data-ue-search');

                const matchesUE = !selectedUE || institution === selectedUE;
                // Search matches if found in either KO or UE
                const matchesSearch = !searchTerm || koSearch.includes(searchTerm) || ueSearch.includes(searchTerm);

                if (matchesUE && matchesSearch) {
                    row.classList.remove('hidden');
                    visible++;
                } else {
                    row.classList.add('hidden');
                }
            });

            visibleCount.textContent = visible;
        }

        ueFilter.addEventListener('change', applyFilters);
        koFilter.addEventListener('input', applyFilters);

        resetBtn.addEventListener('click', () => {
            ueFilter.value = '';
            koFilter.value = '';
            applyFilters();
        });
    </script>
</body>
</html>
'''

    # Save HTML
    output_file = Path("fresh_agricultural_dashboard.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print("\n" + "="*80)
    print("📊 FRESH DASHBOARD GENERATED")
    print("="*80)
    print(f"\n✅ Dashboard created successfully!")
    print(f"   File: {output_file}")
    print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
    print(f"\n📋 Dashboard includes:")
    print(f"   - {len(offers)} agricultural land offers")
    print(f"\n🔍 Features:")
    print(f"   - 🔎 Search by document number")
    print(f"   - 🔗 Direct links to detail pages")
    print(f"   - 📄 Direct PDF download links")
    print(f"   - 📅 Publication and expiry dates")
    print(f"\n🌐 Open in browser: file://{output_file.absolute()}")
    print("="*80 + "\n")


if __name__ == "__main__":
    generate_dashboard()

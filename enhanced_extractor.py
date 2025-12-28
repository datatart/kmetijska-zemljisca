#!/usr/bin/env python3
"""
Enhanced OCR Data Extractor

Focuses on extracting the most critical data points from existing OCR texts:
1. Plot IDs (parcel numbers)
2. Total price
3. Total area
4. Individual plot areas
5. "Kupec je znan" status

Note: KO codes are not extracted from PDFs as they are available on detail pages.

Uses multi-strategy approach with confidence scoring.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class PlotExtraction:
    """Individual plot/parcel data"""
    parcel_id: str
    area_m2: Optional[int] = None
    price_eur: Optional[float] = None
    share: str = "1/1"
    confidence: float = 0.0


@dataclass
class DocumentExtraction:
    """Complete document extraction result"""
    pdf_id: str
    plots: List[PlotExtraction] = field(default_factory=list)
    total_price: Optional[float] = None
    total_area_m2: Optional[int] = None
    buyer_known: bool = False
    buyer_known_confidence: float = 0.0
    template_type: str = "unknown"
    confidence_score: float = 0.0
    extraction_notes: List[str] = field(default_factory=list)


class EnhancedExtractor:
    """Enhanced extractor focusing on critical data points"""

    def extract_from_ocr_text(self, text: str, pdf_id: str) -> DocumentExtraction:
        """Main extraction method"""

        # Detect template
        template = self._detect_template(text)

        # Extract based on template
        if template == "electronic_form":
            result = self._extract_electronic(text, pdf_id)
        elif template == "table_format":
            result = self._extract_table(text, pdf_id)
        elif template == "skzg":
            result = self._extract_skzg(text, pdf_id)
        else:
            result = self._extract_generic(text, pdf_id)

        result.template_type = template

        # Calculate confidence
        result.confidence_score = self._calculate_confidence(result)

        return result

    def _detect_template(self, text: str) -> str:
        """Detect document template type"""

        # Electronic form indicators
        if re.search(r'DOKUMENT JE ELEKTRONSKO PODPISAN', text, re.I):
            return "electronic_form"
        if re.search(r'Oznaka dokumenta.*?\d+-\d+', text, re.I):
            return "electronic_form"

        # SKZG format
        if re.search(r'Sklad kmetijskih zemljišč', text, re.I):
            return "skzg"
        if re.search(r'PONUDBO št', text, re.I):
            return "skzg"

        # Table format (many parcels)
        parcel_count = len(re.findall(r'\b\d{1,4}/\d{1,3}\b', text))
        if parcel_count >= 5:
            return "table_format"

        return "generic"

    def _extract_electronic(self, text: str, pdf_id: str) -> DocumentExtraction:
        """Extract from electronic form (highest accuracy template)"""
        result = DocumentExtraction(pdf_id=pdf_id)

        # Electronic forms have fields grouped by type, not per parcel
        # Order: all parcels, then all areas, then all prices

        # Extract all parcel IDs in order
        parcel_matches = list(re.finditer(r'Parcelna številka:[\s\n]*(\d+/\d+)', text))
        parcel_ids = [m.group(1) for m in parcel_matches]

        # Extract all prices (often right after parcel number)
        price_matches = list(re.finditer(r'Cena[/\s]*EUR:[\s\n]*(\d+(?:\.\d{2})?)', text))
        prices = []
        for m in price_matches:
            try:
                prices.append(float(m.group(1)))
            except:
                prices.append(None)

        # Extract all areas in order
        area_matches = list(re.finditer(r'Površina \(m[2²?]\):[\s\n]*(\d+)', text))
        areas = []
        for m in area_matches:
            try:
                areas.append(int(m.group(1)))
            except:
                areas.append(None)

        # Extract shares (if any)
        share_matches = list(re.finditer(
            r'kakšen delež.*?prodajate.*?[\s\n]*(\d+/\d+)',
            text,
            re.I
        ))
        shares = [m.group(1) for m in share_matches]

        # Match up the data by index
        num_parcels = len(parcel_ids)

        for i in range(num_parcels):
            parcel_id = parcel_ids[i]

            # Get corresponding area
            area = areas[i] if i < len(areas) else None

            # Get corresponding price
            price = prices[i] if i < len(prices) else None

            # Get corresponding share
            share = shares[i] if i < len(shares) else "1/1"

            plot = PlotExtraction(
                parcel_id=parcel_id,
                area_m2=area,
                price_eur=price,
                share=share,
                confidence=0.9  # High confidence for labeled fields
            )
            result.plots.append(plot)

        # Extract total price
        result.total_price = self._extract_total_price(text)

        # Extract total area
        if result.plots:
            total_area = sum(p.area_m2 for p in result.plots if p.area_m2)
            result.total_area_m2 = total_area if total_area > 0 else None

        # Check for "kupec znan"
        result.buyer_known, result.buyer_known_confidence = self._check_buyer_known(text)

        return result

    def _extract_table(self, text: str, pdf_id: str) -> DocumentExtraction:
        """Extract from table format documents"""
        result = DocumentExtraction(pdf_id=pdf_id)

        # Strategy 1: Find table rows with pattern: parcel_id followed by area
        # Look for parcel IDs and try to find associated areas

        # Find all parcel IDs
        parcel_matches = list(re.finditer(r'\b(\d{1,4}/\d{1,3})\b', text))

        for match in parcel_matches:
            parcel_id = match.group(1)

            # Look for area in nearby context (within 100 chars)
            start = match.start()
            end = min(match.end() + 100, len(text))
            context = text[start:end]

            # Try to find area in the context
            area_match = re.search(r'\b(\d{1,6})\b', context[len(parcel_id):])
            area = None

            if area_match:
                try:
                    potential_area = int(area_match.group(1))
                    # Validate area (not a year, reasonable range)
                    if not (1900 <= potential_area <= 2100) and 1 <= potential_area <= 999999:
                        area = potential_area
                except ValueError:
                    pass

            plot = PlotExtraction(
                parcel_id=parcel_id,
                area_m2=area,
                confidence=0.6  # Moderate confidence for table
            )
            result.plots.append(plot)

        # If too many duplicates or too many plots, try simpler approach
        if not result.plots or len(result.plots) > 50:
            result = self._extract_parcels_simple(text, pdf_id, result)

        result.total_price = self._extract_total_price(text)
        result.buyer_known, result.buyer_known_confidence = self._check_buyer_known(text)

        return result

    def _extract_skzg(self, text: str, pdf_id: str) -> DocumentExtraction:
        """Extract from SKZG format"""
        result = DocumentExtraction(pdf_id=pdf_id)

        # SKZG has specific table structure
        # Look for: parcele | (m²) | cena pattern

        # Find all parcel IDs
        parcel_matches = re.finditer(r'\b(\d{1,4}/\d{1,3})\b', text)

        for match in parcel_matches:
            parcel_id = match.group(1)

            # Look for area nearby
            context_start = max(0, match.start() - 50)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end]

            # Try to find area
            area_match = re.search(r'\b(\d{2,6})\s*(?:m[2²]?)?', context[match.start() - context_start:])
            area = None

            if area_match:
                try:
                    potential_area = int(area_match.group(1))
                    if 1 <= potential_area <= 999999 and not (1900 <= potential_area <= 2100):
                        area = potential_area
                except ValueError:
                    pass

            plot = PlotExtraction(
                parcel_id=parcel_id,
                area_m2=area,
                confidence=0.7
            )
            result.plots.append(plot)

        result.total_price = self._extract_total_price(text)
        result.buyer_known, result.buyer_known_confidence = self._check_buyer_known(text)

        return result

    def _extract_generic(self, text: str, pdf_id: str) -> DocumentExtraction:
        """Generic extraction with lower confidence"""
        result = DocumentExtraction(pdf_id=pdf_id)

        result = self._extract_parcels_simple(text, pdf_id, result)

        result.total_price = self._extract_total_price(text)
        result.buyer_known, result.buyer_known_confidence = self._check_buyer_known(text)

        return result

    def _extract_parcels_simple(self, text: str, pdf_id: str, result: DocumentExtraction) -> DocumentExtraction:
        """Simple parcel extraction fallback"""

        # Find all parcel IDs
        parcel_ids = re.findall(r'\b(\d{1,4}/\d{1,3})\b', text)

        # Deduplicate and limit
        seen = set()
        for parcel_id in parcel_ids:
            if parcel_id not in seen and len(seen) < 30:  # Limit to avoid false positives
                plot = PlotExtraction(
                    parcel_id=parcel_id,
                    confidence=0.4  # Low confidence
                )
                result.plots.append(plot)
                seen.add(parcel_id)

        return result

    def _extract_total_price(self, text: str) -> Optional[float]:
        """Extract total price"""

        # Pattern 1: "Cena skupaj: 21.000,00 EUR"
        match = re.search(
            r'Cena skupaj:[\s\n]*(\d{1,6}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            text,
            re.I
        )

        if match:
            price_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(price_str)
            except:
                pass

        # Pattern 2: Just large EUR amount
        match = re.search(r'(\d{1,6}[.,]\d{3}[.,]\d{2})\s*EUR', text)
        if match:
            price_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                price = float(price_str)
                if price >= 100:  # Reasonable minimum
                    return price
            except:
                pass

        return None

    def _check_buyer_known(self, text: str) -> Tuple[bool, float]:
        """Check if 'kupec je znan' status"""

        # Strong patterns
        if re.search(r'KUPEC\s+(?:JE\s+)?ZNAN', text, re.I):
            return True, 0.95

        if re.search(r'kupec.*?znan', text, re.I):
            return True, 0.8

        # Negative indicators
        if re.search(r'KUPEC\s+NI\s+ZNAN', text, re.I):
            return False, 0.9

        return False, 0.5


    def _calculate_confidence(self, result: DocumentExtraction) -> float:
        """Calculate overall extraction confidence"""

        if not result.plots:
            return 0.1

        # Average plot confidence
        avg_plot_conf = sum(p.confidence for p in result.plots) / len(result.plots)

        # Data completeness score
        completeness = 0.0
        if any(p.area_m2 for p in result.plots):
            completeness += 0.4  # Areas are important
        if result.total_price:
            completeness += 0.3  # Total price is valuable
        if result.buyer_known:
            completeness += 0.2  # Buyer status is useful
        if len(result.plots) >= 2:
            completeness += 0.1  # Multiple plots indicator

        return min((avg_plot_conf + completeness) / 2, 1.0)

    def process_batch(self, ocr_dir: Path, output_file: Path, limit: Optional[int] = None):
        """Process batch of OCR text files"""

        print("="*80)
        print("📊 ENHANCED OCR DATA EXTRACTOR")
        print("="*80)

        ocr_files = sorted(ocr_dir.glob("*.txt"))

        if limit:
            ocr_files = ocr_files[:limit]

        print(f"\n📂 Processing {len(ocr_files)} OCR files from: {ocr_dir}")

        results = []
        stats = {
            'total': 0,
            'with_plots': 0,
            'with_areas': 0,
            'with_price': 0,
            'buyer_known': 0,
            'high_confidence': 0  # >0.7
        }

        for i, ocr_file in enumerate(ocr_files, 1):
            pdf_id = ocr_file.stem

            with open(ocr_file, 'r', encoding='utf-8') as f:
                text = f.read()

            result = self.extract_from_ocr_text(text, pdf_id)
            results.append(asdict(result))

            # Update stats
            stats['total'] += 1
            if result.plots:
                stats['with_plots'] += 1
            if any(p.area_m2 for p in result.plots):
                stats['with_areas'] += 1
            if result.total_price:
                stats['with_price'] += 1
            if result.buyer_known:
                stats['buyer_known'] += 1
            if result.confidence_score >= 0.7:
                stats['high_confidence'] += 1

            # Progress indicator
            if i % 50 == 0 or i == len(ocr_files):
                print(f"   Progress: {i}/{len(ocr_files)} ({i/len(ocr_files)*100:.1f}%)")

        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Print statistics
        print("\n" + "="*80)
        print("✅ EXTRACTION COMPLETE")
        print("="*80)

        total = stats['total']
        print(f"\n📊 Results:")
        print(f"   Total documents: {total}")
        print(f"   Documents with plots: {stats['with_plots']} ({stats['with_plots']/total*100:.1f}%)")
        print(f"   Documents with areas: {stats['with_areas']} ({stats['with_areas']/total*100:.1f}%)")
        print(f"   Documents with total price: {stats['with_price']} ({stats['with_price']/total*100:.1f}%)")
        print(f"   'Kupec znan' status: {stats['buyer_known']} documents")
        print(f"   High confidence (≥0.7): {stats['high_confidence']} ({stats['high_confidence']/total*100:.1f}%)")

        total_plots = sum(len(r['plots']) for r in results)
        total_areas = sum(len([p for p in r['plots'] if p.get('area_m2')]) for r in results)
        print(f"\n📈 Data Points:")
        print(f"   Total plots extracted: {total_plots}")
        print(f"   Plots with areas: {total_areas}")

        print(f"\n💾 Results saved to: {output_file}")
        print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
        print("="*80)


def main():
    """Main entry point"""
    extractor = EnhancedExtractor()

    ocr_dir = Path("data/ocr_texts")
    output_file = Path("data/enhanced_extraction.json")

    # Process all OCR texts
    extractor.process_batch(ocr_dir, output_file)


if __name__ == "__main__":
    main()

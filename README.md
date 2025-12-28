# Občinski razpisi - Kmetijska zemljišča

Samodejno posodobljen pregled ponudb za kmetijska zemljišča iz e-Uprava oglasne deske.

## 🌐 Live Dashboard

👉 **[https://kmetijska-zemljisca.datatart.com](https://kmetijska-zemljisca.datatart.com)**

## 📊 Kaj prikazuje?

Dashboard prikazuje aktivne ponudbe za prodajo in najem kmetijskih zemljišč, objavljene na [e-Uprava oglasni deski](https://e-uprava.gov.si/si/e-uprava/oglasnadeska.html).

### Podatki vključujejo:
- **Številko dokumenta** - direktna povezava na podrobnosti objave
- **Upravno enoto** - 56 različnih upravnih enot po Sloveniji
- **Katastrsko občino** - kod in ime KO (kjer je na voljo)
- **Datum objave** - kdaj je bila ponudba objavljena
- **Veljavnost** - do kdaj je ponudba aktivna
- **PDF dokument** - neposredna povezava do PDF-ja

### Funkcionalnosti:
- 🔍 **Filtriranje po upravni enoti** - dropdown z vsemi 56 UE
- 🔎 **Iskanje** - išči po upravni enoti ali katastrski občini
- 📊 **Statistika** - število aktivnih ponudb, pokritost s KO podatki
- 📱 **Odzivna zasnova** - deluje na mobilnih napravah

## 🤖 Samodejno posodabljanje

Dashboard se samodejno posodablja **vsak dan ob 6:00 UTC** (7:00 CET, 8:00 CEST) preko GitHub Actions.

### Kako deluje:
1. **Scraping** - `scrape_fresh_dashboard.py` prenese podatke iz e-Uprava RSS feed-a in podrobnih strani
2. **Generiranje** - `generate_fresh_dashboard.py` ustvari HTML dashboard
3. **Commit** - GitHub Actions commitne spremembe v repozitorij
4. **Deployment** - Avtomatsko objavljeno na datatart.com

## 🛠️ Lokalni razvoj

### Zahteve:
```bash
# Namesti uv (če še nimaš)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Namesti dependencies
uv pip install requests beautifulsoup4 lxml
```

### Pridobi najnovejše podatke:
```bash
python scrape_fresh_dashboard.py
```

### Generiraj dashboard:
```bash
python generate_fresh_dashboard.py
```

### Odpri dashboard:
```bash
open fresh_agricultural_dashboard.html
# ali
open index.html
```

## 📁 Struktura projekta

```
.
├── scrape_fresh_dashboard.py          # Scraper za e-Uprava podatke
├── generate_fresh_dashboard.py        # Generator HTML dashboard-a
├── index.html                         # Glavni dashboard (hosting)
├── data/
│   ├── fresh_agricultural_offers.json # Scraped podatki
│   └── official_ko_list.json         # Uraden seznam KO kod
├── pyproject.toml                     # Python dependencies (uv)
└── .github/
    └── workflows/
        └── update-dashboard.yml       # GitHub Actions workflow
```

## 📈 Statistika

- **~522** aktivnih ponudb (spremenljivo)
- **78.9%** pokritost s podatki o katastrski občini
- **56** upravnih enot
- **299** različnih katastrskih občin

## 🔗 Viri podatkov

- **e-Uprava oglasna deska**: https://e-uprava.gov.si/si/e-uprava/oglasnadeska.html
- **Statistični urad RS (KO liste)**: https://www.stat.si/Klasje/Klasje/Tabela/6415

## 📝 Licenca

Podatki so javno dostopni preko e-Uprava portala. Ta projekt le agregira in prikazuje javno dostopne informacije.

---

**Zadnja posodobitev**: Samodejno posodobljeno vsak dan ob 6:00 UTC

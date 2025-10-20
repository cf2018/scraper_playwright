# Google Maps Business Scraper & Dashboard

A comprehensive Python-based system for scraping business information from Google Maps and managing the data through a web dashboard.

## Files

### Weather Scraping
- `get_ba_weather_playwright.py` - Scrapes weather information for Buenos Aires from Google
- `requirements.txt` - Python dependencies

### Plumber Data Extraction
- `scrape_plomeros_maps.py` - Automated script to scrape plumber information from Google Maps
- `plomeros_buenos_aires.json` - Extracted data for 10 plumbers in Buenos Aires

## Plumber Data Structure

The JSON file contains the following information for each plumber:
- **name**: Business name
- **phone**: Contact phone number
- **url**: Website URL (when available)
- **email**: Email address (currently null as not available in Google Maps)
- **address**: Business address
- **rating**: Google Maps star rating
- **reviews**: Number of Google reviews
- **hours**: Business operating hours
- **type**: Type of plumbing service

## Sample Plumber Data

The `plomeros_buenos_aires.json` file contains information for 10 plumbers including:

1. **Ebro Desobstrucciones SRL** - 4.7★ (210 reviews) - 24/7 service
2. **Industrias Kyster S.A** - 4.9★ (7 reviews) - Pump supplier
3. **Eolo Construcciones Plomeros/Gasistas/Electric** - 4.9★ (380 reviews)
4. **Plomero Express** - 4.6★ (516 reviews)
5. **Javier Plomero Gasista Matriculado** - 4.8★ (479 reviews)

And 5 more qualified plumbers with contact information and ratings.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

## Usage

### Run Weather Scraper
```bash
python get_ba_weather_playwright.py
```

### Run Plumber Scraper
```bash
python scrape_plomeros_maps.py
```

## Data Extraction Results

Successfully extracted complete information for 10 plumbers in Buenos Aires including:
- Contact details (phone numbers)
- Business websites
- Physical addresses
- Customer ratings and review counts
- Operating hours
- Service categories

The data is saved in JSON format for easy integration with other applications.

# Contact Information Extractor

A generic Playwright-based tool for extracting WhatsApp, email, and Instagram contact information from any website. This script analyzes both the main page and automatically discovers and searches contact pages for comprehensive contact information extraction.

## Features

- **Multi-page Analysis**: Automatically finds and analyzes contact pages
- **Comprehensive Extraction**: Extracts emails, WhatsApp numbers, Instagram profiles, and phone numbers
- **Smart Detection**: Uses context-aware patterns to distinguish WhatsApp from regular phone numbers
- **Robust Parsing**: Handles various URL formats and text patterns
- **JSON Output**: Structured output with detailed extraction metadata
- **Flexible Usage**: Command-line interface with customizable options

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

## Usage

### Basic Usage
```bash
python extract_contact_info.py <website_url>
```

### Examples
```bash
# Extract contacts from a website
python extract_contact_info.py http://www.librerialasflores.com.ar/

# Specify custom output filename
python extract_contact_info.py https://example.com --output example_contacts.json

# Run with visible browser (non-headless)
python extract_contact_info.py https://example.com --headless false

# Set custom timeout (in milliseconds)
python extract_contact_info.py https://example.com --timeout 60000
```

## Command Line Options

- `url`: Website URL to extract contacts from (required)
- `--output`, `-o`: Custom output JSON filename (optional)
- `--headless`: Run browser in headless mode (default: True)
- `--timeout`: Page load timeout in milliseconds (default: 30000)

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "website": "http://example.com",
  "extraction_date": "2025-07-04T10:51:06.947586",
  "pages_analyzed": [
    {
      "url": "http://example.com",
      "type": "main_page",
      "contacts_found": {
        "url": "http://example.com",
        "emails": ["contact@example.com"],
        "whatsapp": ["+1234567890"],
        "instagram": ["https://instagram.com/example"],
        "phone_numbers": ["+1234567890"]
      }
    }
  ],
  "contacts": {
    "emails": ["contact@example.com"],
    "whatsapp": ["+1234567890"],
    "instagram": ["https://instagram.com/example"],
    "phone_numbers": ["+1234567890"]
  }
}
```

## What It Extracts

### Email Addresses
- Standard email formats (user@domain.com)
- Mailto links
- Email addresses in text content

### WhatsApp Numbers
- WhatsApp web links (wa.me, api.whatsapp.com)
- Phone numbers with WhatsApp context
- Various international phone number formats

### Instagram Profiles
- Instagram profile links
- Instagram usernames with @ symbol

### Phone Numbers
- General phone numbers not identified as WhatsApp
- International and local formats
- Numbers from tel: links

## How It Works

1. **Main Page Analysis**: Extracts contact information from the homepage
2. **Contact Page Discovery**: Automatically finds links to contact pages using common indicators:
   - "contacto", "contact", "contato", "kontakt"
   - "contact-us", "contact_us", "contactanos"
   - "get-in-touch", "reach-us", "connect"
3. **Multi-source Extraction**: Analyzes HTML content, text content, and link attributes
4. **Smart Classification**: Uses context and patterns to classify phone numbers as WhatsApp or regular phones
5. **Deduplication**: Removes duplicate entries across all analyzed pages

## Example Output

Running the script on `http://www.librerialasflores.com.ar/` produces:

```
============================================================
CONTACT EXTRACTION SUMMARY
============================================================
Website: http://www.librerialasflores.com.ar/
Pages analyzed: 4
Emails found: 1
WhatsApp numbers: 6
Instagram profiles: 1
Phone numbers: 3

Emails:
  - ventas@librerialasflores.com.ar

WhatsApp:
  - +541131784331
  - +541123739300
  - +541158284211

Instagram:
  - https://instagram.com/lasflores.librerias
```

## Error Handling

The script includes comprehensive error handling:
- Graceful handling of page load failures
- Timeout management for slow-loading pages
- Validation of extracted contact information
- Detailed logging of extraction process

## Limitations

- Requires JavaScript-enabled pages (uses Playwright)
- May not work with heavily protected or CAPTCHA-enabled sites
- Extraction accuracy depends on website structure and content
- Some contact information may be embedded in images (not extracted)

## Contributing

Feel free to improve the extraction patterns, add new contact types, or enhance the discovery mechanisms.

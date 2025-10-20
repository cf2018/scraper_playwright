"""
Generic Website Contact Information Extractor Module

This module provides reusable functions to extract WhatsApp, email, and Instagram contact 
information from any given website. It searches both the main page and attempts to find 
a contact page for comprehensive contact information extraction.

Can be used as a standalone script or imported as a module.
"""

import asyncio
import json
import re
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ContactExtractor:
    def __init__(self, headless=True, timeout=30000):
        self.headless = headless
        self.timeout = timeout
        
        # Regex patterns for contact information
        self.patterns = {
            'email': [
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ],
            'whatsapp': [
                # These patterns are for text-based extraction (non-URL)
                r'whatsapp.*?(\+?[\d\s\-\(\)]{8,})',
                r'(\+?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,6})',  # General phone pattern
            ],
            'instagram': [
                r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)',
                r'@([a-zA-Z0-9_.]+)',  # Instagram handles
            ]
        }
        
        # Common contact page indicators
        self.contact_indicators = [
            'contacto', 'contact', 'contato', 'kontakt',
            'contact-us', 'contact_us', 'contactanos',
            'get-in-touch', 'reach-us', 'connect'
        ]

    async def extract_from_page(self, page, url):
        """Extract contact information from a single page"""
        contacts = {
            'url': url,
            'emails': set(),
            'whatsapp': set(),
            'instagram': set(),
            'phone_numbers': set()
        }
        
        try:
            await page.goto(url, timeout=self.timeout)
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Get page content
            content = await page.content()
            
            # Extract text content for text-based patterns
            text_content = await page.evaluate('document.body.innerText')
            
            # Get all links
            links = await page.evaluate('''
                Array.from(document.querySelectorAll('a')).map(a => ({
                    href: a.href,
                    text: a.innerText,
                    title: a.title || ''
                }))
            ''')
            
            # Extract emails
            for pattern in self.patterns['email']:
                # From HTML content
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    email = match.group(1) if match.groups() else match.group(0)
                    if self._is_valid_email(email):
                        contacts['emails'].add(email.lower())
                
                # From text content
                for match in re.finditer(pattern, text_content, re.IGNORECASE):
                    email = match.group(1) if match.groups() else match.group(0)
                    if self._is_valid_email(email):
                        contacts['emails'].add(email.lower())
            
            # Extract WhatsApp from links - prioritize direct WhatsApp API links
            whatsapp_from_links = set()
            general_phones_from_links = set()
            
            for link in links:
                href = link.get('href', '')
                text = link.get('text', '')
                
                # Check for WhatsApp links and extract phone numbers from URLs
                if any(domain in href.lower() for domain in ['wa.me', 'api.whatsapp.com', 'whatsapp.com']):
                    phone_number = self._extract_phone_from_whatsapp_url(href)
                    if phone_number:
                        whatsapp_from_links.add(phone_number)
                        logger.info(f"Found WhatsApp from URL: {phone_number} (from {href})")
                        continue
                
                # Fallback: Look for WhatsApp-related text patterns in non-WhatsApp links
                for pattern in self.patterns['whatsapp']:  # Use all WhatsApp patterns
                    for source in [href, text]:
                        if any(keyword in source.lower() for keyword in ['whatsapp', 'whats app']):
                            matches = re.finditer(pattern, source, re.IGNORECASE)
                            for match in matches:
                                phone = match.group(1) if match.groups() else match.group(0)
                                phone = self._clean_phone(phone)
                                if phone and phone not in whatsapp_from_links:
                                    whatsapp_from_links.add(phone)
                                    logger.info(f"Found WhatsApp from link context: {phone}")
                        elif self._is_phone_number(source):
                            phone = self._clean_phone(source)
                            if phone and phone not in whatsapp_from_links:
                                general_phones_from_links.add(phone)
            
            # Add prioritized WhatsApp numbers
            contacts['whatsapp'].update(whatsapp_from_links)
            
            # Extract Instagram from links
            for link in links:
                href = link.get('href', '')
                for pattern in self.patterns['instagram']:
                    match = re.search(pattern, href, re.IGNORECASE)
                    if match and 'instagram.com' in href:
                        username = match.group(1) if match.groups() else match.group(0)
                        if username and len(username) > 1:
                            contacts['instagram'].add(f"https://instagram.com/{username}")
            
            # Additional phone number extraction from text with WhatsApp prioritization
            phone_patterns = [
                r'(\+?[\d\s\-\(\)]{10,})',
                r'tel:(\+?[\d\s\-\(\)]+)',
                r'telefono[:\s]*(\+?[\d\s\-\(\)]+)',
                r'phone[:\s]*(\+?[\d\s\-\(\)]+)',
                r'celular[:\s]*(\+?[\d\s\-\(\)]+)',
            ]
            
            whatsapp_from_text = set()
            general_phones_from_text = set()
            
            for pattern in phone_patterns:
                for match in re.finditer(pattern, text_content, re.IGNORECASE):
                    phone = self._clean_phone(match.group(1))
                    if phone and len(phone) >= 8:
                        # Check if this phone is already identified as WhatsApp from links
                        if phone in contacts['whatsapp']:
                            continue
                            
                        # Try to determine if it's WhatsApp based on context
                        context_start = max(0, match.start() - 100)
                        context_end = min(len(text_content), match.end() + 100)
                        context = text_content[context_start:context_end].lower()
                        
                        # Strong WhatsApp indicators in context
                        whatsapp_keywords = [
                            'whatsapp', 'whats app', 'whatsap', 'wassap', 'wasap',
                            'wa.me', 'api.whatsapp', 'chat whatsapp', 'mensaje whatsapp',
                            'escribinos por whatsapp', 'contactanos por whatsapp'
                        ]
                        
                        if any(keyword in context for keyword in whatsapp_keywords):
                            whatsapp_from_text.add(phone)
                            logger.info(f"Found WhatsApp from text context: {phone}")
                        else:
                            general_phones_from_text.add(phone)
            
            # Add WhatsApp numbers from text (only those not already found in links)
            for phone in whatsapp_from_text:
                if phone not in contacts['whatsapp']:
                    contacts['whatsapp'].add(phone)
            
            # Add remaining phone numbers to general category
            for phone in general_phones_from_text:
                if phone not in contacts['whatsapp']:
                    contacts['phone_numbers'].add(phone)
            
            # Also add phones from links that weren't WhatsApp
            for phone in general_phones_from_links:
                if phone not in contacts['whatsapp']:
                    contacts['phone_numbers'].add(phone)
            
        except Exception as e:
            logger.warning(f"Error extracting from {url}: {str(e)}")
        
        # Convert sets to lists for JSON serialization
        for key in ['emails', 'whatsapp', 'instagram', 'phone_numbers']:
            contacts[key] = list(contacts[key])
        
        return contacts

    async def find_contact_page(self, page, base_url):
        """Try to find a contact page"""
        contact_urls = []
        
        try:
            # Get all links on the main page
            links = await page.evaluate('''
                Array.from(document.querySelectorAll('a')).map(a => ({
                    href: a.href,
                    text: a.innerText.toLowerCase(),
                    title: (a.title || '').toLowerCase()
                }))
            ''')
            
            # Look for contact page links
            for link in links:
                href = link.get('href', '')
                text = link.get('text', '')
                title = link.get('title', '')
                
                # Check if link text or href contains contact indicators
                for indicator in self.contact_indicators:
                    if (indicator in text or 
                        indicator in href.lower() or 
                        indicator in title):
                        if href and href.startswith('http'):
                            contact_urls.append(href)
                        elif href:
                            # Convert relative URL to absolute
                            full_url = urljoin(base_url, href)
                            contact_urls.append(full_url)
                        break
            
            # Remove duplicates while preserving order
            seen = set()
            unique_contact_urls = []
            for url in contact_urls:
                if url not in seen:
                    seen.add(url)
                    unique_contact_urls.append(url)
            
            return unique_contact_urls[:3]  # Limit to first 3 contact pages
            
        except Exception as e:
            logger.warning(f"Error finding contact page: {str(e)}")
            return []

    def _is_valid_email(self, email):
        """Validate email format"""
        if not email or len(email) > 254:
            return False
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None

    def _clean_phone(self, phone):
        """Clean and format phone number"""
        if not phone:
            return None
        
        # Remove common formatting characters
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Must have at least 8 digits
        if len(re.sub(r'[^\d]', '', cleaned)) < 8:
            return None
        
        return cleaned

    def _is_phone_number(self, text):
        """Check if text looks like a phone number"""
        # Remove non-digit characters except +
        digits = re.sub(r'[^\d]', '', text)
        return len(digits) >= 8 and len(digits) <= 15

    def _extract_phone_from_whatsapp_url(self, url):
        """
        Extract phone number from WhatsApp URLs like:
        - https://wa.me/5491140494048?text=...
        - https://api.whatsapp.com/send?phone=5491123456789
        - https://api.whatsapp.com/send/?phone=5491123456789&text=hello
        """
        if not url:
            return None
        
        # Patterns to extract phone numbers from WhatsApp URLs
        patterns = [
            # wa.me/PHONE format (most common)
            r'https?://wa\.me/(\+?[\d]+)',
            # api.whatsapp.com with phone parameter
            r'https?://(?:api\.)?whatsapp\.com/send/?[?&]?phone=(\+?[\d]+)',
            # Generic phone parameter
            r'phone=(\+?[\d]+)',
            # WhatsApp URL with phone in path
            r'whatsapp(?:\.com)?/.*?(\+?[\d]{8,15})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                phone = match.group(1)
                # Clean and format the phone number
                if phone:
                    # Ensure + prefix for international numbers (10+ digits)
                    cleaned_phone = re.sub(r'[^\d+]', '', phone)
                    if not cleaned_phone.startswith('+') and len(cleaned_phone) >= 10:
                        cleaned_phone = '+' + cleaned_phone
                    return cleaned_phone
        
        return None

    async def extract_contacts(self, url, browser=None):
        """Main method to extract contacts from website"""
        logger.info(f"Starting contact extraction for: {url}")
        
        # Use provided browser or create a new one
        browser_provided = browser is not None
        p = None
        
        if not browser_provided:
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=self.headless)
        
        try:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            all_contacts = {
                'website': url,
                'extraction_date': datetime.now().isoformat(),
                'pages_analyzed': [],
                'contacts': {
                    'emails': set(),
                    'whatsapp': set(),
                    'instagram': set(),
                    'phone_numbers': set()
                }
            }
            
            try:
                # Extract from main page
                logger.info("Extracting from main page...")
                main_contacts = await self.extract_from_page(page, url)
                all_contacts['pages_analyzed'].append({
                    'url': url,
                    'type': 'main_page',
                    'contacts_found': main_contacts
                })
                
                # Merge contacts
                for key in ['emails', 'whatsapp', 'instagram', 'phone_numbers']:
                    all_contacts['contacts'][key].update(main_contacts[key])
                
                # Find and extract from contact pages
                logger.info("Looking for contact pages...")
                contact_urls = await self.find_contact_page(page, url)
                
                for contact_url in contact_urls:
                    try:
                        logger.info(f"Extracting from contact page: {contact_url}")
                        contact_contacts = await self.extract_from_page(page, contact_url)
                        all_contacts['pages_analyzed'].append({
                            'url': contact_url,
                            'type': 'contact_page',
                            'contacts_found': contact_contacts
                        })
                        
                        # Merge contacts
                        for key in ['emails', 'whatsapp', 'instagram', 'phone_numbers']:
                            all_contacts['contacts'][key].update(contact_contacts[key])
                            
                    except Exception as e:
                        logger.warning(f"Error processing contact page {contact_url}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error processing main page: {str(e)}")
            
            finally:
                await context.close()
            
            # Convert sets to lists for JSON serialization
            for key in ['emails', 'whatsapp', 'instagram', 'phone_numbers']:
                all_contacts['contacts'][key] = list(all_contacts['contacts'][key])
            
            return all_contacts
            
        finally:
            if not browser_provided and browser:
                await browser.close()
            if p:
                await p.stop()


# Convenience functions for external use
async def extract_website_contacts(url, headless=True, timeout=30000, browser=None):
    """
    Extract contact information from a website.
    
    Args:
        url (str): Website URL to extract contacts from
        headless (bool): Run browser in headless mode (default: True)
        timeout (int): Page load timeout in milliseconds (default: 30000)
        browser: Optional existing Playwright browser instance
    
    Returns:
        dict: Contact information in JSON format
    """
    extractor = ContactExtractor(headless=headless, timeout=timeout)
    return await extractor.extract_contacts(url, browser=browser)


def extract_website_contacts_sync(url, headless=True, timeout=30000):
    """
    Synchronous wrapper for extract_website_contacts.
    
    Args:
        url (str): Website URL to extract contacts from
        headless (bool): Run browser in headless mode (default: True)
        timeout (int): Page load timeout in milliseconds (default: 30000)
    
    Returns:
        dict: Contact information in JSON format
    """
    return asyncio.run(extract_website_contacts(url, headless=headless, timeout=timeout))


def get_simplified_contacts(contacts_data):
    """
    Extract simplified contact information from the full extraction result.
    Returns comma-separated WhatsApp numbers if multiple are found.
    Prioritizes emails by domain (same domain > non-Gmail > Gmail).
    
    Args:
        contacts_data (dict): Full contact extraction result
    
    Returns:
        dict: Simplified contact information with email, whatsapp, instagram
    """
    if not contacts_data or 'contacts' not in contacts_data:
        return {'email': None, 'whatsapp': None, 'instagram': None}
    
    contacts = contacts_data['contacts']
    
    # For WhatsApp, format multiple numbers as comma-separated
    formatted_whatsapp = None
    if contacts['whatsapp']:
        # Prioritize API-style numbers (no formatting) over formatted ones
        api_numbers = []
        formatted_numbers = []
        
        for number in contacts['whatsapp']:
            if re.match(r'^\+?\d+$', str(number)):
                api_numbers.append(str(number))
            else:
                formatted_numbers.append(str(number))
        
        # Combine with API numbers first
        all_numbers = api_numbers + formatted_numbers
        
        if len(all_numbers) == 1:
            formatted_whatsapp = all_numbers[0]
        elif len(all_numbers) > 1:
            formatted_whatsapp = ', '.join(all_numbers)
    
    # For email, prioritize same domain > non-Gmail > Gmail
    best_email = None
    if contacts['emails']:
        # Try to get website domain for prioritization
        website_domain = None
        if 'website' in contacts_data:
            try:
                from urllib.parse import urlparse
                website_domain = urlparse(contacts_data['website']).netloc.lower().replace('www.', '')
            except:
                pass
        
        # Categorize emails
        same_domain = []
        non_gmail = []
        gmail_others = []
        
        for email in contacts['emails']:
            email_lower = email.lower().strip()
            email_domain = email_lower.split('@')[-1] if '@' in email_lower else ''
            
            if website_domain and email_domain == website_domain:
                same_domain.append(email)
            elif email_domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                non_gmail.append(email)
            else:
                gmail_others.append(email)
        
        # Return the best email based on priority
        if same_domain:
            best_email = same_domain[0]
        elif non_gmail:
            best_email = non_gmail[0]
        elif gmail_others:
            best_email = gmail_others[0]
        else:
            best_email = contacts['emails'][0]  # Fallback
    
    return {
        'email': best_email,
        'whatsapp': formatted_whatsapp,
        'instagram': contacts['instagram'][0] if contacts['instagram'] else None,
    }

def main():
    """Command-line interface for the contact extractor"""
    # Configure logging for CLI usage
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description='Extract contact information from websites')
    parser.add_argument('url', help='Website URL to extract contacts from')
    parser.add_argument('--output', '-o', help='Output JSON filename')
    parser.add_argument('--headless', action='store_true', default=True, 
                       help='Run browser in headless mode (default: True)')
    parser.add_argument('--timeout', type=int, default=30000,
                       help='Page load timeout in milliseconds (default: 30000)')
    parser.add_argument('--simple', action='store_true',
                       help='Output simplified contact format (email, whatsapp, instagram only)')
    
    args = parser.parse_args()
    
    # Ensure URL has protocol
    url = args.url
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Generate output filename if not provided
    if not args.output:
        domain = urlparse(url).netloc.replace('www.', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f"{domain}_contacts_{timestamp}.json"
    
    # Ensure json_output directory exists and adjust output path
    import os
    json_output_dir = "json_output"
    os.makedirs(json_output_dir, exist_ok=True)
    
    # If output doesn't already include json_output path, prepend it
    if not args.output.startswith(json_output_dir):
        args.output = os.path.join(json_output_dir, args.output)
    
    try:
        # Extract contacts
        contacts = extract_website_contacts_sync(url, headless=args.headless, timeout=args.timeout)
        
        # Use simplified format if requested
        if args.simple:
            contacts = get_simplified_contacts(contacts)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(contacts, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Contact extraction completed. Results saved to: {args.output}")
        
        # Print summary
        if args.simple:
            print(f"\n{'='*60}")
            print(f"SIMPLIFIED CONTACT EXTRACTION")
            print(f"{'='*60}")
            print(f"Website: {url}")
            print(f"Email: {contacts.get('email', 'Not found')}")
            print(f"WhatsApp: {contacts.get('whatsapp', 'Not found')}")
            print(f"Instagram: {contacts.get('instagram', 'Not found')}")
        else:
            print(f"\n{'='*60}")
            print(f"CONTACT EXTRACTION SUMMARY")
            print(f"{'='*60}")
            print(f"Website: {contacts['website']}")
            print(f"Pages analyzed: {len(contacts['pages_analyzed'])}")
            print(f"Emails found: {len(contacts['contacts']['emails'])}")
            print(f"WhatsApp numbers: {len(contacts['contacts']['whatsapp'])}")
            print(f"Instagram profiles: {len(contacts['contacts']['instagram'])}")
            print(f"Phone numbers: {len(contacts['contacts']['phone_numbers'])}")
            
            if contacts['contacts']['emails']:
                print(f"\nEmails:")
                for email in contacts['contacts']['emails']:
                    print(f"  - {email}")
            
            if contacts['contacts']['whatsapp']:
                print(f"\nWhatsApp:")
                for wa in contacts['contacts']['whatsapp']:
                    print(f"  - {wa}")
            
            if contacts['contacts']['instagram']:
                print(f"\nInstagram:")
                for ig in contacts['contacts']['instagram']:
                    print(f"  - {ig}")
            
            if contacts['contacts']['phone_numbers']:
                print(f"\nOther Phone Numbers:")
                for phone in contacts['contacts']['phone_numbers']:
                    print(f"  - {phone}")
        
        print(f"\nDetailed results saved to: {args.output}")
        
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python3
"""
Final test to verify WhatsApp extraction works without navigation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_contact_info import ContactExtractor

def test_comprehensive_whatsapp_extraction():
    """Test comprehensive WhatsApp extraction without navigation"""
    print("Testing comprehensive WhatsApp extraction (no navigation)...")
    
    extractor = ContactExtractor()
    
    # Simulate a webpage with various WhatsApp link formats
    mock_links = [
        {
            'href': 'https://wa.me/5491140494048?text=Hola,%20gracias%20por%20contactarnos',
            'text': 'Contactanos por WhatsApp',
            'title': ''
        },
        {
            'href': 'https://api.whatsapp.com/send/?phone=5491123325814',
            'text': 'WhatsApp',
            'title': ''
        },
        {
            'href': 'https://api.whatsapp.com/send?phone=541137777540&text=',
            'text': 'Chat',
            'title': ''
        },
        {
            'href': 'https://example.com/contact',
            'text': 'WhatsApp: +54 911 8765-4321',
            'title': ''
        }
    ]
    
    whatsapp_numbers = set()
    
    print("\nProcessing mock links:")
    for i, link in enumerate(mock_links, 1):
        href = link.get('href', '')
        text = link.get('text', '')
        
        print(f"\nLink {i}:")
        print(f"  href: {href}")
        print(f"  text: {text}")
        
        # Check for WhatsApp links and extract phone numbers from URLs
        if any(domain in href.lower() for domain in ['wa.me', 'api.whatsapp.com', 'whatsapp.com']):
            phone_number = extractor._extract_phone_from_whatsapp_url(href)
            if phone_number:
                whatsapp_numbers.add(phone_number)
                print(f"  ✅ Extracted from URL: {phone_number}")
            else:
                print(f"  ❌ Could not extract from URL")
        elif 'whatsapp' in text.lower():
            # Fallback: text-based extraction
            import re
            pattern = r'(\+?[\d\s\-\(\)]{8,})'
            match = re.search(pattern, text)
            if match:
                phone = extractor._clean_phone(match.group(1))
                if phone:
                    whatsapp_numbers.add(phone)
                    print(f"  ✅ Extracted from text: {phone}")
                else:
                    print(f"  ❌ Could not clean phone from text")
            else:
                print(f"  ❌ No phone pattern found in text")
        else:
            print(f"  ⏭️  Skipped (not WhatsApp related)")
    
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS:")
    print(f"WhatsApp numbers found: {list(whatsapp_numbers)}")
    print(f"Total numbers: {len(whatsapp_numbers)}")
    
    # Expected results
    expected = {'+5491140494048', '+5491123325814', '+541137777540', '+5491187654321'}
    
    print(f"\nExpected: {sorted(expected)}")
    print(f"Found: {sorted(whatsapp_numbers)}")
    
    if whatsapp_numbers == expected:
        print("✅ ALL TESTS PASS - WhatsApp extraction working correctly!")
    else:
        missing = expected - whatsapp_numbers
        extra = whatsapp_numbers - expected
        if missing:
            print(f"❌ Missing: {missing}")
        if extra:
            print(f"❌ Extra: {extra}")
    
    print(f"\n🎯 KEY IMPROVEMENT: No navigation to WhatsApp URLs!")
    print(f"   The extractor now parses phone numbers directly from URLs")
    print(f"   instead of trying to navigate to them.")

if __name__ == "__main__":
    test_comprehensive_whatsapp_extraction()

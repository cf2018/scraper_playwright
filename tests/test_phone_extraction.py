#!/usr/bin/env python3
"""
Test the improved phone number extraction logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape_businesses_maps import BusinessScraper

def test_phone_extraction():
    """Test phone number extraction from various text formats"""
    print("Testing improved phone number extraction...")
    
    scraper = BusinessScraper("test")
    
    # Test cases based on real Google Maps data
    test_cases = [
        {
            'text': 'Teléfono: 0385 421-4413',
            'expected': '0385 421-4413',
            'description': 'Standard Argentine format (Santiago del Estero)'
        },
        {
            'text': '011 4371-4927',
            'expected': '011 4371-4927',
            'description': 'Buenos Aires format'
        },
        {
            'text': '+54 11 4123-4567',
            'expected': '+54 11 4123-4567',
            'description': 'International format'
        },
        {
            'text': '4321-5678',
            'expected': '4321-5678',
            'description': 'Local number only'
        },
        {
            'text': 'Contact us: 0261 423-1234 for more info',
            'expected': '0261 423-1234',
            'description': 'Number in context'
        },
        {
            'text': 'Email: contact@example.com',
            'expected': None,
            'description': 'Should not extract from email'
        },
        {
            'text': '',
            'expected': None,
            'description': 'Empty text'
        }
    ]
    
    print(f"\nTesting _extract_phone_from_text:")
    for i, test_case in enumerate(test_cases, 1):
        result = scraper._extract_phone_from_text(test_case['text'])
        
        print(f"\nTest {i}: {test_case['description']}")
        print(f"  Input: '{test_case['text']}'")
        print(f"  Expected: {test_case['expected']}")
        print(f"  Result: {result}")
        
        if result == test_case['expected']:
            print("  ✅ PASS")
        else:
            print("  ❌ FAIL")
    
    # Test tel: link extraction
    tel_test_cases = [
        {
            'tel_href': 'tel:03854214413',
            'expected': '0385 421-4413',
            'description': 'Standard tel link'
        },
        {
            'tel_href': 'tel:+541143714927',
            'expected': '+541143714927',
            'description': 'International tel link'
        },
        {
            'tel_href': 'tel:1234567890',
            'expected': '1234 567-890',
            'description': '10-digit tel link'
        },
        {
            'tel_href': 'not a tel link',
            'expected': None,
            'description': 'Invalid tel link'
        }
    ]
    
    print(f"\nTesting _extract_phone_from_tel_link:")
    for i, test_case in enumerate(tel_test_cases, 1):
        result = scraper._extract_phone_from_tel_link(test_case['tel_href'])
        
        print(f"\nTest {i}: {test_case['description']}")
        print(f"  Input: '{test_case['tel_href']}'")
        print(f"  Expected: {test_case['expected']}")
        print(f"  Result: {result}")
        
        if result == test_case['expected']:
            print("  ✅ PASS")
        else:
            print("  ❌ FAIL")

if __name__ == "__main__":
    test_phone_extraction()

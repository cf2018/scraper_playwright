#!/usr/bin/env python3
"""
Test script for the refactored extract_contact_info module
"""

import asyncio
import sys
import os

# Add the current directory to path to import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_contact_info import extract_website_contacts_sync, get_simplified_contacts

def test_module_usage():
    """Test using the module programmatically"""
    print("Testing module usage...")
    
    url = "http://www.librerialasflores.com.ar/"
    
    # Test synchronous function
    print(f"Extracting contacts from: {url}")
    contacts = extract_website_contacts_sync(url)
    
    print(f"Full extraction result keys: {list(contacts.keys())}")
    print(f"Found {len(contacts['contacts']['emails'])} emails")
    print(f"Found {len(contacts['contacts']['whatsapp'])} WhatsApp numbers")
    print(f"Found {len(contacts['contacts']['instagram'])} Instagram profiles")
    
    # Test simplified extraction
    simplified = get_simplified_contacts(contacts)
    print(f"\nSimplified contacts: {simplified}")
    
    return contacts

if __name__ == "__main__":
    test_module_usage()

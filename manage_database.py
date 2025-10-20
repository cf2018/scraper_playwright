#!/usr/bin/env python3
"""
Business Database Management Tool

This script provides functionality to view, filter, and manage the scraped business data
stored in MongoDB.
"""

import argparse
import json
from datetime import datetime
from database import BusinessDatabase, show_database_stats

def list_businesses(keyword=None, contacted=None, limit=100):
    """List businesses with optional filtering."""
    db = BusinessDatabase()
    try:
        print("\n" + "="*60)
        print("📋 BUSINESS LISTINGS")
        print("="*60)
        
        # Apply filters
        filter_desc = []
        if keyword:
            filter_desc.append(f"keyword: '{keyword}'")
        if contacted is not None:
            status = "contacted" if contacted else "not contacted"
            filter_desc.append(f"status: {status}")
        
        if filter_desc:
            print(f"Filters: {', '.join(filter_desc)}")
        else:
            print("No filters applied (showing all businesses)")
        
        businesses = db.get_businesses(keyword, contacted, limit)
        
        if not businesses:
            print("❌ No businesses found matching the criteria")
            return
        
        print(f"Found {len(businesses)} businesses:\n")
        
        for i, business in enumerate(businesses, 1):
            status = "✅ Contacted" if business.get('contacted', False) else "⏳ Not contacted"
            print(f"{i}. {business.get('name', 'Unknown')}")
            print(f"   📞 Phone: {business.get('phone', 'N/A')}")
            print(f"   🌐 Website: {business.get('website', 'N/A')}")
            print(f"   📧 Email: {business.get('email', 'N/A')}")
            print(f"   📱 WhatsApp: {business.get('whatsapp', 'N/A')}")
            print(f"   📍 Address: {business.get('address', 'N/A')}")
            print(f"   ⭐ Rating: {business.get('rating', 'N/A')} ({business.get('reviews', 0)} reviews)")
            print(f"   🔍 Search: {business.get('search_keyword', 'N/A')}")
            print(f"   📅 Added: {business.get('created_at', 'N/A')}")
            print(f"   {status}")
            print(f"   ID: {business.get('_id', 'N/A')}")
            print()
            
    finally:
        db.close()

def list_keywords():
    """List all search keywords in the database."""
    db = BusinessDatabase()
    try:
        print("\n" + "="*50)
        print("🔍 SEARCH KEYWORDS")
        print("="*50)
        
        keywords = db.get_search_keywords()
        
        if not keywords:
            print("❌ No search keywords found")
            return
            
        print(f"Found {len(keywords)} unique search keywords:")
        for i, keyword in enumerate(keywords, 1):
            print(f"{i}. {keyword}")
            
    finally:
        db.close()

def mark_contacted(business_id, contacted=True):
    """Mark a business as contacted or not contacted."""
    db = BusinessDatabase()
    try:
        success = db.mark_contacted(business_id, contacted)
        if success:
            status = "contacted" if contacted else "not contacted"
            print(f"✅ Successfully marked business as {status}")
        else:
            print("❌ Failed to update business contact status")
    finally:
        db.close()

def export_businesses(keyword=None, contacted=None, output_file=None):
    """Export businesses to JSON file."""
    db = BusinessDatabase()
    try:
        businesses = db.get_businesses(keyword, contacted, limit=1000)  # Get up to 1000
        
        if not businesses:
            print("❌ No businesses found to export")
            return
        
        # Generate filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filters = []
            if keyword:
                filters.append(keyword.replace(' ', '_'))
            if contacted is not None:
                filters.append("contacted" if contacted else "not_contacted")
            
            filter_str = "_".join(filters) if filters else "all"
            output_file = f"businesses_export_{filter_str}_{timestamp}.json"
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(businesses, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Exported {len(businesses)} businesses to {output_file}")
        
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Business Database Management Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List businesses command
    list_parser = subparsers.add_parser('list', help='List businesses')
    list_parser.add_argument('--keyword', '-k', help='Filter by search keyword')
    list_parser.add_argument('--contacted', '-c', action='store_true', help='Show only contacted businesses')
    list_parser.add_argument('--not-contacted', '-n', action='store_true', help='Show only not contacted businesses')
    list_parser.add_argument('--limit', '-l', type=int, default=100, help='Maximum number of results (default: 100)')
    
    # List keywords command
    keywords_parser = subparsers.add_parser('keywords', help='List all search keywords')
    
    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # Mark contacted command
    contact_parser = subparsers.add_parser('contact', help='Mark business as contacted')
    contact_parser.add_argument('business_id', help='Business ID to update')
    contact_parser.add_argument('--uncontacted', '-u', action='store_true', help='Mark as not contacted instead')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export businesses to JSON')
    export_parser.add_argument('--keyword', '-k', help='Filter by search keyword')
    export_parser.add_argument('--contacted', '-c', action='store_true', help='Export only contacted businesses')
    export_parser.add_argument('--not-contacted', '-n', action='store_true', help='Export only not contacted businesses')
    export_parser.add_argument('--output', '-o', help='Output file name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            contacted = None
            if args.contacted:
                contacted = True
            elif args.not_contacted:
                contacted = False
            list_businesses(args.keyword, contacted, args.limit)
            
        elif args.command == 'keywords':
            list_keywords()
            
        elif args.command == 'stats':
            show_database_stats()
            
        elif args.command == 'contact':
            mark_contacted(args.business_id, not args.uncontacted)
            
        elif args.command == 'export':
            contacted = None
            if args.contacted:
                contacted = True
            elif args.not_contacted:
                contacted = False
            export_businesses(args.keyword, contacted, args.output)
            
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
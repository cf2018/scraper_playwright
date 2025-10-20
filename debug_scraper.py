#!/usr/bin/env python3
"""
Debug script to test the scraper and understand why it's not reaching max results
"""

import asyncio
from scrape_businesses_maps import BusinessScraper

async def debug_scraper():
    """Test the scraper with detailed debugging"""
    
    test_queries = [
        ("plomeros Buenos Aires", 5),
        ("restaurants Buenos Aires", 8),
        ("dentistas CABA", 10)
    ]
    
    for query, max_results in test_queries:
        print("=" * 80)
        print(f"🧪 TESTING: '{query}' (target: {max_results} results)")
        print("=" * 80)
        
        scraper = BusinessScraper(query)
        
        try:
            businesses = await scraper.scrape_businesses(max_results=max_results)
            
            print(f"\n📊 FINAL RESULTS:")
            print(f"   • Requested: {max_results}")
            print(f"   • Found: {len(businesses)}")
            print(f"   • Duplicates: {scraper.duplicates_found}")
            print(f"   • Success rate: {len(businesses)}/{max_results} ({len(businesses)/max_results*100:.1f}%)")
            
            if len(businesses) < max_results:
                print(f"\n⚠️ SHORTFALL ANALYSIS:")
                total_processed = len(businesses) + scraper.duplicates_found
                print(f"   • Total businesses processed: {total_processed}")
                print(f"   • Missing: {max_results - len(businesses)}")
                
                if scraper.duplicates_found > 0:
                    print(f"   • High duplicate rate: {scraper.duplicates_found}/{total_processed} ({scraper.duplicates_found/total_processed*100:.1f}%)")
                
                if total_processed < max_results:
                    print(f"   • Insufficient business links found by Google Maps")
                
            print(f"\n📋 BUSINESSES FOUND:")
            for i, biz in enumerate(businesses, 1):
                print(f"   {i}. {biz['name']} - {biz.get('phone', 'No phone')}")
            
        except Exception as e:
            print(f"❌ Error testing '{query}': {e}")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(debug_scraper())

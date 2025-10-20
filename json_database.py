"""
JSON-based fallback database for when MongoDB is not available.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

class JSONDatabase:
    """JSON-based database fallback."""
    
    def __init__(self, db_file="businesses_database.json"):
        """Initialize JSON database."""
        self.db_file = db_file
        self.data = {"businesses": [], "metadata": {"created": datetime.utcnow().isoformat()}}
        self._load_data()
    
    def _load_data(self):
        """Load data from JSON file."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                print(f"✅ Loaded JSON database: {len(self.data.get('businesses', []))} businesses")
            except Exception as e:
                print(f"⚠️ Error loading JSON database, starting fresh: {e}")
                
    def _save_data(self):
        """Save data to JSON file."""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)
            return True
        except Exception as e:
            print(f"❌ Error saving JSON database: {e}")
            return False
    
    def save_business(self, business_data: Dict[str, Any], search_keyword: str) -> bool:
        """Save a business to the JSON database."""
        try:
            # Check for duplicates (same name + phone + website)
            name = business_data.get("name", "") or ""
            name = name.strip().lower()
            phone = business_data.get("phone") or ""
            phone = phone.strip() if isinstance(phone, str) else ""
            website = business_data.get("website", "") or ""
            website = website.strip().lower()
            
            for existing in self.data["businesses"]:
                existing_name = (existing.get("name", "") or "").strip().lower()
                existing_phone = existing.get("phone") or ""
                existing_phone = existing_phone.strip() if isinstance(existing_phone, str) else ""
                existing_website = (existing.get("website", "") or "").strip().lower()
                
                if (existing_name == name and
                    existing_phone == phone and
                    existing_website == website):
                    print(f"⚠️ Duplicate business skipped: {business_data.get('name', 'Unknown')}")
                    return False
            
            # Add new business
            document = {
                "_id": str(uuid.uuid4()),
                "name": business_data.get("name", ""),
                "phone": business_data.get("phone", ""),
                "website": business_data.get("website", ""),
                "email": business_data.get("email", ""),
                "whatsapp": business_data.get("whatsapp", ""),
                "instagram": business_data.get("instagram", ""),
                "address": business_data.get("address", ""),
                "rating": business_data.get("rating"),
                "reviews": business_data.get("reviews"),
                "search_keyword": search_keyword.lower().strip(),
                "contacted": False,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.data["businesses"].append(document)
            
            if self._save_data():
                print(f"✅ Saved business: {business_data.get('name', 'Unknown')}")
                return True
            else:
                # Remove from memory if save failed
                self.data["businesses"].pop()
                return False
                
        except Exception as e:
            print(f"❌ Error saving business: {e}")
            return False
    
    def save_businesses_batch(self, businesses: List[Dict[str, Any]], search_keyword: str) -> Dict[str, int]:
        """Save multiple businesses."""
        stats = {"saved": 0, "duplicates": 0, "errors": 0}
        
        for business in businesses:
            try:
                if self.save_business(business, search_keyword):
                    stats["saved"] += 1
                else:
                    stats["duplicates"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"❌ Error in batch save: {e}")
        
        print(f"📊 JSON batch save complete: {stats['saved']} saved, {stats['duplicates']} duplicates, {stats['errors']} errors")
        return stats
    
    def get_businesses(self, search_keyword: Optional[str] = None, 
                      contacted: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get businesses with filtering."""
        businesses = self.data.get("businesses", [])
        
        # Apply filters
        if search_keyword:
            keyword_lower = search_keyword.lower().strip()
            businesses = [b for b in businesses if b.get("search_keyword", "").lower() == keyword_lower]
        
        if contacted is not None:
            businesses = [b for b in businesses if b.get("contacted", False) == contacted]
        
        # Sort by created date (newest first) and limit
        businesses.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return businesses[:limit]
    
    def get_search_keywords(self) -> List[str]:
        """Get unique search keywords."""
        keywords = set()
        for business in self.data.get("businesses", []):
            keyword = business.get("search_keyword", "").strip()
            if keyword:
                keywords.add(keyword)
        return sorted(list(keywords))
    
    def mark_contacted(self, business_id: str, contacted: bool = True) -> bool:
        """Mark business as contacted."""
        for business in self.data.get("businesses", []):
            if business.get("_id") == business_id:
                business["contacted"] = contacted
                business["updated_at"] = datetime.utcnow().isoformat()
                return self._save_data()
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        businesses = self.data.get("businesses", [])
        total = len(businesses)
        contacted = len([b for b in businesses if b.get("contacted", False)])
        not_contacted = total - contacted
        
        # Count by keyword
        keyword_counts = {}
        for business in businesses:
            keyword = business.get("search_keyword", "unknown")
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        keyword_stats = [{"_id": k, "count": v} for k, v in keyword_counts.items()]
        keyword_stats.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "total_businesses": total,
            "contacted": contacted,
            "not_contacted": not_contacted,
            "keywords": keyword_stats
        }

# Updated database module to use JSON fallback
def save_scraping_results_fallback(businesses: List[Dict[str, Any]], search_keyword: str) -> Dict[str, int]:
    """Save results using JSON database fallback."""
    print("🗄️ Using JSON database fallback...")
    db = JSONDatabase()
    return db.save_businesses_batch(businesses, search_keyword)
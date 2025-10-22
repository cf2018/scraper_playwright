"""
MongoDB integration module for storing scraped business data.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BusinessDatabase:
    """Handle MongoDB operations for business data."""
    
    def __init__(self):
        """Initialize MongoDB connection."""
        # Support both MONGODB_URI (local) and MONGODB_CONNECTION_STRING (Lambda/Terraform)
        self.mongodb_uri = os.getenv('MONGODB_URI') or os.getenv('MONGODB_CONNECTION_STRING')
        # Support both MONGODB_NAME (local) and MONGODB_DATABASE (Lambda/Terraform)
        self.mongodb_name = os.getenv('MONGODB_NAME') or os.getenv('MONGODB_DATABASE', 'scraper')
        
        if not self.mongodb_uri:
            raise ValueError("MONGODB_URI or MONGODB_CONNECTION_STRING not found in environment variables")
        
        self.client = None
        self.db = None
        self.collection = None
        self._connect()
    
    def _connect(self):
        """Establish MongoDB connection."""
        try:
            # Configure connection with shorter timeouts
            self.client = MongoClient(
                self.mongodb_uri, 
                serverSelectionTimeoutMS=10000,  # 10 seconds
                connectTimeoutMS=10000,  # 10 seconds
                socketTimeoutMS=10000,   # 10 seconds
                maxPoolSize=10
            )
            self.db = self.client[self.mongodb_name]
            self.collection = self.db.businesses
            
            # Test connection with timeout
            self.client.admin.command('ping')
            print(f"✅ Connected to MongoDB: {self.mongodb_name}")
            
            # Create indexes for efficient queries
            self._create_indexes()
            
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            print("⚠️ Database operations will be skipped")
            self.client = None
            self.db = None
            self.collection = None
    
    def _create_indexes(self):
        """Create database indexes for efficient queries."""
        try:
            # Create compound index for uniqueness (name + phone + website)
            self.collection.create_index([
                ("name", ASCENDING),
                ("phone", ASCENDING),
                ("website", ASCENDING)
            ], unique=True, name="business_unique_idx")
            
            # Index for search keyword filtering
            self.collection.create_index([("search_keyword", ASCENDING)], name="keyword_idx")
            
            # Index for contact status filtering
            self.collection.create_index([("contacted", ASCENDING)], name="contacted_idx")
            
            # Index for created date
            self.collection.create_index([("created_at", ASCENDING)], name="created_at_idx")
            
            print("✅ Database indexes created successfully")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not create indexes: {e}")
    
    def save_business(self, business_data: Dict[str, Any], search_keyword: str) -> bool:
        """
        Save a single business to the database.
        
        Args:
            business_data: Dictionary containing business information
            search_keyword: The search term used to find this business
            
        Returns:
            bool: True if saved successfully, False if duplicate
        """
        if self.collection is None:
            print("⚠️ Database not connected, skipping save")
            return False
            
        try:
            # Prepare document for insertion
            # Support both 'website' and 'url' field names (scraper uses 'url')
            website = business_data.get("website") or business_data.get("url", "")
            
            document = {
                "name": business_data.get("name", ""),
                "phone": business_data.get("phone", ""),
                "website": website,
                "email": business_data.get("email", ""),
                "whatsapp": business_data.get("whatsapp", ""),
                "instagram": business_data.get("instagram", ""),
                "address": business_data.get("address", ""),
                "rating": business_data.get("rating"),
                "reviews": business_data.get("reviews"),
                "search_keyword": search_keyword.lower().strip(),
                "contacted": False,  # Default to not contacted
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert document
            result = self.collection.insert_one(document)
            print(f"✅ Saved business: {business_data.get('name', 'Unknown')} (ID: {result.inserted_id})")
            return True
            
        except DuplicateKeyError:
            # Business already exists (same name + phone + website)
            print(f"⚠️ Duplicate business skipped: {business_data.get('name', 'Unknown')}")
            return False
            
        except Exception as e:
            print(f"❌ Error saving business {business_data.get('name', 'Unknown')}: {e}")
            return False
    
    def save_businesses_batch(self, businesses: List[Dict[str, Any]], search_keyword: str) -> Dict[str, int]:
        """
        Save multiple businesses to the database.
        
        Args:
            businesses: List of business data dictionaries
            search_keyword: The search term used to find these businesses
            
        Returns:
            dict: Statistics about the save operation
        """
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
        
        print(f"📊 Batch save complete: {stats['saved']} saved, {stats['duplicates']} duplicates, {stats['errors']} errors")
        return stats
    
    def get_businesses(self, search_keyword: Optional[str] = None, contacted: Optional[bool] = None, 
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve businesses from the database with optional filtering.
        
        Args:
            search_keyword: Filter by search keyword (optional)
            contacted: Filter by contact status (optional)
            limit: Maximum number of results to return
            
        Returns:
            list: List of business documents
        """
        if self.collection is None:
            print("⚠️ Database not connected, returning empty list")
            return []
            
        try:
            # Build query filter
            query = {}
            
            if search_keyword:
                query["search_keyword"] = search_keyword.lower().strip()
            
            if contacted is not None:
                query["contacted"] = contacted
            
            # Execute query
            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
            businesses = list(cursor)
            
            # Convert ObjectId to string for JSON serialization
            for business in businesses:
                business["_id"] = str(business["_id"])
                
            print(f"📋 Retrieved {len(businesses)} businesses (keyword: {search_keyword}, contacted: {contacted})")
            return businesses
            
        except Exception as e:
            print(f"❌ Error retrieving businesses: {e}")
            return []
    
    def get_search_keywords(self) -> List[str]:
        """Get all unique search keywords in the database."""
        try:
            keywords = self.collection.distinct("search_keyword")
            keywords = [k for k in keywords if k]  # Remove empty strings
            print(f"🔍 Found {len(keywords)} unique search keywords")
            return sorted(keywords)
        except Exception as e:
            print(f"❌ Error retrieving keywords: {e}")
            return []
    
    def mark_contacted(self, business_id: str, contacted: bool = True) -> bool:
        """
        Mark a business as contacted or not contacted.
        
        Args:
            business_id: MongoDB ObjectId as string
            contacted: Contact status to set
            
        Returns:
            bool: True if updated successfully
        """
        try:
            from bson import ObjectId
            
            result = self.collection.update_one(
                {"_id": ObjectId(business_id)},
                {
                    "$set": {
                        "contacted": contacted,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                status = "contacted" if contacted else "not contacted"
                print(f"✅ Marked business as {status}")
                return True
            else:
                print(f"⚠️ Business not found or already in desired state")
                return False
                
        except Exception as e:
            print(f"❌ Error updating contact status: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            total_businesses = self.collection.count_documents({})
            contacted_count = self.collection.count_documents({"contacted": True})
            not_contacted_count = self.collection.count_documents({"contacted": False})
            
            # Get businesses by keyword
            pipeline = [
                {"$group": {"_id": "$search_keyword", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            keyword_stats = list(self.collection.aggregate(pipeline))
            
            stats = {
                "total_count": total_businesses,
                "total_businesses": total_businesses,  # Keep for backward compatibility
                "contacted_count": contacted_count,
                "contacted": contacted_count,  # Keep for backward compatibility
                "not_contacted_count": not_contacted_count,
                "not_contacted": not_contacted_count,  # Keep for backward compatibility
                "search_keywords": [item["_id"] for item in keyword_stats if item["_id"]],
                "keywords": keyword_stats
            }
            
            print(f"📊 Database stats: {total_businesses} total, {contacted_count} contacted, {not_contacted_count} not contacted")
            return stats
            
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}
    
    def delete_business(self, business_id: str) -> bool:
        """
        Delete a business by ID.
        
        Args:
            business_id: The business ID to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if self.collection is None:
            return False
            
        try:
            from bson import ObjectId
            result = self.collection.delete_one({"_id": ObjectId(business_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Error deleting business: {e}")
            return False
    
    def delete_businesses(self, keyword: str = None, contacted: bool = None) -> int:
        """
        Delete businesses based on filters.
        
        Args:
            keyword: Optional keyword filter
            contacted: Optional contacted status filter
            
        Returns:
            int: Number of businesses deleted
        """
        if self.collection is None:
            return 0
            
        try:
            # Build filter
            filter_query = {}
            
            if keyword:
                filter_query["search_keyword"] = keyword
                
            if contacted is not None:
                filter_query["contacted"] = contacted
            
            result = self.collection.delete_many(filter_query)
            print(f"🗑️ Deleted {result.deleted_count} businesses")
            return result.deleted_count
        except Exception as e:
            print(f"❌ Error deleting businesses: {e}")
            return 0
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
    
    # ==================== SCRAPING TASK MANAGEMENT ====================
    
    def create_scraping_task(self, task_id, search_query, max_results):
        """
        Create a new scraping task in MongoDB.
        
        Args:
            task_id: Unique task identifier
            search_query: Search query string
            max_results: Maximum number of results to scrape
            
        Returns:
            dict: Created task document
        """
        if self.db is None:
            raise Exception("MongoDB connection not available")
        
        task = {
            '_id': task_id,
            'search_query': search_query,
            'max_results': max_results,
            'status': 'pending',
            'progress': 0,
            'total_found': 0,
            'duplicates_found': 0,
            'current_activity': 'Initializing...',
            'error': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'completed_at': None
        }
        
        self.db.scraping_tasks.insert_one(task)
        print(f"📝 Created scraping task: {task_id}")
        return task
    
    def get_scraping_task(self, task_id):
        """
        Get a scraping task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            dict: Task document or None
        """
        if self.db is None:
            return None
        
        return self.db.scraping_tasks.find_one({'_id': task_id})
    
    def update_scraping_task(self, task_id, updates):
        """
        Update a scraping task.
        
        Args:
            task_id: Task identifier
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if successful
        """
        if self.db is None:
            return False
        
        updates['updated_at'] = datetime.now()
        
        result = self.db.scraping_tasks.update_one(
            {'_id': task_id},
            {'$set': updates}
        )
        
        return result.modified_count > 0
    
    def complete_scraping_task(self, task_id, status='completed', error=None):
        """
        Mark a scraping task as completed or failed.
        
        Args:
            task_id: Task identifier
            status: Final status ('completed' or 'error')
            error: Error message if status is 'error'
            
        Returns:
            bool: True if successful
        """
        if self.db is None:
            return False
        
        updates = {
            'status': status,
            'completed_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        if error:
            updates['error'] = error
        
        result = self.db.scraping_tasks.update_one(
            {'_id': task_id},
            {'$set': updates}
        )
        
        print(f"✅ Task {task_id} marked as {status}")
        return result.modified_count > 0

# Utility functions for easy access
def save_scraping_results(businesses: List[Dict[str, Any]], search_keyword: str) -> Dict[str, int]:
    """
    Convenience function to save scraping results to database.
    
    Args:
        businesses: List of business data dictionaries
        search_keyword: The search term used
        
    Returns:
        dict: Save statistics
    """
    db = BusinessDatabase()
    try:
        return db.save_businesses_batch(businesses, search_keyword)
    finally:
        db.close()

def get_businesses_by_keyword(search_keyword: str, contacted: Optional[bool] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to get businesses by search keyword.
    
    Args:
        search_keyword: The search keyword to filter by
        contacted: Optional contact status filter
        
    Returns:
        list: List of businesses
    """
    db = BusinessDatabase()
    try:
        return db.get_businesses(search_keyword, contacted)
    finally:
        db.close()

def show_database_stats():
    """Display database statistics."""
    db = BusinessDatabase()
    try:
        stats = db.get_stats()
        print("\n" + "="*50)
        print("📊 DATABASE STATISTICS")
        print("="*50)
        print(f"Total businesses: {stats.get('total_businesses', 0)}")
        print(f"Contacted: {stats.get('contacted', 0)}")
        print(f"Not contacted: {stats.get('not_contacted', 0)}")
        print("\nBusinesses by search keyword:")
        for item in stats.get('keywords', [])[:10]:  # Show top 10
            print(f"  • {item['_id']}: {item['count']} businesses")
    finally:
        db.close()

if __name__ == "__main__":
    # Test the database connection
    try:
        db = BusinessDatabase()
        db.get_stats()
        db.close()
        print("✅ Database module test successful!")
    except Exception as e:
        print(f"❌ Database module test failed: {e}")
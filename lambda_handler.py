#!/usr/bin/env python3
"""
AWS Lambda Handler for Business Scraper

This module provides the Lambda function handler for running the business scraper
in a serverless environment with automatic headless browser configuration.
"""

import json
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, Any

# Set environment for Lambda
os.environ['PLAYWRIGHT_HEADLESS'] = 'true'
os.environ['LAMBDA_ENVIRONMENT'] = 'true'

# Import application modules
try:
    from scrape_businesses_maps import BusinessScraper
except ImportError as e:
    print(f"Import error for scraper: {e}")
    
try:
    from database import BusinessDatabase
    mongodb_available = True
except ImportError:
    mongodb_available = False
    print("MongoDB not available, using JSON fallback")

from json_database import JSONDatabase


def lambda_handler(event, context):
    """
    AWS Lambda handler for business scraping.
    
    Args:
        event (dict): Lambda event data containing:
            - search_query (str): Search terms for businesses
            - max_results (int): Maximum number of results to scrape
            - headless (bool): Browser headless mode (forced True in Lambda)
            - timeout (int): Browser timeout in milliseconds
            
        context: Lambda context object
        
    Returns:
        dict: Response with statusCode and body containing results or error
    """
    start_time = datetime.now()
    
    try:
        # Log incoming event (excluding sensitive data)
        print(f"Lambda invocation started at {start_time}")
        print(f"Event keys: {list(event.keys())}")
        
        # Extract and validate parameters from event
        search_query = event.get("search_query", "registro de marcas en buenos aires")
        max_results = min(int(event.get("max_results", 50)), 100)  # Cap at 100 for Lambda limits
        timeout = min(int(event.get("timeout", 30000)), 60000)  # Cap at 60 seconds
        
        # Validate search query
        if not search_query or len(search_query.strip()) == 0:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "success": False,
                    "error": "search_query parameter is required and cannot be empty"
                })
            }
        
        print(f"Starting scrape for: '{search_query}' (max: {max_results} results)")
        
        # Initialize scraper with Lambda-optimized settings
        scraper = BusinessScraper(
            headless=True,          # Always headless in Lambda
            slow_mo=0,             # No slow motion delays
            timeout=timeout,        # Configurable timeout
            viewport={'width': 1280, 'height': 720}  # Standard viewport
        )
        
        # Run the scraping process (async)
        import asyncio
        scrape_start = datetime.now()
        results = asyncio.run(scraper.scrape_businesses(
            search_query=search_query,
            max_results=max_results
        ))
        scrape_duration = (datetime.now() - scrape_start).total_seconds()
        
        # Calculate execution metrics
        total_duration = (datetime.now() - start_time).total_seconds()
        
        # Prepare response
        response_data = {
            "success": True,
            "message": f"Successfully scraped {len(results)} businesses",
            "data": {
                "results_count": len(results),
                "search_query": search_query,
                "execution_time_seconds": round(total_duration, 2),
                "scraping_time_seconds": round(scrape_duration, 2),
                "businesses": results  # Include actual business data
            }
        }
        
        print(f"Scraping completed successfully in {total_duration:.2f}s")
        print(f"Found {len(results)} businesses")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_data, ensure_ascii=False, default=str)
        }
        
    except Exception as e:
        # Log detailed error information
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "execution_time_seconds": (datetime.now() - start_time).total_seconds()
        }
        
        print(f"Lambda execution failed: {error_details}")
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": error_details["execution_time_seconds"]
            })
        }


def health_check_handler(event, context):
    """
    Health check handler for Lambda warm-up and monitoring.
    
    Returns:
        dict: Health status response
    """
    try:
        # Basic health checks
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "playwright_available": False,
            "mongodb_available": mongodb_available
        }
        
        # Test Playwright import
        try:
            from playwright.sync_api import sync_playwright
            health_status["playwright_available"] = True
        except ImportError:
            pass
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(health_status)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "unhealthy",
                "error": str(e)
            })
        }


def api_gateway_handler(event, context):
    """
    Handler for API Gateway integration with different HTTP methods.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        dict: API Gateway compatible response
    """
    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        
        if http_method == 'GET' and path == '/health':
            return health_check_handler(event, context)
        
        elif http_method == 'POST' and path == '/scrape':
            # Extract body data for POST requests
            body = event.get('body', '{}')
            if isinstance(body, str):
                body = json.loads(body)
            
            # Merge query parameters and body parameters
            query_params = event.get('queryStringParameters') or {}
            scrape_event = {**query_params, **body}
            
            return lambda_handler(scrape_event, context)
        
        else:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Not Found",
                    "message": f"Path {path} with method {http_method} not found"
                })
            }
            
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal Server Error",
                "message": str(e)
            })
        }


if __name__ == "__main__":
    # Test the lambda handler locally
    test_event = {
        "search_query": "registro de marcas en buenos aires",
        "max_results": 10
    }
    
    class MockContext:
        def __init__(self):
            self.function_name = "test-function"
            self.function_version = "1"
            self.memory_limit_in_mb = 512
    
    print("Testing Lambda handler locally...")
    result = lambda_handler(test_event, MockContext())
    print(f"Result: {json.dumps(result, indent=2)}")
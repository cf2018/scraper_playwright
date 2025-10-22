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

# Optional Flask bridge: if `app` and `apig_wsgi` are available in the image we can
# forward API Gateway proxy events to the Flask WSGI app. This makes the
# behavior consistent no matter which module the Lambda runtime invokes.
try:
    from apig_wsgi import make_lambda_handler
    from app import app as flask_app  # type: ignore
    _flask_handler = make_lambda_handler(flask_app)
    _FLASK_AVAILABLE = True
except Exception:
    _FLASK_AVAILABLE = False
    
# Diagnostic startup log so we can see in CloudWatch whether Flask/awsgi were
# successfully imported in the Lambda runtime.
print(f"_FLASK_AVAILABLE = {_FLASK_AVAILABLE}")


def lambda_handler(event, context):
    """
    AWS Lambda handler for business scraping.
    
    Args:
        event (dict): Lambda event data containing:
            - action (str): 'scrape' for async scraping invocation
            - task_id (str): Task ID for async scraping
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
        
        # Check if this is an async scraping invocation
        if event.get('action') == 'scrape':
            print(f"🎯 Async scraping invocation for task {event.get('task_id')}")
            from app import run_scraping_task_mongodb
            
            task_id = event.get('task_id')
            search_query = event.get('search_query')
            max_results = event.get('max_results')
            
            # Run scraping (will create its own DB connection)
            run_scraping_task_mongodb(task_id, search_query, max_results, None)
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "message": f"Scraping completed for task {task_id}"
                })
            }        # Extract and validate parameters from event
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


def serve_dashboard_html():
    """
    Serve the dashboard HTML page.
    This function returns the HTML content for the web dashboard.
    """
    try:
        # Get database stats for the dashboard
        db = None
        db_type = "JSON"
        
        if mongodb_available:
            try:
                db = BusinessDatabase()
                if db.collection is None:
                    db = None
            except:
                db = None
        
        if db is None:
            db = JSONDatabase()
        
        try:
            # Get statistics
            stats = db.get_stats()
            recent_businesses = db.get_businesses(limit=20)
            keywords = db.get_search_keywords()
        except Exception as e:
            # Fallback stats if database fails
            stats = {"total_businesses": 0, "contacted": 0, "not_contacted": 0}
            recent_businesses = []
            keywords = []
        finally:
            if hasattr(db, 'close'):
                db.close()
        
        # Generate HTML dashboard
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Business Scraper Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            border-radius: 10px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .header p {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .stat-card h3 {{
            color: #667eea;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .stat-card .number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #333;
        }}
        
        .actions {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }}
        
        .btn {{
            background: #667eea;
            color: white;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 5px;
            text-decoration: none;
            display: inline-block;
            margin: 0.5rem;
            cursor: pointer;
            transition: background 0.3s;
        }}
        
        .btn:hover {{
            background: #5a6fd8;
        }}
        
        .btn-secondary {{
            background: #6c757d;
        }}
        
        .btn-secondary:hover {{
            background: #5a6268;
        }}
        
        .table-container {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        
        .status-badge {{
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        .status-contacted {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-not-contacted {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .filters {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }}
        
        .filter-row {{
            display: flex;
            gap: 1rem;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        select, input {{
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        
        .delete-btn {{
            background: #dc3545;
            color: white;
            border: none;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.8rem;
        }}
        
        .delete-btn:hover {{
            background: #c82333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕷️ Business Scraper Dashboard</h1>
            <p>Google Maps Business Data Collection & Management</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Businesses</h3>
                <div class="number">{stats.get('total_businesses', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Contacted</h3>
                <div class="number">{stats.get('contacted', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Not Contacted</h3>
                <div class="number">{stats.get('not_contacted', 0)}</div>
            </div>
        </div>
        
        <div class="actions">
            <h2>Actions</h2>
            <a href="/scrape" class="btn">🕷️ Start New Scrape</a>
            <a href="/export" class="btn btn-secondary">📊 Export Data</a>
            <button onclick="refreshData()" class="btn btn-secondary">🔄 Refresh</button>
        </div>
        
        <div class="filters">
            <h2>Filters</h2>
            <div class="filter-row">
                <select id="keywordFilter">
                    <option value="">All Keywords</option>
                    {"".join(f'<option value="{kw}">{kw}</option>' for kw in keywords)}
                </select>
                <select id="contactedFilter">
                    <option value="">All Status</option>
                    <option value="true">Contacted</option>
                    <option value="false">Not Contacted</option>
                </select>
                <button onclick="applyFilters()" class="btn">Apply Filters</button>
                <button onclick="clearFilters()" class="btn btn-secondary">Clear</button>
            </div>
        </div>
        
        <div class="table-container">
            <table id="businessesTable">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Address</th>
                        <th>Phone</th>
                        <th>Website</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="businessesBody">
                    {"".join(f'''
                    <tr>
                        <td>{b.get('name', 'N/A')}</td>
                        <td>{b.get('address', 'N/A')}</td>
                        <td>{b.get('phone', 'N/A')}</td>
                        <td><a href="{b.get('website', '#')}" target="_blank">{b.get('website', 'N/A')}</a></td>
                        <td><span class="status-badge status-{'contacted' if b.get('contacted') else 'not-contacted'}">{'Contacted' if b.get('contacted') else 'Not Contacted'}</span></td>
                        <td>
                            <button onclick="toggleContact('{b.get('_id', '')})" class="btn" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;">Toggle Status</button>
                            <button onclick="deleteBusiness('{b.get('_id', '')})" class="delete-btn">Delete</button>
                        </td>
                    </tr>
                    ''' for b in recent_businesses)}
                </tbody>
            </table>
        </div>
    </div>

        <script>
        async function refreshData() {{
            location.reload();
        }}
        
        async function applyFilters() {{
            const keyword = document.getElementById('keywordFilter').value;
            const contacted = document.getElementById('contactedFilter').value;
            
            let url = '/api/businesses?';
            if (keyword) url += 'keyword=' + encodeURIComponent(keyword) + '&';
            if (contacted) url += 'contacted=' + contacted + '&';
            
            try {{
                const response = await fetch(url);
                const data = await response.json();
                updateTable(data.businesses);
            }} catch (error) {{
                alert('Error loading filtered data: ' + error.message);
            }}
        }}
        
        async function clearFilters() {{
            document.getElementById('keywordFilter').value = '';
            document.getElementById('contactedFilter').value = '';
            applyFilters();
        }}
        
        async function toggleContact(businessId) {{
            try {{
                const response = await fetch('/api/contact/' + businessId, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{contacted: true}})
                }});
                const data = await response.json();
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error updating status: ' + data.error);
                }}
            }} catch (error) {{
                alert('Error: ' + error.message);
            }}
        }}
        
        async function deleteBusiness(businessId) {{
            if (!confirm('Are you sure you want to delete this business?')) return;
            
            try {{
                const response = await fetch('/api/delete/' + businessId, {{
                    method: 'DELETE'
                }});
                const data = await response.json();
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error deleting business: ' + data.error);
                }}
            }} catch (error) {{
                alert('Error: ' + error.message);
            }}
        }}
        
        function updateTable(businesses) {{
            const tbody = document.getElementById('businessesBody');
            tbody.innerHTML = businesses.map(b => 
                '<tr>' +
                    '<td>' + (b.name || 'N/A') + '</td>' +
                    '<td>' + (b.address || 'N/A') + '</td>' +
                    '<td>' + (b.phone || 'N/A') + '</td>' +
                    '<td><a href="' + (b.website || '#') + '" target="_blank">' + (b.website || 'N/A') + '</a></td>' +
                    '<td><span class="status-badge status-' + (b.contacted ? 'contacted' : 'not-contacted') + '">' + (b.contacted ? 'Contacted' : 'Not Contacted') + '</span></td>' +
                    '<td>' +
                        '<button onclick="toggleContact(\'' + b._id + '\')" class="btn" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;">Toggle Status</button>' +
                        '<button onclick="deleteBusiness(\'' + b._id + '\')" class="delete-btn">Delete</button>' +
                    '</td>' +
                '</tr>'
            ).join('');
        }}
    </script>
</body>
</html>"""
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "Access-Control-Allow-Origin": "*"
            },
            "body": html_content
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal Server Error",
                "message": str(e)
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
    # If Flask is available, prefer forwarding the API Gateway event to it so
    # the unified web app (routes under / and /api/*) handles the request.
    if _FLASK_AVAILABLE:
        try:
            # Use apig_wsgi handler to convert the API Gateway event to a WSGI call
            return _flask_handler(event, context)
        except Exception as e:
            print(f"Flask forwarding failed, falling back to builtin handler: {e}")

    try:
        print(f"DEBUG: Received event: {json.dumps(event, default=str)}")
        
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        
        print(f"DEBUG: HTTP method: {http_method}, Path: {path}")
        
        # Check if this is a web request (browser) vs API request
        # Use query parameter 'format' to explicitly request JSON, otherwise serve HTML
        query_params = event.get('queryStringParameters') or {}
        format_param = query_params.get('format', '').lower()
        
        # Debug logging
        print(f"Query params received: {query_params}")
        print(f"Format param: '{format_param}'")
        
        # If format=json is explicitly requested, serve API info
        # Otherwise, serve HTML dashboard (default for web browsers)
        is_api_request = format_param == 'json'
        
        print(f"Is API request: {is_api_request}")
        
        # Root endpoint - serve dashboard HTML for web requests, API info for API requests
        if http_method == 'GET' and path in ['/', '']:
            if not is_api_request:
                # Serve the web dashboard
                print("DEBUG: Serving HTML dashboard")
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "text/html",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": """<!DOCTYPE html>
<html>
<head>
    <title>Business Scraper Dashboard</title>
</head>
<body>
    <h1>🕷️ Business Scraper Dashboard</h1>
    <p>Dashboard is loading...</p>
    <a href="/scrape">Go to Scraper</a>
</body>
</html>"""
                }
            else:
                # Serve API information
                print("DEBUG: Serving API info")
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "name": "Business Scraper API",
                        "version": "1.0.0",
                        "description": "Google Maps business scraper running on AWS Lambda",
                        "endpoints": {
                            "GET /": "API information and available endpoints",
                            "GET /health": "Health check and system status",
                            "POST /scrape": "Scrape businesses from Google Maps"
                        },
                        "timestamp": datetime.now().isoformat()
                    })
                }
        
        elif http_method == 'GET' and path == '/health':
            print("DEBUG: Serving health check")
            return health_check_handler(event, context)
        
        elif http_method == 'POST' and path == '/scrape':
            print("DEBUG: Serving scrape endpoint")
            # Extract body data for POST requests
            body = event.get('body', '{}')
            if isinstance(body, str):
                body = json.loads(body)
            
            # Merge query parameters and body parameters
            query_params = event.get('queryStringParameters') or {}
            scrape_event = {**query_params, **body}
            
            return lambda_handler(scrape_event, context)
        
        else:
            print(f"DEBUG: 404 for path {path} with method {http_method}")
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Not Found",
                    "message": f"Path {path} with method {http_method} not found"
                })
            }
            
    except Exception as e:
        print(f"DEBUG: Exception in api_gateway_handler: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
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
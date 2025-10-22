"""
Flask Web Application for Google Maps Business Scraper
A modern web interface for scraping business information from Google Maps
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_cors import CORS
import asyncio
import json
import os
from datetime import datetime
from scrape_businesses_maps import BusinessScraper
import threading
import uuid
from apig_wsgi import make_lambda_handler

# boto3 is available in Lambda runtime by default
try:
    import boto3
    boto3_available = True
except ImportError:
    boto3_available = False

# Import database modules
try:
    from database import BusinessDatabase
    mongodb_available = True
except:
    mongodb_available = False

from json_database import JSONDatabase

app = Flask(__name__)
CORS(app)

# Handle API Gateway stage prefix (e.g., /prod)
# Set to empty string when deployed without prefix
API_PREFIX = os.environ.get('API_PREFIX', '/prod' if os.environ.get('LAMBDA_ENVIRONMENT') else '')

# Configure Flask to handle the prefix transparently
if API_PREFIX:
    app.config['APPLICATION_ROOT'] = API_PREFIX
    
    # Middleware to strip the prefix from incoming requests
    class PrefixMiddleware:
        def __init__(self, app, prefix):
            self.app = app
            self.prefix = prefix.rstrip('/')
            
        def __call__(self, environ, start_response):
            path = environ.get('PATH_INFO', '')
            if path.startswith(self.prefix):
                environ['PATH_INFO'] = path[len(self.prefix):] or '/'
                environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
    
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, API_PREFIX)

# Make API_PREFIX available to all templates
@app.context_processor
def inject_api_prefix():
    return {'api_prefix': API_PREFIX}

# Store active scraping tasks
active_tasks = {}

def get_database():
    """Get the appropriate database (MongoDB or JSON fallback)."""
    if mongodb_available:
        try:
            db = BusinessDatabase()
            # BusinessDatabase __init__ will raise ValueError if connection fails
            return db, "MongoDB"
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
    
    # Fall back to JSON database
    return JSONDatabase(), "JSON"

class ScrapingTask:
    def __init__(self, task_id, search_query, max_results):
        self.task_id = task_id
        self.search_query = search_query
        self.max_results = max_results
        self.status = "starting"
        self.progress = 0
        self.total_found = 0
        self.duplicates_found = 0
        self.results = []
        self.error = None
        self.start_time = datetime.now()
        self.end_time = None
        self.json_file = None

@app.route('/')
def dashboard():
    """Main dashboard page."""
    db, db_type = get_database()
    
    # Check if database is actually connected
    db_error = None
    if db_type == "MongoDB":
        try:
            # Test the connection
            if hasattr(db, 'collection') and db.collection is not None:
                db.collection.database.client.admin.command('ping')
        except Exception as e:
            db_error = "Database temporarily unavailable. Please try again later."
            print(f"❌ Database connection test failed: {e}")
    
    try:
        if db_error:
            # Return dashboard with error message
            return render_template('dashboard.html', 
                                 stats={'total': 0, 'contacted': 0, 'not_contacted': 0}, 
                                 businesses=[],
                                 keywords=[],
                                 db_type=db_type,
                                 db_error=db_error)
        
        # Get statistics
        stats = db.get_stats()
        
        # Get recent businesses (last 20)
        recent_businesses = db.get_businesses(limit=20)
        
        # Get all keywords for filter dropdown
        keywords = db.get_search_keywords()
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             businesses=recent_businesses,
                             keywords=keywords,
                             db_type=db_type)
    except Exception as e:
        print(f"❌ Error loading dashboard: {e}")
        return render_template('dashboard.html', 
                             stats={'total': 0, 'contacted': 0, 'not_contacted': 0}, 
                             businesses=[],
                             keywords=[],
                             db_type=db_type,
                             db_error="Database temporarily unavailable. Please try again later.")
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/scrape')
def scrape_page():
    """Scraping page with search form"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def start_scraping():
    """Start a new scraping task - now works in Lambda with MongoDB!"""
    try:
        data = request.get_json()
        search_query = data.get('search_query', '').strip()
        max_results = min(int(data.get('max_results', 10)), 20)  # Limit to 20 for Lambda timeout
        
        if not search_query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Get database connection
        db, db_type = get_database()
        
        if db_type != "MongoDB":
            return jsonify({
                'error': 'Scraping requires MongoDB connection',
                'message': 'Please configure MONGODB_CONNECTION_STRING environment variable'
            }), 503
        
        try:
            # Create task in MongoDB
            db.create_scraping_task(task_id, search_query, max_results)
            
            # Check if we're in Lambda environment
            is_lambda = os.getenv('LAMBDA_ENVIRONMENT') == 'true'
            
            if is_lambda and boto3_available:
                # Invoke Lambda asynchronously to avoid API Gateway timeout
                try:
                    lambda_client = boto3.client('lambda')
                    function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME')
                    
                    print(f"📞 Invoking Lambda async: {function_name} for task {task_id}")
                    
                    payload = {
                        'action': 'scrape',
                        'task_id': task_id,
                        'search_query': search_query,
                        'max_results': max_results
                    }
                    
                    response = lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='Event',  # Async invocation
                        Payload=json.dumps(payload)
                    )
                    
                    print(f"✅ Lambda invoked: StatusCode={response.get('StatusCode')}")
                    
                    return jsonify({
                        'task_id': task_id, 
                        'status': 'started',
                        'message': 'Scraping started! Poll /api/status/' + task_id + ' for progress'
                    })
                except Exception as e:
                    print(f"❌ Failed to invoke Lambda async: {e}")
                    # Fall back to synchronous execution
                    print("⚠️ Falling back to synchronous scraping")
                    run_scraping_task_mongodb(task_id, search_query, max_results, db)
                    return jsonify({
                        'task_id': task_id, 
                        'status': 'completed',
                        'message': 'Scraping completed synchronously'
                    })
            else:
                # Local development - run synchronously
                run_scraping_task_mongodb(task_id, search_query, max_results, db)
                
                return jsonify({
                    'task_id': task_id, 
                    'status': 'completed',
                    'message': 'Scraping completed'
                })
            
        finally:
            if hasattr(db, 'close'):
                db.close()
        
    except Exception as e:
        print(f"❌ Error starting scraping: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """Get status of a scraping task - now reads from MongoDB!"""
    db, db_type = get_database()
    
    try:
        if db_type != "MongoDB":
            # Fallback to memory for local development
            task = active_tasks.get(task_id)
            if not task:
                return jsonify({'error': 'Task not found'}), 404
            
            response = {
                'task_id': task_id,
                'status': task.status,
                'progress': task.progress,
                'total_found': task.total_found,
                'duplicates_found': task.duplicates_found,
                'search_query': task.search_query,
                'max_results': task.max_results,
                'start_time': task.start_time.isoformat()
            }
            
            if task.end_time:
                response['end_time'] = task.end_time.isoformat()
                response['duration'] = str(task.end_time - task.start_time)
            
            if task.error:
                response['error'] = task.error
            
            return jsonify(response)
        
        # Read from MongoDB
        task = db.get_scraping_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        response = {
            'task_id': task_id,
            'status': task['status'],
            'progress': task['progress'],
            'total_found': task['total_found'],
            'duplicates_found': task['duplicates_found'],
            'search_query': task['search_query'],
            'max_results': task['max_results'],
            'current_activity': task.get('current_activity', ''),
            'created_at': task['created_at'].isoformat(),
            'updated_at': task['updated_at'].isoformat()
        }
        
        if task.get('completed_at'):
            response['completed_at'] = task['completed_at'].isoformat()
            duration = task['completed_at'] - task['created_at']
            response['duration'] = str(duration)
        
        if task.get('error'):
            response['error'] = task['error']
        
        return jsonify(response)
        
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/download/<task_id>')
def download_json(task_id):
    """Download JSON results for a task"""
    task = active_tasks.get(task_id)
    if not task or not task.json_file:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        return send_file(task.json_file, as_attachment=True, download_name=f"{task.search_query.replace(' ', '_')}_results.json")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_scraping_task_mongodb(task_id, search_query, max_results, db):
    """
    Run scraping task synchronously with MongoDB state persistence.
    This works in Lambda because we update MongoDB as we progress.
    """
    loop = None
    try:
        # Create new database connection if not provided
        if db is None:
            db, _ = get_database()
        
        # Update task status to running
        db.update_scraping_task(task_id, {
            'status': 'running',
            'progress': 0,
            'current_activity': 'Starting browser...'
        })
        print(f"🚀 Starting scraping task: {task_id}")
        
        # Set up event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the scraping
        loop.run_until_complete(execute_scraping_mongodb(task_id, search_query, max_results, db))
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Scraping error: {error_msg}")
        if db:
            db.complete_scraping_task(task_id, status='error', error=error_msg)
    finally:
        if loop:
            loop.close()
        if db and hasattr(db, 'close'):
            db.close()

async def execute_scraping_mongodb(task_id, search_query, max_results, db):
    """Execute the actual scraping with MongoDB progress updates"""
    try:
        print(f"🔍 Scraping: {search_query} (max: {max_results})")
        
        # Create scraper instance (headless mode for Lambda)
        scraper = BusinessScraper(search_query, headless=True)
        
        # Track progress and update MongoDB
        original_extract = scraper.extract_business_info
        last_update_count = 0
        
        async def track_progress_extract(page):
            nonlocal last_update_count
            result = await original_extract(page)
            
            # Update MongoDB every business found
            current_count = len(scraper.business_data)
            if current_count != last_update_count:
                progress = min(95, int((current_count / max_results) * 100))
                db.update_scraping_task(task_id, {
                    'progress': progress,
                    'total_found': current_count,
                    'duplicates_found': scraper.duplicates_found,
                    'current_activity': f'Extracting business {current_count}/{max_results}...'
                })
                print(f"📊 Progress: {current_count}/{max_results} ({progress}%)")
                last_update_count = current_count
            
            return result
        
        scraper.extract_business_info = track_progress_extract
        
        # Update activity: navigating to Google Maps
        db.update_scraping_task(task_id, {
            'current_activity': f'Searching Google Maps for "{search_query}"...'
        })
        
        # Start scraping
        businesses = await scraper.scrape_businesses(max_results=max_results)
        
        # Update activity: saving results
        db.update_scraping_task(task_id, {
            'current_activity': 'Saving results to database...'
        })
        
        # Save results to database
        saved_count = 0
        for business in businesses:
            try:
                db.save_business(business, search_query)
                saved_count += 1
            except Exception as e:
                print(f"⚠️ Failed to save business: {e}")
        
        # Mark task as completed
        db.update_scraping_task(task_id, {
            'progress': 100,
            'total_found': len(businesses),
            'duplicates_found': scraper.duplicates_found,
            'current_activity': f'Completed! {saved_count} businesses saved.'
        })
        
        db.complete_scraping_task(task_id, status='completed')
        
        print(f"✅ Scraping completed: {saved_count} businesses saved")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Scraping failed: {error_msg}")
        db.complete_scraping_task(task_id, status='error', error=error_msg)
        raise

# Dashboard API Routes
@app.route('/api/businesses')
def api_businesses():
    """API endpoint to get filtered businesses."""
    db, db_type = get_database()
    
    try:
        # Test database connection
        if db_type == "MongoDB":
            try:
                if hasattr(db, 'collection') and db.collection is not None:
                    db.collection.database.client.admin.command('ping')
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': 'Database temporarily unavailable'
                }), 503
        
        # Get query parameters
        keyword = request.args.get('keyword')
        contacted = request.args.get('contacted')
        limit = int(request.args.get('limit', 50))
        
        # Convert contacted parameter
        contacted_filter = None
        if contacted == 'true':
            contacted_filter = True
        elif contacted == 'false':
            contacted_filter = False
        
        # Get filtered businesses
        businesses = db.get_businesses(keyword, contacted_filter, limit)
        
        return jsonify({
            'success': True,
            'businesses': businesses,
            'db_type': db_type,
            'count': len(businesses)
        })
    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Database temporarily unavailable'
        }), 503
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/stats')
def api_stats():
    """API endpoint to get database statistics."""
    db, db_type = get_database()
    
    try:
        stats = db.get_stats()
        keywords = db.get_search_keywords()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'keywords': keywords,
            'db_type': db_type
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/contact/<business_id>', methods=['POST'])
def update_contact_status(business_id):
    """API endpoint to update business contact status."""
    db, db_type = get_database()
    
    try:
        data = request.get_json()
        contacted = data.get('contacted', False)
        
        # Update business
        success = db.update_contact_status(business_id, contacted)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Contact status updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Business not found or could not be updated'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/business/<business_id>')
def business_detail(business_id):
    """Business detail page."""
    db, db_type = get_database()
    
    try:
        # Get business by ID
        business = db.get_business_by_id(business_id)
        
        if business:
            return render_template('business_detail.html', business=business, db_type=db_type)
        else:
            return "Business not found", 404
    except Exception as e:
        return f"Error loading business: {str(e)}", 500
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/export')
def export_page():
    """Export page."""
    db, db_type = get_database()
    
    try:
        keywords = db.get_search_keywords()
        return render_template('export.html', keywords=keywords, db_type=db_type)
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/export')
def api_export():
    """API endpoint to export businesses as JSON."""
    db, db_type = get_database()
    
    try:
        # Get query parameters
        keyword = request.args.get('keyword')
        contacted = request.args.get('contacted')
        
        # Convert contacted parameter
        contacted_filter = None
        if contacted == 'true':
            contacted_filter = True
        elif contacted == 'false':
            contacted_filter = False
        
        # Get businesses
        businesses = db.get_businesses(keyword, contacted_filter, limit=1000)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filters = []
        if keyword:
            filters.append(keyword.replace(' ', '_'))
        if contacted_filter is not None:
            filters.append("contacted" if contacted_filter else "not_contacted")
        
        filter_str = "_".join(filters) if filters else "all"
        filename = f"businesses_export_{filter_str}_{timestamp}.json"
        
        response = app.response_class(
            response=json.dumps(businesses, indent=2, ensure_ascii=False, default=str),
            status=200,
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/delete/<business_id>', methods=['DELETE'])
def delete_business(business_id):
    """API endpoint to delete a business."""
    db, db_type = get_database()
    
    try:
        # Delete the business
        success = db.delete_business(business_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Business deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Business not found or could not be deleted'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/delete-all', methods=['DELETE'])
def delete_all_businesses():
    """API endpoint to delete all businesses."""
    db, db_type = get_database()
    
    try:
        # Get parameters for filtered deletion
        keyword = request.args.get('keyword')
        contacted = request.args.get('contacted')
        
        # Convert contacted parameter
        contacted_filter = None
        if contacted == 'true':
            contacted_filter = True
        elif contacted == 'false':
            contacted_filter = False
        
        # Delete businesses based on filters
        count = db.delete_businesses(keyword, contacted_filter)
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {count} businesses',
            'count': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if hasattr(db, 'close'):
            db.close()

if __name__ == '__main__':
    # Ensure templates and static directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('json_output', exist_ok=True)
    
    print("🚀 Starting Unified Business Scraper Application...")
    print("📊 Dashboard: http://localhost:5000/")
    print("🕷️ Scraping: http://localhost:5000/scrape")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

# Lambda handler bridge for API Gateway (REST API proxy -> WSGI)
# Create the handler using apig-wsgi which properly bridges API Gateway to Flask
_flask_handler = make_lambda_handler(app)

def handler(event, context):
    """
    Main Lambda handler that routes between:
    1. Async scraping invocations (action='scrape')
    2. API Gateway web requests (forwarded to Flask)
    """
    import json
    
    # Check if this is an async scraping invocation
    if event.get('action') == 'scrape':
        print(f"🎯 Async scraping invocation for task {event.get('task_id')}")
        
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
        }
    
    # Otherwise, forward to Flask for normal web/API requests
    return _flask_handler(event, context)

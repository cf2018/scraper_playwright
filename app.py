"""
Flask Web Application for Google Maps Business Scraper
A modern web interface for scraping business information from Google Maps
"""

from flask import Flask, render_template, request, jsonify, send_file
import asyncio
import json
import os
from datetime import datetime
from scrape_businesses_maps import BusinessScraper
import threading
import uuid

app = Flask(__name__)

# Store active scraping tasks
active_tasks = {}

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
def index():
    """Main page with search form"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def start_scraping():
    """Start a new scraping task"""
    try:
        data = request.get_json()
        search_query = data.get('search_query', '').strip()
        max_results = min(int(data.get('max_results', 10)), 50)  # Limit to 50 max
        
        if not search_query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        task = ScrapingTask(task_id, search_query, max_results)
        active_tasks[task_id] = task
        
        # Start scraping in background thread
        thread = threading.Thread(target=run_scraping_task, args=(task,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id, 'status': 'started'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """Get status of a scraping task"""
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
        'start_time': task.start_time.isoformat(),
        'results': task.results
    }
    
    if task.end_time:
        response['end_time'] = task.end_time.isoformat()
        response['duration'] = str(task.end_time - task.start_time)
    
    if task.error:
        response['error'] = task.error
    
    if task.json_file:
        response['json_file'] = task.json_file
    
    return jsonify(response)

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

def run_scraping_task(task):
    """Run the scraping task in an async context"""
    try:
        # Set up event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the scraping
        loop.run_until_complete(execute_scraping(task))
        
    except Exception as e:
        task.status = "error"
        task.error = str(e)
        task.end_time = datetime.now()
    finally:
        if loop:
            loop.close()

async def execute_scraping(task):
    """Execute the actual scraping"""
    try:
        task.status = "running"
        
        # Create scraper instance
        scraper = BusinessScraper(task.search_query)
        
        # Custom scraper to track progress
        original_extract = scraper.extract_business_info
        
        async def track_progress_extract(page):
            result = await original_extract(page)
            # Don't modify task.results here - let the main scraper handle duplicates
            # Just update the progress based on the scraper's actual business_data length
            task.total_found = len(scraper.business_data)
            task.duplicates_found = scraper.duplicates_found
            task.progress = min(100, (task.total_found / task.max_results) * 100)
            return result
        
        scraper.extract_business_info = track_progress_extract
        
        # Start scraping
        businesses = await scraper.scrape_businesses(max_results=task.max_results)
        
        # Save results and update task with final stats
        task.json_file = scraper.save_to_json()
        task.duplicates_found = scraper.duplicates_found
        task.status = "completed"
        task.end_time = datetime.now()
        
        # Clean up results for display (remove huge nested objects)
        task.results = []
        for business in businesses:
            clean_business = {}
            for key, value in business.items():
                if key != 'website_extraction':  # Skip heavy nested data
                    clean_business[key] = value
                else:
                    # Just keep summary
                    if isinstance(value, dict):
                        clean_business['website_contacts_found'] = value.get('total_contacts_found', {})
            task.results.append(clean_business)
        
    except Exception as e:
        task.status = "error"
        task.error = str(e)
        task.end_time = datetime.now()

if __name__ == '__main__':
    # Ensure templates and static directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

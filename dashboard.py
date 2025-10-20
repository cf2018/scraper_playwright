"""
Web Dashboard for Business Scraper Database

A Flask-based web interface to view, filter, and manage scraped business data.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import json
import os

# Import our database modules
try:
    from database import BusinessDatabase
    mongodb_available = True
except:
    mongodb_available = False

from json_database import JSONDatabase

app = Flask(__name__)
CORS(app)

def get_database():
    """Get the appropriate database (MongoDB or JSON fallback)."""
    if mongodb_available:
        try:
            db = BusinessDatabase()
            if db.collection is not None:
                return db, "MongoDB"
        except:
            pass
    
    # Fall back to JSON database
    return JSONDatabase(), "JSON"

@app.route('/')
def dashboard():
    """Main dashboard page."""
    db, db_type = get_database()
    
    try:
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
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/businesses')
def api_businesses():
    """API endpoint to get filtered businesses."""
    db, db_type = get_database()
    
    try:
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
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
def api_update_contact(business_id):
    """API endpoint to update contact status."""
    db, db_type = get_database()
    
    try:
        data = request.get_json()
        contacted = data.get('contacted', True)
        
        success = db.mark_contacted(business_id, contacted)
        
        return jsonify({
            'success': success,
            'message': f'Business marked as {"contacted" if contacted else "not contacted"}'
        })
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
        # Get all businesses and find the one with matching ID
        businesses = db.get_businesses(limit=1000)
        business = None
        
        for b in businesses:
            if str(b.get('_id')) == str(business_id):
                business = b
                break
        
        if not business:
            return "Business not found", 404
        
        return render_template('business_detail.html', 
                             business=business,
                             db_type=db_type)
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/export')
def export_page():
    """Export page."""
    db, db_type = get_database()
    
    try:
        keywords = db.get_search_keywords()
        return render_template('export.html', 
                             keywords=keywords,
                             db_type=db_type)
    finally:
        if hasattr(db, 'close'):
            db.close()

@app.route('/api/export')
def api_export():
    """API endpoint to export businesses as JSON."""
    db, db_type = get_database()
    
    try:
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

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("🚀 Starting Business Scraper Dashboard...")
    print("📊 Access the dashboard at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
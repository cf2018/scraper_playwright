#!/usr/bin/env python3
"""
Demo script to showcase the Flask web application
"""

import os
import sys
import time
import webbrowser
from threading import Timer

def open_browser():
    """Open the web browser after a delay"""
    print("🌐 Opening web browser...")
    webbrowser.open('http://localhost:5000')

def main():
    print("=" * 60)
    print("🚀 GOOGLE MAPS BUSINESS SCRAPER - WEB DEMO")
    print("=" * 60)
    print()
    print("This demo will:")
    print("✅ Start the Flask web application")
    print("✅ Open your web browser automatically")
    print("✅ Show you the modern web interface")
    print()
    print("Features you'll see:")
    print("🎨 Beautiful modern design with gradients")
    print("📱 Responsive mobile-friendly interface")
    print("⚡ Real-time progress tracking")
    print("📊 Elegant business card results")
    print("📁 JSON download capability")
    print()
    print("Example searches to try:")
    print("• 'plomeros Buenos Aires'")
    print("• 'restaurants New York'")
    print("• 'dentistas Santiago del Estero'")
    print("• 'agencias marketing digital CABA'")
    print()
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("❌ Error: app.py not found. Please run this from the project directory.")
        sys.exit(1)
    
    if not os.path.exists('templates/index.html'):
        print("❌ Error: Web template not found. Please ensure templates are in place.")
        sys.exit(1)
    
    # Schedule browser opening
    Timer(3.0, open_browser).start()
    
    print("🌟 Starting Flask application...")
    print("📍 Web interface will be available at: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop the demo")
    print()
    
    # Import and run the Flask app
    try:
        from app import app
        app.run(debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Demo stopped. Thank you for trying the web interface!")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("💡 Try running: pip install flask")

if __name__ == "__main__":
    main()

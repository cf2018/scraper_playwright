#!/bin/bash

# Flask Web App Launcher for Google Maps Business Scraper
# This script starts the Flask web application

echo "🚀 Starting Google Maps Business Scraper Web App..."
echo "====================================================="

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
fi

# Install dependencies if needed
echo "📋 Checking dependencies..."
pip install -q flask

# Create necessary directories
mkdir -p json_output
mkdir -p templates
mkdir -p static

echo "🌐 Starting Flask application..."
echo "📍 The web interface will be available at: http://localhost:5000"
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

# Start the Flask app
python app.py

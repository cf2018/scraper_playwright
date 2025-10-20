# Google Maps Business Scraper - Web Interface

A modern, beautiful web application for scraping business information from Google Maps. This Flask-based web interface provides an intuitive way to search for businesses and view results in a clean, modern format.

## Features

🎨 **Modern UI**: Beautiful, responsive design with gradient backgrounds and smooth animations
📱 **Mobile-Friendly**: Fully responsive interface that works on all devices
⚡ **Real-Time Progress**: Live progress tracking with status updates
📊 **Rich Results Display**: Organized business cards with contact information
📁 **JSON Export**: Download complete results as JSON files
🔍 **Smart Contact Extraction**: WhatsApp, email, Instagram, phone, and website extraction

## Quick Start

### Option 1: Use the Launcher Script
```bash
./start_webapp.sh
```

### Option 2: Manual Setup
```bash
# Install dependencies
pip install flask

# Start the application
python app.py
```

The web interface will be available at: http://localhost:5000

## How to Use

1. **Open your browser** and navigate to http://localhost:5000
2. **Enter a search query** (e.g., "plomeros Buenos Aires", "restaurants New York")
3. **Set max results** (1-50 businesses)
4. **Click "Start Scraping"** and watch the real-time progress
5. **View results** in beautiful business cards
6. **Download JSON** for further processing

## Web Interface Features

### 🎯 Search Form
- **Smart Input Validation**: Ensures valid search queries
- **Adjustable Results**: Choose between 1-50 results
- **Instant Feedback**: Real-time validation and error messages

### 📈 Progress Tracking
- **Real-Time Updates**: See progress as businesses are found
- **Status Indicators**: Visual status badges (Running, Completed, Error)
- **Live Counter**: Number of businesses found updates in real-time

### 🎴 Results Display
- **Business Cards**: Each business displayed in an elegant card format
- **Contact Icons**: Font Awesome icons for different contact methods
- **Smart Links**: Clickable phone numbers, emails, and websites
- **WhatsApp Integration**: Direct links to WhatsApp conversations
- **Responsive Grid**: Automatically adjusts to screen size

### 📱 Mobile Experience
- **Touch-Friendly**: Large buttons and touch targets
- **Responsive Design**: Adapts to mobile screens
- **Fast Loading**: Optimized for mobile networks

## API Endpoints

The Flask app provides these REST API endpoints:

### `POST /api/scrape`
Start a new scraping task
```json
{
  "search_query": "plomeros Buenos Aires",
  "max_results": 10
}
```

### `GET /api/status/<task_id>`
Get real-time status of a scraping task
```json
{
  "task_id": "uuid",
  "status": "running",
  "progress": 45,
  "total_found": 4,
  "results": [...]
}
```

### `GET /api/download/<task_id>`
Download JSON results for a completed task

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Frontend**: Modern HTML5, CSS3, JavaScript
- **Styling**: Custom CSS with gradients and animations
- **Icons**: Font Awesome 6
- **Scraping**: Playwright (from existing scraper modules)
- **Real-Time**: AJAX polling for progress updates

## Customization

### Styling
Modify `/templates/index.html` to customize the appearance:
- Change color gradients in the CSS
- Adjust card layouts and spacing
- Modify animations and transitions

### Functionality
Edit `app.py` to customize:
- Maximum results limit (currently 50)
- Progress update frequency
- Result data formatting

## File Structure

```
├── app.py                 # Main Flask application
├── start_webapp.sh       # Launcher script
├── templates/
│   └── index.html        # Web interface template
├── json_output/          # Scraped results storage
├── scrape_businesses_maps.py  # Core scraper
└── extract_contact_info.py   # Contact extractor
```

## Production Deployment

For production deployment, consider:

1. **Use a production WSGI server** (e.g., Gunicorn)
2. **Set up reverse proxy** (e.g., Nginx)
3. **Configure environment variables**
4. **Enable HTTPS**
5. **Set up proper logging**

Example with Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Troubleshooting

### Common Issues

1. **Flask not found**: Run `pip install flask`
2. **Playwright browser not installed**: Run `playwright install chromium`
3. **Permission denied**: Run `chmod +x start_webapp.sh`
4. **Port already in use**: Change port in `app.py` or kill existing process

### Browser Compatibility

The web interface supports:
- ✅ Chrome/Chromium 80+
- ✅ Firefox 75+
- ✅ Safari 13+
- ✅ Edge 80+

## Contributing

Feel free to contribute by:
- Improving the UI/UX design
- Adding new features
- Optimizing performance
- Fixing bugs

## License

This project is part of the Google Maps Business Scraper suite. Use responsibly and respect website terms of service.

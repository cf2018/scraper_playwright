"""
Google Maps Business Scraper
Automates the extraction of business information from Google Maps
Enhanced with website contact information extraction
"""

import asyncio
import json
import re
import sys
import argparse
from playwright.async_api import async_playwright
from datetime import datetime
from extract_contact_info import ContactExtractor
from database import BusinessDatabase
from json_database import JSONDatabase

class BusinessScraper:
    def __init__(self, search_query=None, headless=None, slow_mo=None, timeout=None, viewport=None):
        self.search_query = search_query
        self.business_data = []
        self.duplicates_found = 0  # Track duplicates for statistics
        self.db_saved_count = 0  # Track businesses saved to database
        self.db_duplicate_count = 0  # Track database duplicates
        self.db = None  # Database connection
        
        # Auto-detect Lambda environment for headless mode
        if headless is None:
            headless = self._is_lambda_environment()
        
        # Lambda-optimized settings
        self.headless = headless
        self.slow_mo = slow_mo if slow_mo is not None else (0 if self._is_lambda_environment() else 50)
        self.timeout = timeout if timeout is not None else (30000 if self._is_lambda_environment() else 60000)
        self.viewport = viewport if viewport is not None else {'width': 1280, 'height': 720}
        
        # Initialize contact extractor for website scraping
        self.contact_extractor = ContactExtractor(
            headless=self.headless, 
            timeout=min(self.timeout, 10000)  # Shorter timeout for contact extraction
        )
        
        # Initialize database connection
        self._initialize_database()
    
    def _is_lambda_environment(self):
        """Detect if running in AWS Lambda environment."""
        import os
        return (
            os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None or
            os.environ.get('LAMBDA_ENVIRONMENT') == 'true' or
            os.environ.get('_LAMBDA_SERVER_PORT') is not None
        )
        
    def _initialize_database(self):
        """Initialize database connection with fallback."""
        try:
            # Try MongoDB first
            self.db = BusinessDatabase()
            if self.db.collection is None:
                raise Exception("MongoDB not available")
            print("✅ Connected to MongoDB for individual saves")
        except Exception as e:
            print(f"⚠️ MongoDB not available ({e}), using JSON database")
            self.db = JSONDatabase()
            print("✅ Connected to JSON database for individual saves")
    
    def _save_business_to_db(self, business_data, search_query=None):
        """Save a single business to database immediately."""
        try:
            # Use provided search query or fall back to instance variable
            query = search_query or self.search_query
            if self.db.save_business(business_data, query):
                self.db_saved_count += 1
                print(f"💾 Saved to database: {business_data.get('name', 'Unknown')}")
                return True
            else:
                self.db_duplicate_count += 1
                print(f"🔄 Already in database: {business_data.get('name', 'Unknown')}")
                return False
        except Exception as e:
            print(f"❌ Database save error for {business_data.get('name', 'Unknown')}: {e}")
            return False
    
    def close_database(self):
        """Close database connection."""
        if self.db and hasattr(self.db, 'close'):
            self.db.close()
        
    async def scrape_businesses(self, search_query=None, max_results=10):
        """Scrape business information from Google Maps"""
        # Use provided search query or fall back to instance variable
        query = search_query or self.search_query
        if not query:
            raise ValueError("Search query is required")
        
        async with async_playwright() as p:
            # Launch browser with Lambda-optimized settings
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
            
            # Add Lambda-specific args if in Lambda environment
            if self._is_lambda_environment():
                launch_args.extend([
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-background-networking',
                    '--memory-pressure-off'
                ])
            
            browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=launch_args
            )
            
            # Enhanced context with more realistic browser fingerprint
            context = await browser.new_context(
                viewport=self.viewport,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='es-AR',  # Argentine Spanish for more natural browsing
                timezone_id='America/Argentina/Buenos_Aires',
                permissions=['geolocation'],
                geolocation={'latitude': -34.6037, 'longitude': -58.3816},  # Buenos Aires coordinates
                extra_http_headers={
                    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Ch-Ua': '"Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # Set timeout for all operations
            context.set_default_timeout(self.timeout)
            page = await context.new_page()
            
            try:
                # Navigate to Google Maps
                print("Navigating to Google Maps...")
                await page.goto("https://www.google.com/maps")
                print("Page loaded, waiting for network to settle...")
                
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    print("✓ Network idle achieved")
                except:
                    print("⚠ Network didn't settle, continuing anyway...")
                
                # Handle common Google Maps interferences
                print("Checking for dialogs and popups...")
                
                # Handle cookie consent dialog
                try:
                    cookie_buttons = [
                        'button:has-text("Accept all")',
                        'button:has-text("Aceptar todo")',
                        'button:has-text("I agree")',
                        'button:has-text("Acepto")',
                        '[aria-label*="Accept"]',
                        '[aria-label*="Aceptar"]'
                    ]
                    
                    for button_selector in cookie_buttons:
                        button = page.locator(button_selector).first
                        if await button.count() > 0:
                            print(f"✓ Found and clicking consent button: {button_selector}")
                            try:
                                await button.click(timeout=5000)  # 5 second timeout for cookie clicks
                                await page.wait_for_timeout(1000)
                                break
                            except Exception as click_error:
                                print(f"⚠ Could not click consent button: {click_error}")
                                continue
                except Exception as e:
                    print(f"No cookie dialog found or error: {e}")
                
                # Handle traffic/location dialogs
                try:
                    dismiss_buttons = [
                        'button[aria-label*="Dismiss"]',
                        'button[aria-label*="Close"]',
                        'button[aria-label*="Cerrar"]',
                        '[data-value="dismiss"]',
                        'button:has-text("Not now")',
                        'button:has-text("Ahora no")',
                        '[aria-label*="No thanks"]'
                    ]
                    
                    for button_selector in dismiss_buttons:
                        button = page.locator(button_selector).first
                        if await button.count() > 0:
                            print(f"✓ Found and dismissing dialog: {button_selector}")
                            try:
                                await button.click(timeout=5000)  # 5 second timeout for dialog clicks
                                await page.wait_for_timeout(1000)
                                break
                            except Exception as click_error:
                                print(f"⚠ Could not click dialog button: {click_error}")
                                continue
                except Exception as e:
                    print(f"No dismiss dialogs found: {e}")
                
                # Wait a bit more for any animations to complete
                await page.wait_for_timeout(2000)
                
                # Search for businesses with multiple selector strategies
                print(f"Searching for: {query}...")
                
                search_selectors = [
                    'input[id="searchboxinput"]',
                    'input[name="q"]',
                    'input[placeholder*="Search"]',
                    'input[placeholder*="Buscar"]',
                    'input[data-value="search"]',
                    'input[type="text"]'
                ]
                
                search_success = False
                for selector in search_selectors:
                    try:
                        print(f"Trying search selector: {selector}")
                        search_box = page.locator(selector).first
                        
                        if await search_box.count() > 0:
                            print(f"✓ Found search box with selector: {selector}")
                            
                            # Clear any existing text and fill
                            await search_box.click()
                            await search_box.clear()
                            await search_box.fill(query)
                            print(f"✓ Filled search box with: {self.search_query}")
                            
                            # Try multiple ways to submit
                            try:
                                await search_box.press("Enter")
                                print("✓ Pressed Enter")
                            except:
                                # Try clicking search button as fallback
                                search_button = page.locator('button[data-value="search"]').first
                                if await search_button.count() > 0:
                                    await search_button.click()
                                    print("✓ Clicked search button")
                            
                            search_success = True
                            break
                            
                    except Exception as e:
                        print(f"Selector {selector} failed: {e}")
                        continue
                
                if not search_success:
                    print("❌ Could not find search box with any selector!")
                    # Take a screenshot for debugging
                    await page.screenshot(path="debug_search_failure.png")
                    print("📸 Screenshot saved as debug_search_failure.png")
                    return []
                
                print("Waiting for search results...")
                await page.wait_for_timeout(5000)
                
                # Wait for search results to load with debugging
                print("Waiting for search results to load...")
                
                result_selectors = [
                    '[role="main"]',
                    '[data-value="search results"]',
                    'div[class*="search"]',
                    '[aria-label*="Results"]',
                    '[aria-label*="Resultados"]'
                ]
                
                results_found = False
                for selector in result_selectors:
                    try:
                        print(f"Checking for results with selector: {selector}")
                        await page.wait_for_selector(selector, timeout=5000)
                        print(f"✓ Found results container: {selector}")
                        results_found = True
                        break
                    except:
                        print(f"Selector {selector} timed out")
                        continue
                
                if not results_found:
                    print("❌ Could not find results container!")
                    await page.screenshot(path="debug_no_results.png")
                    print("📸 Screenshot saved as debug_no_results.png")
                    return []
                
                # Get all business result links from the results panel with debugging
                print("Looking for business links...")
                
                # Strategy: Collect ALL unique business links from different selectors
                all_business_links = set()  # Use set to automatically handle duplicates
                link_selectors = [
                    # Primary selectors - most reliable
                    'div[role="main"] a[href*="/maps/place/"]',
                    'feed[aria-label*="Resultados"] a[href*="/maps/place/"]',
                    '[role="feed"] a[href*="/maps/place/"]',
                    # Secondary selectors - broader search
                    'a[href*="/maps/place/"]',
                    # Alternative selectors for different layouts
                    '[data-result-index] a',
                    'div[class*="result"] a',
                    # Generic link selectors within results
                    'main a[href*="/place/"]',
                    '[role="main"] [role="link"][href*="/place/"]',
                    # More specific for Google Maps structure
                    'div[class*="fontHeadlineSmall"] a',
                    'h3 a[href*="/maps/place/"]',
                    'div[class*="lI9IFe"] a'
                ]
                
                # Collect all unique business URLs and their corresponding elements
                unique_business_data = {}  # URL -> (element, business_name)
                
                for selector in link_selectors:
                    try:
                        print(f"Trying link selector: {selector}")
                        links = await page.locator(selector).all()
                        print(f"   Found {len(links)} potential links")
                        
                        for link in links:
                            try:
                                href = await link.get_attribute("href")
                                if href and "/maps/place/" in href:
                                    # Extract a clean business identifier from URL
                                    business_id = href.split("/maps/place/")[1].split("/")[0].split("?")[0]
                                    
                                    # Get business name for debugging
                                    try:
                                        business_name = await link.inner_text()
                                        business_name = business_name.strip()[:50] + "..." if len(business_name) > 50 else business_name.strip()
                                    except:
                                        business_name = "Unknown"
                                    
                                    # Only add if we haven't seen this business before
                                    if business_id not in unique_business_data:
                                        unique_business_data[business_id] = (link, business_name)
                                        print(f"     ✓ Added unique business: {business_name}")
                                    else:
                                        print(f"     ⚠ Skipping duplicate: {business_name}")
                            except Exception as e:
                                print(f"     Error processing link: {e}")
                                continue
                                
                    except Exception as e:
                        print(f"Link selector {selector} failed: {e}")
                        continue
                
                # Convert to list of elements
                business_links = [data[0] for data in unique_business_data.values()]
                print(f"🎯 Found {len(business_links)} unique business links total")
                
                # If we don't have enough links, try scrolling to load more
                if len(business_links) < max_results:
                    print(f"⚠️ Only found {len(business_links)} unique links, but need {max_results}. Trying to scroll for more...")
                    try:
                        # Target the specific feed element that contains the results
                        feed_selector = 'feed[aria-label*="Resultados"]'
                        results_feed = page.locator(feed_selector).first
                        
                        # Fallback to main panel if feed not found
                        if await results_feed.count() == 0:
                            results_feed = page.locator('[role="main"]').first
                            feed_selector = '[role="main"]'
                        
                        if await results_feed.count() > 0:
                            print(f"   🎯 Targeting scrollable element: {feed_selector}")
                            previous_count = len(unique_business_data)
                            max_scroll_attempts = 20  # Increased scroll attempts
                            no_new_results_count = 0  # Track consecutive attempts with no new results
                            
                            for scroll_attempt in range(max_scroll_attempts):
                                print(f"   Scroll attempt {scroll_attempt + 1}/{max_scroll_attempts}...")
                                
                                # Enhanced scrolling strategy based on Playwright best practices
                                try:
                                    # First, ensure the feed element is still visible and scrollable
                                    await results_feed.wait_for(state="visible", timeout=5000)
                                    
                                    # Get current scroll position to detect if we can scroll more
                                    current_scroll_top = await results_feed.evaluate("el => el.scrollTop")
                                    current_scroll_height = await results_feed.evaluate("el => el.scrollHeight")
                                    current_client_height = await results_feed.evaluate("el => el.clientHeight")
                                    
                                    print(f"      📏 Scroll metrics: top={current_scroll_top}, height={current_scroll_height}, client={current_client_height}")
                                    
                                    # Store initial scroll height to detect content changes
                                    initial_scroll_height = current_scroll_height
                                    
                                    # Check if we're already at the bottom
                                    if current_scroll_top + current_client_height >= current_scroll_height - 50:
                                        print(f"      ⬇️ Already near bottom, trying different scroll approach...")
                                        
                                        # Use page.mouse.wheel directly on the feed element
                                        feed_box = await results_feed.bounding_box()
                                        if feed_box:
                                            center_x = feed_box['x'] + feed_box['width'] / 2
                                            center_y = feed_box['y'] + feed_box['height'] * 0.8  # Scroll near bottom of feed
                                            
                                            await page.mouse.move(center_x, center_y)
                                            await page.wait_for_timeout(200)
                                            
                                            # Use smaller, more frequent scrolls
                                            for micro_scroll in range(10):
                                                await page.mouse.wheel(0, 200)  # Smaller scroll increments
                                                await page.wait_for_timeout(100)
                                        
                                    else:
                                        # Normal scrolling approach
                                        feed_box = await results_feed.bounding_box()
                                        
                                        if feed_box:
                                            # Position mouse in the center of the feed
                                            center_x = feed_box['x'] + feed_box['width'] / 2
                                            center_y = feed_box['y'] + feed_box['height'] / 2
                                            
                                            print(f"      🖱️ Mouse wheel scrolling at ({center_x:.0f}, {center_y:.0f})")
                                            
                                            # Move mouse to center of feed
                                            await page.mouse.move(center_x, center_y)
                                            await page.wait_for_timeout(200)
                                            
                                            # Progressive scrolling with increasing amounts
                                            scroll_amount = 300 + (scroll_attempt * 50)  # Increase scroll amount each attempt
                                            for wheel_scroll in range(3):
                                                await page.mouse.wheel(0, scroll_amount)
                                                await page.wait_for_timeout(200)
                                        
                                        else:
                                            print(f"      ⚠ Could not get feed bounding box")
                                            # Direct element scrolling as fallback
                                            await results_feed.evaluate("el => el.scrollBy(0, 800)")
                                    
                                    # Wait for content to load - longer wait for later attempts
                                    wait_time = 2000 + (scroll_attempt * 500)  # Increase wait time for later attempts
                                    await page.wait_for_timeout(wait_time)
                                    
                                    # Try to scroll to the very bottom to trigger lazy loading
                                    await results_feed.evaluate("el => el.scrollTop = el.scrollHeight")
                                    await page.wait_for_timeout(1000)
                                    
                                    # Check if scroll height increased (new content loaded)
                                    new_scroll_height = await results_feed.evaluate("el => el.scrollHeight")
                                    if new_scroll_height > initial_scroll_height:
                                        print(f"      📈 Scroll height increased: {initial_scroll_height} → {new_scroll_height}")
                                    else:
                                        print(f"      📉 No scroll height change: {new_scroll_height}")
                                        
                                except Exception as scroll_error:
                                    print(f"      ❌ Error in enhanced scroll: {scroll_error}")
                                    # Fallback to basic mouse wheel
                                    try:
                                        await page.mouse.move(640, 360)
                                        await page.mouse.wheel(0, 800)
                                        await page.wait_for_timeout(2000)
                                    except:
                                        print(f"      ❌ Fallback scroll also failed")
                                
                                # Re-scan for new unique businesses
                                new_businesses_found = 0
                                for selector in link_selectors:
                                    try:
                                        links = await page.locator(selector).all()
                                        
                                        for link in links:
                                            try:
                                                href = await link.get_attribute("href")
                                                if href and "/maps/place/" in href:
                                                    business_id = href.split("/maps/place/")[1].split("/")[0].split("?")[0]
                                                    
                                                    if business_id not in unique_business_data:
                                                        try:
                                                            business_name = await link.inner_text()
                                                            business_name = business_name.strip()[:50] + "..." if len(business_name) > 50 else business_name.strip()
                                                        except:
                                                            business_name = "Unknown"
                                                        
                                                        unique_business_data[business_id] = (link, business_name)
                                                        new_businesses_found += 1
                                                        print(f"     ✅ New business found: {business_name}")
                                            except:
                                                continue
                                    except:
                                        continue
                                
                                current_count = len(unique_business_data)
                                
                                # Check for the "Back to top" button which indicates more results were loaded
                                try:
                                    back_to_top_button = page.locator('button:has-text("Volver al principio")').first
                                    if await back_to_top_button.count() > 0:
                                        print(f"   🔝 'Volver al principio' button detected - more results have been loaded!")
                                except:
                                    pass
                                
                                if new_businesses_found > 0:
                                    print(f"   ✓ Found {new_businesses_found} new businesses (total: {current_count})")
                                    previous_count = current_count
                                    no_new_results_count = 0  # Reset counter
                                    
                                    # Update business_links with new data
                                    business_links = [data[0] for data in unique_business_data.values()]
                                    
                                    if current_count >= max_results:
                                        print(f"   🎯 Found enough unique businesses ({current_count}) after scrolling")
                                        break
                                else:
                                    no_new_results_count += 1
                                    print(f"   ⚠️ No new businesses found (attempt {no_new_results_count})")
                                    
                                    # If we haven't found new results in 4 consecutive attempts, try different approach
                                    if no_new_results_count >= 4:
                                        print(f"   📍 Trying alternative approaches...")
                                        
                                        # Look for "Load more" type buttons or pagination
                                        load_more_selectors = [
                                            'button:has-text("Más resultados")',
                                            'button:has-text("Ver más")',
                                            'button:has-text("Load more")',
                                            'button:has-text("Show more")',
                                            'button:has-text("Cargar más")',
                                            '[role="button"]:has-text("más")',
                                            '[aria-label*="more"]',
                                            '[aria-label*="más"]',
                                            '[aria-label*="Load"]'
                                        ]
                                        
                                        button_found = False
                                        for button_selector in load_more_selectors:
                                            try:
                                                load_button = page.locator(button_selector).first
                                                if await load_button.count() > 0:
                                                    print(f"   🔘 Found load more button: {button_selector}")
                                                    await load_button.click()
                                                    await page.wait_for_timeout(3000)
                                                    button_found = True
                                                    no_new_results_count = 0  # Reset counter
                                                    break
                                            except:
                                                continue
                                        
                                        if not button_found and no_new_results_count >= 6:
                                            print(f"   ⛔ No more results seem to be loading. Google Maps may have limited results for this search.")
                                            break
                            
                            # Final update
                            business_links = [data[0] for data in unique_business_data.values()]
                            print(f"   📊 Final scroll summary: Found {len(business_links)} unique businesses after {scroll_attempt + 1} scroll attempts")
                        else:
                            print(f"   ❌ Could not find scrollable results container")
                            
                    except Exception as e:
                        print(f"   Error while scrolling: {e}")
                
                if not business_links:
                    print("❌ No business links found!")
                    await page.screenshot(path="debug_no_links.png")
                    print("📸 Screenshot saved as debug_no_links.png")
                    
                    # Additional debugging - show page content
                    print("🔍 DEBUG: Checking page content...")
                    try:
                        page_title = await page.title()
                        print(f"   Page title: {page_title}")
                        
                        # Check if we're on the right type of page
                        if "maps" not in page_title.lower():
                            print("   ⚠️ May not be on a Google Maps page")
                        
                        # Look for any links at all
                        all_links = await page.locator('a').count()
                        print(f"   Total links on page: {all_links}")
                        
                        # Look specifically for any place-related content
                        place_content = await page.locator('[href*="place"]').count()
                        print(f"   Links containing 'place': {place_content}")
                        
                    except Exception as debug_error:
                        print(f"   Debug error: {debug_error}")
                    
                    return []
                
                print(f"✅ Found {len(business_links)} business results total")
                print(f"🎯 Target: {max_results} unique businesses, Will process: {min(max_results, len(business_links))}")
                
                # Process each business with enhanced debugging
                for i, link in enumerate(business_links[:max_results]):
                    try:
                        print(f"\n🔍 Processing business {i+1}/{min(max_results, len(business_links))}...")
                        print(f"📊 Current stats: {len(self.business_data)} unique businesses, {self.duplicates_found} duplicates")
                        
                        # Check if we have enough unique businesses
                        if len(self.business_data) >= max_results:
                            print(f"🎉 Target reached! Found {len(self.business_data)} unique businesses")
                            break
                        
                        # Get link text for debugging
                        try:
                            link_text = await link.inner_text()
                            print(f"Link text: {link_text[:50]}...")
                        except:
                            print("Could not get link text")
                        
                        # Click on the business link
                        print("Clicking on business link...")
                        await link.click()
                        await page.wait_for_timeout(3000)
                        
                        # Verify we're on a business page
                        current_url = page.url
                        if "/maps/place/" not in current_url:
                            print(f"⚠ Not on a business page, URL: {current_url}")
                            continue
                        
                        print("✓ Successfully navigated to business page")
                        
                        # Extract business information
                        print("Extracting business information...")
                        business_data = await self.extract_business_info(page)
                        if business_data and business_data.get('name'):
                            # Skip website enhancement - causes browser context issues when scraping multiple businesses
                            # Website extraction is disabled to maintain browser stability during multi-business scraping
                            print("  ℹ️ Skipping website extraction to maintain browser stability")
                            enhanced_data = business_data
                            
                            # Check for duplicates before adding
                            if self._is_duplicate_business(enhanced_data):
                                self.duplicates_found += 1
                                print(f"  ⚠️ Skipping duplicate business: {enhanced_data['name']}")
                            else:
                                self.business_data.append(enhanced_data)
                                print(f"  ✅ Extracted: {enhanced_data['name']}")
                                print(f"     Phone: {enhanced_data.get('phone', 'N/A')}")
                                print(f"     Website: {enhanced_data.get('url', 'N/A')}")
                                print(f"     Email: {enhanced_data.get('email', 'N/A')}")
                                print(f"     WhatsApp: {enhanced_data.get('whatsapp', 'N/A')}")
                                
                                # Save immediately to database (lambda-friendly)
                                self._save_business_to_db(enhanced_data, query)
                                print(f"     Instagram: {enhanced_data.get('instagram', 'N/A')}")
                        else:
                            print("  ❌ Could not extract valid business data")
                        
                        # Go back to search results - check if page is still valid first
                        if i < len(business_links) - 1:  # Don't go back on last iteration
                            print("Going back to search results...")
                            try:
                                # Check if page/context is still valid
                                if page.is_closed():
                                    print("⚠️ Page was closed, cannot go back")
                                    raise Exception("Page closed")
                                
                                await page.go_back()
                                await page.wait_for_timeout(3000)
                                
                                # Wait for results to load again
                                try:
                                    await page.wait_for_selector('[role="main"]', timeout=10000)
                                    print("✓ Back on search results page")
                                except:
                                    print("⚠ Could not verify we're back on results page")
                            except Exception as go_back_error:
                                print(f"⚠️ Could not go back ({go_back_error}), re-navigating to search...")
                                # Re-navigate to search results as fallback
                                try:
                                    await page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")
                                    await page.wait_for_timeout(3000)
                                    await page.wait_for_selector('[role="main"]', timeout=10000)
                                    print("✓ Re-navigated to search results")
                                except Exception as nav_error:
                                    print(f"❌ Failed to re-navigate: {nav_error}")
                                    raise  # Re-raise to trigger outer error handling
                        
                    except Exception as e:
                        print(f"  ❌ Error processing business {i+1}: {e}")
                        # Take screenshot on error (skip in Lambda and if page is closed)
                        if not self._is_lambda_environment():
                            try:
                                if not page.is_closed():
                                    await page.screenshot(path=f"debug_error_business_{i+1}.png")
                                    print(f"📸 Error screenshot saved as debug_error_business_{i+1}.png")
                            except:
                                print("⚠️ Could not save debug screenshot")
                        
                        # Try to recover - check if browser/page is still usable
                        try:
                            if i < len(business_links) - 1:  # Don't try to recover on last iteration
                                print("Attempting to recover...")
                                
                                # Check if page is closed
                                if page.is_closed():
                                    print("⚠️ Page is closed, cannot continue scraping")
                                    break  # Exit the loop, can't recover from closed page
                                
                                # Try to go back to search results
                                print("Trying to go back to search results...")
                                try:
                                    await page.go_back(timeout=5000)
                                    await page.wait_for_timeout(2000)
                                    print("✓ Went back successfully")
                                except:
                                    # If go_back fails, try re-navigating
                                    print("Go back failed, trying to re-navigate...")
                                    try:
                                        await page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}", timeout=10000)
                                        await page.wait_for_timeout(3000)
                                        print("✓ Re-navigated to search")
                                    except Exception as nav_error:
                                        print(f"❌ Could not recover: {nav_error}")
                                        break  # Can't recover, exit loop
                        except Exception as recovery_error:
                            print(f"❌ Recovery failed: {recovery_error}")
                            break  # Can't recover, exit loop
                        except:
                            print("Could not go back after error")
                        continue
                
                # Summary after processing all businesses
                print(f"\n📊 SCRAPING SUMMARY:")
                print(f"   • Processed: {min(len(business_links), max_results)} business links")
                print(f"   • Unique businesses found: {len(self.business_data)}")
                print(f"   • Duplicates filtered: {self.duplicates_found}")
                print(f"   • Target was: {max_results}")
                
                if len(self.business_data) < max_results:
                    print(f"⚠️ Found fewer unique businesses than requested. This could be due to:")
                    print(f"   • Limited search results from Google Maps")
                    print(f"   • High number of duplicate businesses")
                    print(f"   • Errors during extraction")
                
            except Exception as e:
                print(f"❌ Error during scraping: {e}")
                # Skip screenshot in Lambda environment to avoid errors
                if not self._is_lambda_environment():
                    try:
                        await page.screenshot(path="debug_final_error.png")
                        print("📸 Final error screenshot saved as debug_final_error.png")
                    except:
                        print("⚠️ Could not save debug screenshot")
                return []
            
            finally:
                await browser.close()
        
        return self.business_data
    
    async def extract_business_info(self, page):
        """Extract business information from the current page"""
        try:
            print("🔍 Starting data extraction...")
            business_data = {
                "name": None,
                "phone": None,
                "url": None,
                "email": None,
                "address": None,
                "rating": None,
                "reviews": None,
                "hours": None,
                "type": None,
                "instagram": None,
                "whatsapp": None
            }
            
            # Extract name with debugging
            try:
                print("Extracting business name...")
                name_selectors = [
                    # More specific selectors for business names on Google Maps
                    'h1[data-attrid="title"]',
                    'h1[class*="DUwDvf"]',  # Common class for business names
                    'h1[class*="x3AX1"]',   # Alternative class
                    'div[data-attrid="title"] h1',
                    'div[class*="lMbq3e"] h1',
                    'h1[class*="fontHeadlineLarge"]',
                    'h1[class*="fontHeadline"]:not(:has-text("Resultados"))',  # Exclude "Resultados"
                    '[data-value="title"] h1',
                    'h1',  # Fallback, but we'll filter out "Resultados"
                ]
                
                for selector in name_selectors:
                    try:
                        name_element = page.locator(selector).first
                        if await name_element.count() > 0:
                            name = await name_element.inner_text()
                            name = name.strip()
                            # Filter out generic/unwanted names
                            if name and name.lower() not in ['resultados', 'results', 'google maps', 'maps']:
                                business_data["name"] = name
                                print(f"✓ Found name: {name}")
                                break
                            else:
                                print(f"⚠ Skipping generic name: {name}")
                    except Exception as e:
                        print(f"Name selector {selector} failed: {e}")
                        continue
                
                if not business_data["name"]:
                    print("❌ Could not extract business name")
            except Exception as e:
                print(f"❌ Error extracting name: {e}")
            
            # Extract phone - more robust selectors with debugging
            try:
                print("Extracting phone number...")
                phone_selectors = [
                    # Direct phone button (most reliable based on investigation)
                    'button:has-text("Teléfono:")',
                    # Tel links
                    'a[href^="tel:"]',
                    # Data attributes
                    'button[data-item-id*="phone"]',
                    '[data-value*="phone"]',
                    # Generic Argentine phone patterns
                    'span[class*="fontBody"]',  # Generic selector for phone content
                    'div[class*="fontBody"]',
                    # Broader search for any phone-like content
                    '*:has-text("Teléfono")',
                    '*:has-text("Tel:")'
                ]
                
                for selector in phone_selectors:
                    try:
                        phone_element = page.locator(selector).first
                        if await phone_element.count() > 0:
                            # Try getting text content
                            phone_text = await phone_element.inner_text()
                            print(f"Checking selector {selector}: {phone_text}")
                            
                            # Extract phone using comprehensive regex for Argentine numbers
                            phone_number = self._extract_phone_from_text(phone_text)
                            if phone_number:
                                business_data["phone"] = phone_number
                                print(f"✓ Found phone: {business_data['phone']}")
                                break
                            
                            # If inner_text doesn't work, try href for tel: links
                            if selector.startswith('a[href^="tel:"]'):
                                href = await phone_element.get_attribute("href")
                                if href and href.startswith("tel:"):
                                    phone_number = self._extract_phone_from_tel_link(href)
                                    if phone_number:
                                        business_data["phone"] = phone_number
                                        print(f"✓ Found phone from tel link: {business_data['phone']}")
                                        break
                    except Exception as e:
                        print(f"Selector {selector} failed: {e}")
                        continue
                
                if not business_data["phone"]:
                    print("❌ Could not extract phone number")
            except Exception as e:
                print(f"❌ Error extracting phone: {e}")
            
            # Extract website - more robust selectors with debugging
            try:
                print("Extracting website...")
                website_selectors = [
                    'a[data-item-id*="authority"]',
                    'a[data-value="website"]',
                    'button:has-text("Sitio web")',
                    'a[href*=".com"]:not([href*="google"])',
                    'a[href*=".ar"]:not([href*="google"])'
                ]
                
                for selector in website_selectors:
                    website_element = page.locator(selector).first
                    if await website_element.count() > 0:
                        href = await website_element.get_attribute("href")
                        if href and not href.startswith("javascript:") and "google" not in href:
                            business_data["url"] = href
                            print(f"✓ Found website: {href}")
                            break
                
                if not business_data["url"]:
                    print("❌ Could not extract website")
            except Exception as e:
                print(f"❌ Error extracting website: {e}")
            
            # Extract Instagram - check for Instagram links
            try:
                print("Extracting Instagram...")
                instagram_selectors = [
                    'a[href*="instagram.com"]',
                    'a[href*="instagram"]',
                    'button:has-text("Instagram")',
                    'a[aria-label*="Instagram"]'
                ]
                
                for selector in instagram_selectors:
                    instagram_element = page.locator(selector).first
                    if await instagram_element.count() > 0:
                        href = await instagram_element.get_attribute("href")
                        if href and "instagram" in href.lower():
                            business_data["instagram"] = href
                            print(f"✓ Found Instagram: {href}")
                            break
                
                if not business_data["instagram"]:
                    print("❌ Could not extract Instagram")
            except Exception as e:
                print(f"❌ Error extracting Instagram: {e}")
            
            # Extract WhatsApp - check for WhatsApp links across entire page including action buttons
            try:
                print("Extracting WhatsApp...")
                whatsapp_selectors = [
                    # Direct WhatsApp links
                    'a[href*="wa.me"]',
                    'a[href*="whatsapp"]',
                    'a[href*="api.whatsapp.com"]',
                    # WhatsApp buttons and labels
                    'button:has-text("WhatsApp")',
                    'a[aria-label*="WhatsApp"]',
                    # Action buttons that might contain WhatsApp links
                    'button[data-item-id*="reserve"] a[href*="wa.me"]',
                    'button[data-item-id*="order"] a[href*="wa.me"]',
                    '[data-item-id*="action"] a[href*="wa.me"]',
                    # Broader search in buttons area
                    'button a[href*="wa.me"]',
                    'button a[href*="whatsapp"]',
                    # Look inside any button container
                    '[role="button"] a[href*="wa.me"]',
                    '[role="button"] a[href*="whatsapp"]',
                    # Generic catch-all for any wa.me or WhatsApp links on the page
                    '*[href*="wa.me"]',
                    '*[href*="api.whatsapp.com"]'
                ]
                
                for selector in whatsapp_selectors:
                    try:
                        whatsapp_element = page.locator(selector).first
                        if await whatsapp_element.count() > 0:
                            href = await whatsapp_element.get_attribute("href")
                            if href and ("whatsapp" in href.lower() or "wa.me" in href.lower()):
                                # Extract phone number from WhatsApp URL
                                phone_number = self._extract_phone_from_whatsapp_url(href)
                                if phone_number:
                                    business_data["whatsapp"] = phone_number
                                    print(f"✓ Found WhatsApp: {phone_number} (from {href})")
                                else:
                                    business_data["whatsapp"] = href
                                    print(f"✓ Found WhatsApp URL: {href} (could not extract phone)")
                                break
                    except Exception as selector_error:
                        # Continue to next selector if this one fails
                        continue
                
                if not business_data["whatsapp"]:
                    print("❌ Could not extract WhatsApp")
            except Exception as e:
                print(f"❌ Error extracting WhatsApp: {e}")
            
            # Extract address - more robust selectors with debugging
            try:
                print("Extracting address...")
                address_selectors = [
                    'button[data-item-id*="address"]',
                    '[data-value="address"]',
                    'span[class*="fontBody"]:has-text("Argentina")',
                    'span[class*="fontBody"]:has-text("Buenos Aires")',
                    'div:has-text("Argentina")',
                    'div:has-text("Buenos Aires")',
                    '[data-item-id="oloc"] span',
                    'div[class*="Io6YTe"] span'
                ]
                
                for selector in address_selectors:
                    address_element = page.locator(selector).first
                    if await address_element.count() > 0:
                        address_text = await address_element.inner_text()
                        # More generic address detection - look for common address patterns
                        if (any(char.isdigit() for char in address_text) and 
                            len(address_text.strip()) > 10 and
                            not address_text.lower().startswith('tel') and
                            not address_text.lower().startswith('phone')):
                            business_data["address"] = address_text.strip()
                            print(f"✓ Found address: {address_text}")
                            break
                
                if not business_data["address"]:
                    print("❌ Could not extract address")
            except Exception as e:
                print(f"❌ Error extracting address: {e}")
            
            # Extract rating and reviews - more robust approach with debugging
            try:
                print("Extracting rating and reviews...")
                # Look for rating in various formats
                rating_selectors = [
                    '[role="img"][aria-label*="estrellas"]',
                    '[role="img"][aria-label*="stars"]',
                    'span[class*="rating"]',
                    'div:has-text("★")'
                ]
                
                for selector in rating_selectors:
                    rating_element = page.locator(selector).first
                    if await rating_element.count() > 0:
                        aria_label = await rating_element.get_attribute("aria-label")
                        if aria_label:
                            rating_match = re.search(r'(\d+[.,]\d+)', aria_label)
                            if rating_match:
                                business_data["rating"] = rating_match.group(1).replace(',', '.')
                                print(f"✓ Found rating: {business_data['rating']}")
                            
                            reviews_match = re.search(r'(\d+)\s+opiniones?', aria_label)
                            if reviews_match:
                                business_data["reviews"] = int(reviews_match.group(1))
                                print(f"✓ Found reviews: {business_data['reviews']}")
                            break
                        
                        # Try inner text if aria-label doesn't work
                        inner_text = await rating_element.inner_text()
                        if inner_text:
                            rating_match = re.search(r'(\d+[.,]\d+)', inner_text)
                            if rating_match:
                                business_data["rating"] = rating_match.group(1).replace(',', '.')
                                print(f"✓ Found rating: {business_data['rating']}")
                            break
                
                if not business_data["rating"]:
                    print("❌ Could not extract rating")
            except Exception as e:
                print(f"❌ Error extracting rating: {e}")
            
            print(f"📊 Extraction summary:")
            print(f"   Name: {business_data['name']}")
            print(f"   Phone: {business_data['phone']}")
            print(f"   Website: {business_data['url']}")
            print(f"   Instagram: {business_data['instagram']}")
            print(f"   WhatsApp: {business_data['whatsapp']}")
            print(f"   Address: {business_data['address']}")
            return business_data if business_data["name"] else None
            
        except Exception as e:
            print(f"❌ Error extracting business info: {e}")
            return None
    
    def _is_duplicate_business(self, new_business):
        """
        Check if a business is already in the business_data list.
        Uses multiple criteria to detect duplicates:
        1. Exact name match (case insensitive)
        2. Same phone number
        3. Same website URL
        4. Name similarity + same address pattern
        """
        if not new_business or not new_business.get('name'):
            return False
        
        new_name = new_business['name'].lower().strip()
        new_phone = self._normalize_phone(new_business.get('phone'))
        new_url = self._normalize_url(new_business.get('url'))
        new_address = new_business.get('address', '').lower().strip()
        
        for existing in self.business_data:
            if not existing or not existing.get('name'):
                continue
                
            existing_name = existing['name'].lower().strip()
            existing_phone = self._normalize_phone(existing.get('phone'))
            existing_url = self._normalize_url(existing.get('url'))
            existing_address = existing.get('address', '').lower().strip()
            
            # Check for exact name match
            if new_name == existing_name:
                print(f"  🔍 Duplicate detected: Same name '{new_business['name']}'")
                return True
            
            # Check for same phone number (if both have phones)
            if new_phone and existing_phone and new_phone == existing_phone:
                print(f"  🔍 Duplicate detected: Same phone '{new_business.get('phone')}' for '{new_business['name']}'")
                return True
            
            # Check for same website URL (if both have URLs)
            if new_url and existing_url and new_url == existing_url:
                print(f"  🔍 Duplicate detected: Same website '{new_business.get('url')}' for '{new_business['name']}'")
                return True
            
            # Check for similar names with same address pattern
            if (self._similar_names(new_name, existing_name) and 
                new_address and existing_address and 
                self._similar_addresses(new_address, existing_address)):
                print(f"  🔍 Duplicate detected: Similar name + address for '{new_business['name']}'")
                return True
        
        return False
    
    def _normalize_phone(self, phone):
        """Normalize phone number for comparison"""
        if not phone:
            return None
        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', str(phone))
        # Remove leading + if present
        if normalized.startswith('+'):
            normalized = normalized[1:]
        return normalized if len(normalized) >= 8 else None
    
    def _normalize_url(self, url):
        """Normalize URL for comparison"""
        if not url:
            return None
        # Remove protocol, www, and trailing slashes
        normalized = re.sub(r'^https?://', '', url.lower())
        normalized = re.sub(r'^www\.', '', normalized)
        normalized = normalized.rstrip('/')
        return normalized if len(normalized) > 3 else None
    
    def _similar_names(self, name1, name2):
        """Check if two business names are similar enough to be considered the same"""
        # Remove common business words and punctuation
        clean_words = ['s.a.', 'srl', 'sa', 'ltda', 'inc', 'corp', 'ltd', 'llc', '&', 'and', 'y']
        
        def clean_name(name):
            # Remove punctuation and common business terms
            cleaned = re.sub(r'[^\w\s]', ' ', name.lower())
            words = cleaned.split()
            return ' '.join([w for w in words if w not in clean_words and len(w) > 2])
        
        clean1 = clean_name(name1)
        clean2 = clean_name(name2)
        
        # Check if one name contains the other (after cleaning)
        if len(clean1) > 5 and len(clean2) > 5:
            return clean1 in clean2 or clean2 in clean1
        
        return False
    
    def _similar_addresses(self, addr1, addr2):
        """Check if two addresses are similar (same street or area)"""
        if not addr1 or not addr2:
            return False
        
        # Extract street numbers and names
        def extract_street_info(addr):
            # Look for street number + street name pattern
            match = re.search(r'(\d+)\s+([a-zA-Z\s]+)', addr)
            if match:
                return (match.group(1), match.group(2).strip())
            return None
        
        street1 = extract_street_info(addr1)
        street2 = extract_street_info(addr2)
        
        if street1 and street2:
            # Same street number and similar street name
            if street1[0] == street2[0] and street1[1][:10] == street2[1][:10]:
                return True
        
        # Check if they share significant common words (same neighborhood/area)
        words1 = set(addr1.split())
        words2 = set(addr2.split())
        common_words = words1.intersection(words2)
        
        # If they share at least 2 significant words (not common like "calle", "av", etc.)
        significant_common = [w for w in common_words if len(w) > 4 and w not in ['calle', 'avenida', 'street', 'avenue']]
        return len(significant_common) >= 2

    async def enhance_with_website_contacts(self, business_data, browser):
        """
        Enhance business data with contact information from the business website
        if WhatsApp, Instagram, or email are missing from Google Maps data
        """
        # Check if we need to extract additional contact info
        needs_extraction = (
            business_data.get('url') and  # Has a website URL
            (not business_data.get('email') or 
             not business_data.get('whatsapp') or 
             not business_data.get('instagram'))
        )
        
        if not needs_extraction:
            print("  ℹ️ All contact info available or no website URL, skipping website extraction")
            return business_data
        
        try:
            print(f"  🌐 Extracting missing contact info from website: {business_data['url']}")
            
            # Check if browser is still valid before attempting website extraction
            if not browser or not browser.contexts:
                print("    ⚠️ Browser context not available, skipping website extraction")
                return business_data
            
            # Extract contacts from the business website
            website_contacts = await self.contact_extractor.extract_contacts(
                business_data['url'], 
                browser=browser
            )
            
            if website_contacts and 'contacts' in website_contacts:
                contacts = website_contacts['contacts']
                
                # Enhance missing email with domain prioritization
                if not business_data.get('email') and contacts.get('emails'):
                    prioritized_email = self._prioritize_emails(contacts['emails'], business_data['url'])
                    business_data['email'] = prioritized_email
                    print(f"    ✅ Added email from website: {business_data['email']}")
                
                # Enhance WhatsApp (handle multiple numbers and URL cleanup)
                existing_whatsapp = business_data.get('whatsapp')
                website_whatsapp = contacts.get('whatsapp', [])
                
                # Check if existing WhatsApp is just a URL that needs phone extraction
                if existing_whatsapp and ('api.whatsapp.com' in existing_whatsapp or 'wa.me' in existing_whatsapp):
                    extracted_phone = self._extract_phone_from_whatsapp_url(existing_whatsapp)
                    if extracted_phone:
                        # Combine with website WhatsApp if any
                        all_whatsapp = [extracted_phone]
                        if website_whatsapp:
                            all_whatsapp.extend(website_whatsapp)
                        business_data['whatsapp'] = self._format_whatsapp_numbers(all_whatsapp)
                        print(f"    ✅ Enhanced WhatsApp (URL + website): {business_data['whatsapp']}")
                    elif website_whatsapp:
                        # Couldn't extract from URL, use website data
                        business_data['whatsapp'] = self._format_whatsapp_numbers(website_whatsapp)
                        print(f"    ✅ Replaced WhatsApp URL with website data: {business_data['whatsapp']}")
                elif not existing_whatsapp and website_whatsapp:
                    # No existing WhatsApp, use website data
                    whatsapp_numbers = self._format_whatsapp_numbers(website_whatsapp)
                    business_data['whatsapp'] = whatsapp_numbers
                    print(f"    ✅ Added WhatsApp from website: {business_data['whatsapp']}")
                
                # Enhance missing Instagram
                if not business_data.get('instagram') and contacts.get('instagram'):
                    business_data['instagram'] = contacts['instagram'][0]
                    print(f"    ✅ Added Instagram from website: {business_data['instagram']}")
                
                # Add website extraction metadata
                business_data['website_extraction'] = {
                    'extracted_at': website_contacts.get('extraction_date'),
                    'pages_analyzed': len(website_contacts.get('pages_analyzed', [])),
                    'total_contacts_found': {
                        'emails': len(contacts.get('emails', [])),
                        'whatsapp': len(contacts.get('whatsapp', [])),
                        'instagram': len(contacts.get('instagram', [])),
                        'phones': len(contacts.get('phone_numbers', []))
                    }
                }
                
            else:
                print("    ⚠️ Could not extract contacts from website")
                
        except Exception as e:
            # Website extraction is optional - don't fail the whole scraping for this
            error_msg = str(e)
            if "closed" in error_msg.lower():
                print(f"    ⚠️ Browser context closed, skipping website extraction")
            else:
                print(f"    ❌ Error extracting from website: {e}")
        
        return business_data
    
    def _prioritize_emails(self, emails, website_url):
        """
        Prioritize emails based on domain preference:
        1. Same domain as website
        2. Non-Gmail domains
        3. Gmail and other generic providers
        """
        if not emails:
            return None
        
        # Extract domain from website URL
        try:
            from urllib.parse import urlparse
            website_domain = urlparse(website_url).netloc.lower().replace('www.', '')
        except:
            website_domain = None
        
        # Categorize emails
        same_domain = []
        non_gmail = []
        gmail_others = []
        
        for email in emails:
            email_lower = email.lower().strip()
            email_domain = email_lower.split('@')[-1] if '@' in email_lower else ''
            
            # Skip obviously invalid emails
            if not email_domain or len(email_domain) < 3:
                continue
            
            if website_domain and email_domain == website_domain:
                same_domain.append(email)
            elif email_domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                non_gmail.append(email)
            else:
                gmail_others.append(email)
        
        # Return the best email based on priority
        if same_domain:
            print(f"      📧 Prioritizing same-domain email: {same_domain[0]}")
            return same_domain[0]
        elif non_gmail:
            print(f"      📧 Using non-Gmail email: {non_gmail[0]}")
            return non_gmail[0]
        elif gmail_others:
            print(f"      📧 Using generic email: {gmail_others[0]}")
            return gmail_others[0]
        else:
            return emails[0]  # Fallback to first email
    
    def _format_whatsapp_numbers(self, whatsapp_numbers):
        """
        Format WhatsApp numbers for output.
        If multiple numbers, return comma-separated string.
        Prioritize numbers from direct API links.
        """
        if not whatsapp_numbers:
            return None
        
        # Remove duplicates while preserving order
        unique_numbers = []
        seen = set()
        
        for number in whatsapp_numbers:
            # Clean the number for comparison
            clean_number = re.sub(r'[^\d+]', '', str(number))
            if clean_number not in seen:
                seen.add(clean_number)
                unique_numbers.append(str(number))
        
        # Prioritize numbers that look like they came from direct API links (no formatting)
        api_numbers = []
        formatted_numbers = []
        
        for number in unique_numbers:
            # Numbers from direct API links are typically just digits or +digits
            if re.match(r'^\+?\d+$', number):
                api_numbers.append(number)
            else:
                formatted_numbers.append(number)
        
        # Combine with API numbers first
        final_numbers = api_numbers + formatted_numbers
        
        if len(final_numbers) == 1:
            print(f"      📱 Found WhatsApp: {final_numbers[0]}")
            return final_numbers[0]
        else:
            result = ', '.join(final_numbers)
            print(f"      📱 Found multiple WhatsApp numbers: {result}")
            return result
    
    def _extract_phone_from_whatsapp_url(self, url):
        """
        Extract phone number from WhatsApp URLs like:
        - https://api.whatsapp.com/send?phone=5491123456789
        - https://wa.me/5491123456789
        - https://api.whatsapp.com/send/?phone=5491123456789&text=hello
        - https://wa.me/5491123456789?text=Hola
        - Handles URL-encoded characters like %3D (=)
        """
        if not url:
            return None
        
        # URL decode to handle encoded characters
        try:
            from urllib.parse import unquote
            url = unquote(url)
        except:
            pass  # If decoding fails, continue with original URL
        
        # Patterns to extract phone numbers from WhatsApp URLs
        patterns = [
            # api.whatsapp.com with query params
            r'https?://api\.whatsapp\.com/send[/?]*\??(?:.*[?&])?phone=(\+?[\d]+)',
            # wa.me with phone in path
            r'https?://wa\.me/(\+?[\d]+)',
            # Generic phone parameter (fallback)
            r'[?&]phone=(\+?[\d]+)',
            # Just the phone parameter without query marker (sometimes in buttons)
            r'phone[=:](\+?[\d]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                phone = match.group(1)
                # Clean and format the phone number
                if phone:
                    # Remove any non-digit characters except +
                    phone = re.sub(r'[^\d+]', '', phone)
                    # Ensure + prefix for international numbers (10+ digits)
                    if not phone.startswith('+') and len(phone) >= 10:
                        phone = '+' + phone
                    # Validate phone length (should be reasonable)
                    if 10 <= len(phone.replace('+', '')) <= 15:
                        return phone
        
        return None
    
    def _extract_phone_from_text(self, text):
        """
        Extract phone number from text using comprehensive regex patterns for Argentine numbers.
        Supports various formats like: 011 4123-4567, 0385 421-4413, +54 11 4123-4567, etc.
        """
        if not text:
            return None
        
        # Clean the text first
        text = text.strip()
        
        # Skip obviously non-phone text
        if len(text) > 100 or any(word in text.lower() for word in ['email', 'website', 'sitio', 'web', 'http']):
            return None
        
        # Patterns for Argentine phone numbers
        patterns = [
            # Full international format: +54 9 11 1234-5678
            r'\+54\s*9?\s*(\d{2,4})\s*(\d{4})[-\s]?(\d{4})',
            # National format with area code: 011 4123-4567, 0385 421-4413
            r'(\d{2,4})\s*(\d{3,4})[-\s]?(\d{4})',
            # Just the number part: 4123-4567
            r'(\d{3,4})[-\s]?(\d{4})',
            # Compact format: 1123456789
            r'(\d{10,11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Reconstruct the phone number in a standard format
                groups = match.groups()
                
                if len(groups) == 3:
                    # Format like: area + first + second (011 4123 4567)
                    if len(groups[0]) <= 4:  # Area code
                        phone = f"{groups[0]} {groups[1]}-{groups[2]}"
                    else:
                        phone = f"{groups[0]}-{groups[1]}-{groups[2]}"
                elif len(groups) == 2:
                    # Format like: first + second (4123 4567)
                    phone = f"{groups[0]}-{groups[1]}"
                elif len(groups) == 1:
                    # Single long number, try to format it
                    num = groups[0]
                    if len(num) == 10:  # 1123456789 -> 011 2345-6789
                        phone = f"{num[:3]} {num[3:7]}-{num[7:]}"
                    elif len(num) == 11:  # 01123456789 -> 011 2345-6789
                        phone = f"{num[:3]} {num[3:7]}-{num[7:]}"
                    else:
                        phone = num
                else:
                    phone = match.group(0)
                
                # Validate the extracted phone looks reasonable
                digits_only = re.sub(r'[^\d]', '', phone)
                if 8 <= len(digits_only) <= 15:  # Reasonable phone length
                    return phone.strip()
        
        return None
    
    def _extract_phone_from_tel_link(self, tel_href):
        """
        Extract phone number from tel: links like tel:03854214413
        """
        if not tel_href or not tel_href.startswith('tel:'):
            return None
        
        # Remove 'tel:' prefix and extract digits
        phone_digits = re.sub(r'[^\d]', '', tel_href[4:])
        
        if len(phone_digits) >= 8:
            # Try to format based on length
            if len(phone_digits) == 10:  # 0385421413 -> 0385 421-413
                return f"{phone_digits[:4]} {phone_digits[4:7]}-{phone_digits[7:]}"
            elif len(phone_digits) == 11:  # 03854214413 -> 0385 421-4413  
                return f"{phone_digits[:4]} {phone_digits[4:7]}-{phone_digits[7:]}"
            else:
                # For other lengths, just add basic formatting
                return phone_digits
        
        return None
    
    def save_to_json(self, filename=None, search_query=None):
        """Save scraped data to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Create filename from search query
            query = search_query or self.search_query or "unknown_query"
            safe_query = re.sub(r'[^\w\s-]', '', query).strip()
            safe_query = re.sub(r'[-\s]+', '_', safe_query).lower()
            filename = f"{safe_query}_{timestamp}.json"
        
        # Ensure json_output directory exists
        import os
        json_output_dir = "json_output"
        os.makedirs(json_output_dir, exist_ok=True)
        
        # Create full path for the file
        full_path = os.path.join(json_output_dir, filename)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(self.business_data, f, ensure_ascii=False, indent=2)
        
        print(f"Data saved to {full_path}")
        return full_path

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Scrape business information from Google Maps')
    parser.add_argument('search_query', 
                       help='Search query for Google Maps (e.g., "plomeros Buenos Aires", "restaurants New York")')
    parser.add_argument('--max-results', '-m', 
                       type=int, 
                       default=10, 
                       help='Maximum number of results to scrape (default: 10)')
    parser.add_argument('--output', '-o', 
                       help='Output filename (if not specified, auto-generated from search query)')
    
    return parser.parse_args()

async def main():
    """Main function to run the scraper"""
    args = parse_arguments()
    
    scraper = BusinessScraper(args.search_query)
    
    print(f"Starting Google Maps Business Scraper for: '{args.search_query}'")
    print("=" * 50)
    
    # Scrape business data
    businesses = await scraper.scrape_businesses(max_results=args.max_results)
    
    print("=" * 50)
    print(f"Scraping completed! Found {len(businesses)} unique businesses.")
    if scraper.duplicates_found > 0:
        print(f"🔍 Filtered out {scraper.duplicates_found} duplicate(s).")
    
    # Save to JSON file
    filename = scraper.save_to_json(args.output)
    
    # Database save summary (individual saves already completed)
    print("\n" + "="*50)
    print("💾 DATABASE SAVE SUMMARY")
    print("="*50)
    print(f"✅ Total businesses saved to database: {scraper.db_saved_count}")
    if scraper.db_duplicate_count > 0:
        print(f"🔄 Businesses already in database: {scraper.db_duplicate_count}")
    
    if scraper.db_saved_count + scraper.db_duplicate_count != len(businesses):
        errors = len(businesses) - scraper.db_saved_count - scraper.db_duplicate_count
        print(f"❌ Database save errors: {errors}")
        
    if scraper.db_saved_count == 0 and len(businesses) > 0:
        print("⚠️ No new businesses were saved - all may have been duplicates or errors occurred")
    
    # Print summary
    print(f"\nSummary of scraped data for '{args.search_query}':")
    for i, business in enumerate(businesses, 1):
        print(f"{i}. {business['name']} - {business.get('phone', 'N/A')} - {business.get('url', 'N/A')}")
    
    # Close database connection
    scraper.close_database()

if __name__ == "__main__":
    asyncio.run(main())

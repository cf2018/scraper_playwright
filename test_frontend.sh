#!/bin/bash
# Container Frontend Testing Script

echo "🧪 Testing Business Scraper Container Frontend"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="http://localhost:5001"

echo -e "${BLUE}📊 Testing API Endpoints...${NC}"

# Test 1: Health/Stats endpoint
echo -n "Testing /api/stats... "
STATS_RESPONSE=$(curl -s "$BASE_URL/api/stats")
if echo "$STATS_RESPONSE" | jq -e '.success == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS${NC}"
    TOTAL_BUSINESSES=$(echo "$STATS_RESPONSE" | jq -r '.stats.total_businesses')
    echo "   📈 Total businesses: $TOTAL_BUSINESSES"
else
    echo -e "${RED}❌ FAIL${NC}"
fi

# Test 2: Businesses endpoint
echo -n "Testing /api/businesses... "
BUSINESSES_RESPONSE=$(curl -s "$BASE_URL/api/businesses?limit=1")
if echo "$BUSINESSES_RESPONSE" | jq -e '.success == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS${NC}"
    BUSINESS_COUNT=$(echo "$BUSINESSES_RESPONSE" | jq -r '.count')
    echo "   🏢 Retrieved businesses: $BUSINESS_COUNT"
else
    echo -e "${RED}❌ FAIL${NC}"
fi

# Test 3: Main dashboard page
echo -n "Testing main dashboard page... "
DASHBOARD_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$DASHBOARD_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $DASHBOARD_RESPONSE)${NC}"
fi

# Test 4: Export page
echo -n "Testing export page... "
EXPORT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/export")
if [ "$EXPORT_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $EXPORT_RESPONSE)${NC}"
fi

# Test 5: Export API
echo -n "Testing export API... "
EXPORT_API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/export")
if [ "$EXPORT_API_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $EXPORT_API_RESPONSE)${NC}"
fi

echo ""
echo -e "${BLUE}🔗 Available Frontend URLs:${NC}"
echo "   📊 Main Dashboard: $BASE_URL"
echo "   📤 Export Page: $BASE_URL/export"
echo "   🔧 API Stats: $BASE_URL/api/stats"
echo "   🏢 API Businesses: $BASE_URL/api/businesses"

echo ""
echo -e "${BLUE}🐳 Container Information:${NC}"
CONTAINER_ID=$(docker ps --filter "ancestor=scraper_playwright-dashboard" --format "{{.ID}}")
if [ ! -z "$CONTAINER_ID" ]; then
    echo "   📦 Container ID: $CONTAINER_ID"
    echo "   💾 Memory Usage: $(docker stats $CONTAINER_ID --no-stream --format "{{.MemUsage}}")"
    echo "   🔄 Status: Running"
else
    echo "   ⚠️  Container not found"
fi

echo ""
echo -e "${GREEN}✨ Frontend testing complete!${NC}"
echo "   🌐 Access the dashboard at: $BASE_URL"
#!/bin/bash

# Strategy Monitor Startup Script
# Starts all required services for the TradeStream Strategy Monitor

set -e

echo "🚀 Starting TradeStream Strategy Monitor..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}Waiting for $name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ $name is ready!${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}✗ $name failed to start within ${max_attempts}s${NC}"
    return 1
}

# Step 1: Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl is not installed${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"

# Step 2: Set up port forwards
echo -e "${BLUE}🔌 Setting up port forwards...${NC}"

if ! check_port 5432; then
    echo "Starting PostgreSQL port-forward..."
    kubectl port-forward -n tradestream-dev svc/tradestream-dev-postgresql 5432:5432 &
    PG_PF_PID=$!
    echo "PostgreSQL port-forward PID: $PG_PF_PID"
else
    echo -e "${YELLOW}⚠ Port 5432 already in use (PostgreSQL may already be forwarded)${NC}"
fi

# Wait for PostgreSQL to be accessible
sleep 3

# Step 3: Get database password
echo -e "${BLUE}🔑 Getting database credentials...${NC}"
DB_PASSWORD=$(kubectl get secret -n tradestream-dev tradestream-dev-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d)

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}✗ Failed to get database password${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database credentials obtained${NC}"

# Step 4: Start API server
echo -e "${BLUE}🌐 Starting Strategy Monitor API...${NC}"

if check_port 8080; then
    echo -e "${YELLOW}⚠ Port 8080 already in use, stopping existing service...${NC}"
    pkill -f "python3.*main.py.*8080" || true
    sleep 2
fi

cd services/strategy_monitor_api
/usr/bin/python3 main.py --postgres_password="$DB_PASSWORD" --api_port=8080 --api_host=0.0.0.0 &
API_PID=$!
echo "API server PID: $API_PID"

# Wait for API to be ready
if wait_for_service "http://localhost:8080/api/health" "Strategy Monitor API"; then
    echo -e "${GREEN}✓ API server started successfully${NC}"
else
    echo -e "${RED}✗ API server failed to start${NC}"
    exit 1
fi

# Step 5: Start UI server
echo -e "${BLUE}🎨 Starting UI server...${NC}"

if check_port 3001; then
    echo -e "${YELLOW}⚠ Port 3001 already in use, stopping existing service...${NC}"
    pkill -f "python3.*http.server.*3001" || true
    sleep 2
fi

cd ../ui/strategy-monitor
python3 -m http.server 3001 &
UI_PID=$!
echo "UI server PID: $UI_PID"

# Wait for UI to be ready
if wait_for_service "http://localhost:3001" "UI server"; then
    echo -e "${GREEN}✓ UI server started successfully${NC}"
else
    echo -e "${RED}✗ UI server failed to start${NC}"
    exit 1
fi

# Step 6: Display status and URLs
echo
echo -e "${GREEN}🎉 Strategy Monitor is now running!${NC}"
echo
echo -e "${BLUE}📊 Dashboard URL:${NC} http://localhost:3001"
echo -e "${BLUE}🔧 API URL:${NC}     http://localhost:8080"
echo
echo -e "${BLUE}📈 Quick API Tests:${NC}"
echo "  Health check:     curl http://localhost:8080/api/health"
echo "  Strategy count:   curl http://localhost:8080/api/strategies?limit=5"
echo "  Metrics:          curl http://localhost:8080/api/metrics"
echo
echo -e "${BLUE}🔍 Process IDs:${NC}"
echo "  API Server:       $API_PID"
echo "  UI Server:        $UI_PID"
if [ ! -z "$PG_PF_PID" ]; then
    echo "  PostgreSQL Forward: $PG_PF_PID"
fi
echo
echo -e "${YELLOW}💡 To stop all services, run:${NC}"
echo "  kill $API_PID $UI_PID"
if [ ! -z "$PG_PF_PID" ]; then
    echo "  kill $PG_PF_PID"
fi
echo
echo -e "${GREEN}Happy monitoring! 🚀${NC}"

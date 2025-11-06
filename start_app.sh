#!/bin/bash

# Food Healthiness Application Startup Script
# This script starts both backend (port 2500) and frontend (port 2506)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=2612
FRONTEND_PORT=2512
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Print with color
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Cleanup function
cleanup() {
    print_info "Shutting down services..."

    # Kill backend process
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        print_info "Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi

    # Kill frontend process
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        print_info "Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi

    print_success "Services stopped"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    print_error "Virtual environment not found. Please create it first:"
    print_info "  python3 -m venv venv"
    print_info "  source venv/bin/activate"
    print_info "  pip install -r backend/requirements.txt"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    print_error "Node modules not found. Please install dependencies:"
    print_info "  cd frontend && npm install"
    exit 1
fi

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    print_warning ".env file not found. Creating from example..."
    print_info "Please edit .env with your actual API keys"
fi

print_info "==================================================="
print_info "  Food Healthiness Application"
print_info "==================================================="
print_info "Backend Port:  $BACKEND_PORT"
print_info "Frontend Port: $FRONTEND_PORT"
print_info "==================================================="

# Start Backend
print_info "Starting backend server on port $BACKEND_PORT..."
cd "$PROJECT_ROOT/backend"

# Activate virtual environment and load environment variables
source "$PROJECT_ROOT/venv/bin/activate"
eval $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs -0 -L1 echo export)

# Start backend with auto-reload
python run_uvicorn.py --port $BACKEND_PORT --reload > "$PROJECT_ROOT/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Check if backend started successfully
if kill -0 $BACKEND_PID 2>/dev/null; then
    print_success "Backend started (PID: $BACKEND_PID)"
    print_info "Backend URL: http://localhost:$BACKEND_PORT"
    print_info "Backend logs: backend.log"
else
    print_error "Backend failed to start. Check backend.log for details"
    exit 1
fi

# Start Frontend
print_info "Starting frontend server on port $FRONTEND_PORT..."
cd "$PROJECT_ROOT/frontend"

# Load environment variables for frontend
eval $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs -0 -L1 echo export)

# Set environment variables for frontend
export PORT=$FRONTEND_PORT
export BROWSER=none  # Don't auto-open browser
export REACT_APP_API_URL="http://localhost:$BACKEND_PORT"

# Start frontend
npm start > "$PROJECT_ROOT/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
print_info "Waiting for frontend to start..."
sleep 5

# Check if frontend started successfully
if kill -0 $FRONTEND_PID 2>/dev/null; then
    print_success "Frontend started (PID: $FRONTEND_PID)"
    print_info "Frontend URL: http://localhost:$FRONTEND_PORT"
    print_info "Frontend logs: frontend.log"
else
    print_error "Frontend failed to start. Check frontend.log for details"
    cleanup
    exit 1
fi

# Print access information
echo ""
print_success "==================================================="
print_success "  Application is ready!"
print_success "==================================================="
print_success "Frontend: http://localhost:$FRONTEND_PORT"
print_success "Backend:  http://localhost:$BACKEND_PORT"
print_success "API Docs: http://localhost:$BACKEND_PORT/api-docs"
print_success "==================================================="
echo ""
print_info "Press Ctrl+C to stop both services"
echo ""

# Monitor processes
while true; do
    # Check if backend is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        print_error "Backend process died. Check backend.log"
        cleanup
        exit 1
    fi

    # Check if frontend is still running
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        print_error "Frontend process died. Check frontend.log"
        cleanup
        exit 1
    fi

    sleep 5
done

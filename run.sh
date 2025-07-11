#!/bin/bash

# Start PostgreSQL and Redis services
echo "Starting PostgreSQL and Redis services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 5

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "Error: Services failed to start"
    exit 1
fi

echo "Services are running!"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the FastAPI application
echo "Starting Thrum backend..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
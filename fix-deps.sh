#!/bin/bash

echo "Installing missing PostgreSQL driver..."
source venv/bin/activate
pip install --upgrade pip
pip install "psycopg2-binary==2.9.9"
pip install -r requirements.txt
echo "Dependencies fixed!"
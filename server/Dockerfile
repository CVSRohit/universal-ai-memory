FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY init_db.py .
COPY static/ ./static/

# Create data directory for SQLite
RUN mkdir -p /data

# Environment
ENV DB_PATH=/data/memory.db

# Expose port
EXPOSE 8080

# Run init script and start application
CMD python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8080

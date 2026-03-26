FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security (using uid 999 which matches Fly.io mount)
RUN groupadd -g 999 appuser && useradd -u 999 -g appuser appuser

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY init_db.py .
COPY static/ ./static/
COPY start.sh .
RUN chmod +x start.sh

# Set permissions on app directory
RUN chown -R appuser:appuser /app

# Environment
ENV DB_PATH=/data/memory.db

# Expose port
EXPOSE 8080

# Startup script fixes permissions and drops to appuser
CMD ["/app/start.sh"]

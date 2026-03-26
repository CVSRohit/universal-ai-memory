#!/bin/bash
# Start script that fixes permissions and runs the app

# Fix permissions on the data directory and database (run as root)
if [ -f /data/memory.db ]; then
    chown appuser:appuser /data/memory.db || true
fi
chown -R appuser:appuser /data || true

# Run database initialization and start server as appuser
exec su -s /bin/bash appuser -c "python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8080"

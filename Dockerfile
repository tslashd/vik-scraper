FROM python:3.11-slim

WORKDIR /app

# Disable Python output buffering so logs stream in real-time via docker logs
ENV PYTHONUNBUFFERED=1

# Install system dependencies — timezone + cron in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends tzdata cron && \
    ln -fs /usr/share/zoneinfo/Europe/Sofia /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

# Create log directories
RUN mkdir -p /app/logs/console /app/logs/data /app/logs/gpt

# Install Python dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source (cache busted on every code change — kept as late as possible)
COPY *.py .

# Install cron jobs
COPY crontab /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron && crontab /etc/cron.d/scraper-cron

# Required env vars (set these in Portainer or via docker run -e)
# DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, OPENAI_API_KEY

# Health check — verify a log was written in the last ~2 hours
# --start-period gives the startup scrape time to finish before health is checked
HEALTHCHECK --interval=5m --timeout=10s --start-period=2m \
    CMD find /app/logs/console -name "*.log" -mmin -130 | grep -q . || exit 1

# Export runtime env vars so cron can see them, run an initial scrape, then hand off to cron.
# tail -F forwards cron.log to Docker stdout so output is visible in Portainer Logs.
CMD sh -c "env >> /etc/environment && \
    mkdir -p /app/logs/console /app/logs/data /app/logs/gpt && \
    echo '[Container] Starting initial scrape...' && \
    python3 /app/scraper.py 2>&1 | tee /app/logs/console/startup.log && \
    echo '[Container] Startup scrape done. Cron scheduled — scraper will run hourly.' && \
    touch /app/logs/console/cron.log && \
    tail -F /app/logs/console/cron.log & \
    cron -f"

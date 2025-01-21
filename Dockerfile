# Use the official Python 3.11 image as the base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set timezone to Europe/Sofia
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Sofia /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

# Create the necessary log directories inside the container
RUN mkdir -p /app/logs/console /app/logs/data /app/logs/gpt

# Copy essential files into the container
COPY .env /app/.env
COPY db.py /app/db.py
COPY ai.py /app/ai.py
COPY scraper.py /app/scraper.py
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add a cron job to run the scraper every hour
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*
COPY crontab /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron && crontab /etc/cron.d/scraper-cron

# Create a placeholder log file for cron output
RUN touch /var/log/cron.log

# Command to run cron and stream logs to stdout
CMD sh -c "cron && tail -f /var/log/cron.log /app/logs/console/*.log"

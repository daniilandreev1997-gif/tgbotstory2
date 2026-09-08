FROM python:3.11-slim

WORKDIR /app

# System dependencies for playwright + ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers (for TikTok)
RUN playwright install chromium && playwright install-deps chromium

COPY . .

# Bothost sets BOT_TOKEN automatically
# Data directory must be /app/data for persistence
RUN mkdir -p /app/data /app/data/tmp && chmod 777 /app/data /app/data/tmp

CMD ["python", "-m", "bot.main"]

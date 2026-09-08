FROM python:3.12-slim

# Install Chrome for Selenium (IG/TT clients)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Chrome binary for Selenium
ENV CHROME_BINARY=/usr/bin/google-chrome
# Avoid .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Flush output immediately
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
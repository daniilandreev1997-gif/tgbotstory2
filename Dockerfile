FROM python:3.12-slim

# No browser/Selenium needed — v3.1 uses HTTP-only clients:
#   IG: instagrapi (session file)
#   TT: __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON parsing
#   VK: direct API

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Avoid .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
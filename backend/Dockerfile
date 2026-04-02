FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PyMuPDF and other native libs + Node.js for OpenCode
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode (agent workspace AI coding assistant)
RUN npm install -g opencode-ai@latest

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

ENTRYPOINT ["python", "-m", "src.cli.main"]

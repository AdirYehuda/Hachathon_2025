FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including curl, unzip, and other tools needed for Amazon Q CLI script execution
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    unzip \
    jq \
    git \
    less \
    groff \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI via pip for better compatibility with slim image
RUN pip install awscli

# Install Amazon Q CLI (musl version for better compatibility in containers)
RUN curl --proto '=https' --tlsv1.2 -sSf "https://desktop-release.q.us-east-1.amazonaws.com/latest/q-x86_64-linux-musl.zip" -o "q.zip" \
    && unzip q.zip \
    && ./q/install.sh --no-confirm --force \
    && rm -rf q.zip q/ \
    && chmod +x /root/.local/bin/q

# Add Amazon Q CLI to PATH and ensure AWS CLI is available
ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py .

# Create directories for Amazon Q CLI script execution and set permissions
RUN mkdir -p /tmp/amazon-q-scripts /root/.aws \
    && chmod 755 /tmp/amazon-q-scripts \
    && chmod 755 /root/.aws

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
# USER app  # Temporarily comment out for AWS access

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

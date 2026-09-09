#!/usr/bin/env bash
set -euo pipefail
# One-time server setup + ongoing deployment script for the Oracle VM.
# Run after: ghcr.io image is pushed and .env.production exists.
#
# Prerequisites on the server:
#   1. Docker Engine + docker compose plugin installed
#   2. GitHub PAT with 'read:packages' scope stored at ~/.ghcr-token
#      (create at https://github.com/settings/tokens, classic token with 'read:packages')
#      OR run: echo "YOUR_PAT" > ~/.ghcr-token && chmod 600 ~/.ghcr-token

APP_DIR="/opt/enterprise-rag"
IMAGE="ghcr.io/vizdumb2005/test/enterprise-rag:latest"

echo "=== Enterprise RAG - Server Deployment ==="

# Setup directories
sudo mkdir -p "$APP_DIR"
sudo chown "$(whoami)":"$(whoami)" "$APP_DIR"
cd "$APP_DIR"

# Check for .env.production
if [ ! -f .env.production ]; then
    echo "ERROR: .env.production not found in $APP_DIR"
    echo "Create it with: cat > .env.production <<'EOF'"
    echo "APP_ENV=production"
    echo "DEBUG=false"
    echo "LOG_LEVEL=info"
    echo "QDRANT_URL=https://773125ea-efc2-4c2c-81dd-9b4be54c5a66.europe-west6-0.gcp.cloud.qdrant.io"
    echo "QDRANT_COLLECTION=enterprise_documents"
    echo "QDRANT_API_KEY=<your_qdrant_api_key>"
    echo "LLM_PROVIDER=mock"
    echo "CORS_ORIGINS=https://vizdumb2005.github.io"
    echo "EOF"
    exit 1
fi

# Authenticate to GHCR (if token exists)
if [ -f ~/.ghcr-token ]; then
    echo "Logging in to GHCR..."
    cat ~/.ghcr-token | docker login ghcr.io -u "$(git config --global user.name 2>/dev/null || echo vizdumb2005)" --password-stdin
fi

# Pull latest image
echo "Pulling $IMAGE..."
docker pull "$IMAGE"

# Generate docker-compose if not present
if [ ! -f docker-compose.prod.yml ]; then
    cat > docker-compose.prod.yml <<'COMPOSE'
version: '3.8'
services:
  api:
    image: ghcr.io/vizdumb2005/test/enterprise-rag:latest
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
      - model_cache:/home/appuser/.cache/huggingface
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
volumes:
  model_cache:
COMPOSE
    echo "Created docker-compose.prod.yml"
fi

# Stop existing container
echo "Stopping existing container..."
docker-compose -f docker-compose.prod.yml down --rmi local 2>/dev/null || true

# Start container
echo "Starting container..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for health check
echo "Waiting for API to become healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is healthy!"
        curl -sf http://localhost:8000/health | head -c 500
        echo
        exit 0
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done
echo "ERROR: API failed to start within 60s"
docker-compose -f docker-compose.prod.yml logs --tail 50
exit 1

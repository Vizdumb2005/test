#!/usr/bin/env bash
set -euo pipefail
# Server-side deployment script for the Oracle VM.
# Run this after every GitHub Actions push to deploy the latest image.
#
# Prerequisites:
#   1. Docker Engine + docker compose plugin installed on this server
#   2. Either:
#      a. The GHCR package is publicly readable (workflow sets visibility), OR
#      b. GitHub PAT stored at ~/.ghcr-token (classic token with 'read:packages' scope):
#         echo "ghp_your_pat_here" > ~/.ghcr-token && chmod 600 ~/.ghcr-token
#   3. .env.production in this directory (run the generate step below if missing)

APP_DIR="/opt/enterprise-rag"
IMAGE="ghcr.io/vizdumb2005/test/enterprise-rag:latest"

echo "=== Enterprise RAG - Oracle VM Deployment ==="

sudo mkdir -p "$APP_DIR"
sudo chown "$(whoami)":"$(whoami)" "$APP_DIR"
cd "$APP_DIR"

# Generate .env.production if not present
if [ ! -f .env.production ]; then
    echo "Generating .env.production..."
    cat > .env.production <<'EOF'
APP_ENV=production
DEBUG=false
LOG_LEVEL=info
QDRANT_URL=https://773125ea-efc2-4c2c-81dd-9b4be54c5a66.europe-west6-0.gcp.cloud.qdrant.io
QDRANT_COLLECTION=enterprise_documents
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MTgyYmRkZjYtNjRjZS00YjZlLWJiNTctZjI1YTNmYzI0ZDIzIn0.Nt9ACmUJ4BWIDaWkmmTV5cO2EO_4wT6J6GVMzDlkkNE
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
EMBEDDING_BATCH_SIZE=32
DENSE_TOP_K=30
SPARSE_TOP_K=30
RERANK_TOP_K=8
HYBRID_METHOD=rrf
HYBRID_ALPHA=0.65
RRF_K=60
QUERY_EXPANSION_ENABLED=true
QUERY_EXPANSION_COUNT=3
QUERY_EXPANSION_MODEL=gpt-4o-mini
CHUNK_SIZE=800
CHUNK_OVERLAP=120
CHUNKING_STRATEGY=recursive
CONTEXT_MAX_CHUNKS=8
CONTEXT_MAX_CHARACTERS=30000
LLM_PROVIDER=mock
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1024
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
MAX_UPLOAD_SIZE_MB=50
CORS_ORIGINS=https://vizdumb2005.github.io
RATE_LIMIT_ENABLED=true
RATE_LIMIT_QUERY_PER_MIN=60
RATE_LIMIT_EVAL_PER_MIN=10
RATE_LIMIT_UPLOAD_PER_MIN=30
EOF
    echo ".env.production created"
    echo "Edit QDRANT_API_KEY and LLM_API_KEY as needed"
    exit 1
fi

# Authenticate to GHCR if token exists
if [ -f ~/.ghcr-token ]; then
    echo "Authenticating to GHCR..."
    cat ~/.ghcr-token | docker login ghcr.io -u "${GITHUB_USER:-vizdumb2005}" --password-stdin
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

# Restart with latest image
echo "Restarting container..."
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# Wait for health check
echo "Waiting for API to become healthy..."
for i in $(seq 1 45); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is healthy!"
        curl -sf http://localhost:8000/health | head -c 500
        echo
        exit 0
    fi
    echo "  Waiting... ($i/45)"
    sleep 2
done
echo "ERROR: API failed to start within 90s"
docker-compose -f docker-compose.prod.yml logs --tail 50
exit 1

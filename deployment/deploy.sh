#!/bin/bash
# ─────────────────────────────────────────────────────────────
# DynamicPro ERP — Production Deployment Script
# Run on the server after cloning the repo
# ─────────────────────────────────────────────────────────────
set -e

echo "=== DynamicPro ERP — Production Deploy ==="

# 1. Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not installed"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "ERROR: docker compose not installed"; exit 1; }

# 2. Create .env if missing
if [ ! -f .env ]; then
    echo "Creating .env from .env.production..."
    cp .env.production .env
    echo "⚠️  Edit .env with real passwords and JWT_SECRET_KEY before starting!"
    exit 1
fi

# 3. Create directories
mkdir -p backups logs/nginx deployment/nginx/ssl

# 4. Generate self-signed cert if no real cert
if [ ! -f deployment/nginx/ssl/fullchain.pem ]; then
    echo "Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout deployment/nginx/ssl/privkey.pem \
        -out deployment/nginx/ssl/fullchain.pem \
        -subj "/C=EG/ST=Cairo/L=Cairo/O=DynamicPro/CN=localhost"
    echo "⚠️  Replace with real cert for production!"
fi

# 5. Build and start
echo "Building and starting services..."
docker compose build
docker compose up -d

# 6. Wait for health
echo "Waiting for services to be healthy..."
sleep 10
docker compose ps

# 7. Run migrations
echo "Running database migrations..."
docker compose exec app python -c "from app import create_app; app = create_app(); app.app_context().push(); from database import db; db.create_all(); print('Migrations complete')"

echo ""
echo "=== Deployment Complete ==="
echo "  HTTP:  http://$(hostname -f 2>/dev/null || echo 'your-server')"
echo "  HTTPS: https://$(hostname -f 2>/dev/null || echo 'your-server')"
echo "  Health: https://$(hostname -f 2>/dev/null || echo 'your-server')/health"

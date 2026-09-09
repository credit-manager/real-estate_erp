#!/bin/bash
# ─────────────────────────────────────────────────────────────
# DynamicPro ERP — Production Deployment Script
# Run on the server after cloning the repository.
# Secrets and TLS certificates must be provisioned outside git.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

log() { printf '[DynamicPro] %s\n' "$*"; }
die() { printf '[DynamicPro] ERROR: %s\n' "$*" >&2; exit 1; }

log "=== Production deployment ==="

# 1. Check prerequisites
command -v docker >/dev/null 2>&1 || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "docker compose plugin is not installed"

# 2. Production environment is mandatory; never generate credentials here.
if [ ! -f .env ]; then
    die ".env is required. Provision DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME/SECRET_KEY/REDIS_URL from your secret manager before deployment."
fi

# Refuse accidental weak local-mode deployment.
if grep -qE '^[[:space:]]*(DYNAMICPRO_ENV|DYNAMICPRO_MODE)[[:space:]]*=[[:space:]]*(development|dev|test)[[:space:]]*$' .env; then
    die ".env selects a non-production environment"
fi

# 3. Create runtime directories with restrictive defaults.
umask 077
mkdir -p backups logs/nginx deployment/nginx/ssl

# 4. Require a real trusted certificate in production. Self-signed TLS is not
#    acceptable for public commercial deployments and is never generated here.
if [ ! -s deployment/nginx/ssl/fullchain.pem ] || [ ! -s deployment/nginx/ssl/privkey.pem ]; then
    die "Trusted TLS certificate is required at deployment/nginx/ssl/fullchain.pem and privkey.pem"
fi

# 5. Build images.
log "Building production images..."
docker compose build --pull

# 6. Start only infrastructure first, then wait for database readiness.
log "Starting PostgreSQL and Redis..."
docker compose up -d postgres redis

log "Waiting for infrastructure health..."
for _ in $(seq 1 60); do
    if docker compose ps --status running postgres redis 2>/dev/null | grep -q postgres \
       && docker compose exec -T postgres pg_isready -U "${DB_USER:-dynamicpro}" -d "${DB_NAME:-dynamicpro}" >/dev/null 2>&1 \
       && docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

docker compose exec -T postgres pg_isready -U "${DB_USER:-dynamicpro}" -d "${DB_NAME:-dynamicpro}" >/dev/null 2>&1 \
    || die "PostgreSQL did not become ready"
docker compose exec -T redis redis-cli ping >/dev/null 2>&1 \
    || die "Redis did not become ready"

# 7. Apply the versioned schema before starting application workers.
#    Do not use db.create_all() as a deployment/migration mechanism.
log "Applying Alembic migrations..."
docker compose run --rm app alembic upgrade head

# 8. Start application-facing services.
log "Starting application services..."
docker compose up -d app frontend nginx backup

# 9. Wait for application readiness and fail closed on bad rollout.
log "Waiting for application readiness..."
for _ in $(seq 1 60); do
    if docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/ready', timeout=5).read()" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/ready', timeout=5).read()" >/dev/null 2>&1 \
    || die "Application readiness check failed"

# 10. Show final service state; deployment exits non-zero on failed health.
docker compose ps
if docker compose ps | grep -Eiq '(unhealthy|exit|dead)'; then
    die "One or more services are unhealthy or stopped"
fi

log "=== Deployment complete ==="
log "HTTPS endpoint: https://$(hostname -f 2>/dev/null || echo 'your-server')"
log "Health: https://$(hostname -f 2>/dev/null || echo 'your-server')/health"

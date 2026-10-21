#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# deploy.sh  — one-click deployment helper
# Usage:
#   ./deploy.sh render       → deploy to Render.com (requires render CLI)
#   ./deploy.sh railway      → deploy to Railway.app
#   ./deploy.sh docker-local → build & run locally via Docker
#   ./deploy.sh docker-hub   → push Docker image to Docker Hub
# ─────────────────────────────────────────────────────────
set -e
IMAGE_NAME="cpcb-aqi-dashboard"
DOCKER_USER="${DOCKER_USER:-your-dockerhub-username}"

case "$1" in
  render)
    echo "Deploying to Render..."
    git add -A && git commit -m "Deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
    git push origin main
    echo "Render auto-deploys on push. Check https://dashboard.render.com"
    ;;

  railway)
    echo "Deploying to Railway..."
    command -v railway >/dev/null || (npm i -g @railway/cli && echo "Installed railway CLI")
    railway login
    railway up
    ;;

  docker-local)
    echo "Building Docker image..."
    docker build -t ${IMAGE_NAME}:latest .
    echo "Starting container on http://localhost:8000 ..."
    docker compose up -d
    echo "Dashboard: http://localhost:8000"
    ;;

  docker-hub)
    echo "Building & pushing to Docker Hub as ${DOCKER_USER}/${IMAGE_NAME}..."
    docker build -t ${DOCKER_USER}/${IMAGE_NAME}:latest .
    docker push ${DOCKER_USER}/${IMAGE_NAME}:latest
    echo "Image pushed: ${DOCKER_USER}/${IMAGE_NAME}:latest"
    ;;

  *)
    echo "Usage: $0 {render|railway|docker-local|docker-hub}"
    exit 1
    ;;
esac

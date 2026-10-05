#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="deployhub"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/kind-config.yaml"

echo "☸️  DeployHub Kubernetes Cluster Setup"
echo "======================================"

if ! command -v kind &>/dev/null; then
    echo "❌ Error: 'kind' is not installed or not in PATH."
    exit 1
fi

if ! command -v kubectl &>/dev/null; then
    echo "❌ Error: 'kubectl' is not installed or not in PATH."
    exit 1
fi

# 1. Create Kind Cluster if not exists
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "✅ Cluster '${CLUSTER_NAME}' already exists."
else
    echo "🚀 Creating Kind cluster '${CLUSTER_NAME}'..."
    kind create cluster --name "${CLUSTER_NAME}" --config "${CONFIG_FILE}"
fi

# 2. Switch context
kubectl config use-context "kind-${CLUSTER_NAME}"

# 3. Install NGINX Ingress Controller for Kind
echo "🌐 Installing NGINX Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "⏳ Waiting for Ingress Controller to be ready (timeout 90s)..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s || echo "⚠️ Ingress pod still initializing in background."

echo ""
echo "🎉 Cluster '${CLUSTER_NAME}' is ready!"
echo "   Applications deployed via Ingress will be accessible at http://<app>.localtest.me"

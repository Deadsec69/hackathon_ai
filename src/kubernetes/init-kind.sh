#!/bin/bash
set -e

echo "Starting Kind initialization script..."

# Wait for Kind to be fully initialized
echo "Waiting for Kind API server to be ready..."
until kubectl cluster-info 2>/dev/null; do
  echo "Waiting for Kubernetes API server to become available..."
  sleep 5
done

echo "Kind cluster is ready!"

# Create kubeconfig directory
echo "Creating kubeconfig directory..."
mkdir -p /kubeconfig

# Export kubeconfig to shared volume
echo "Exporting kubeconfig to shared volume..."
kubectl config view --raw > /kubeconfig/config
chmod 644 /kubeconfig/config

echo "Kubeconfig exported to /kubeconfig/config"
ls -la /kubeconfig/

# Keep the container running
echo "Kind initialization complete. Container will continue running."
tail -f /dev/null

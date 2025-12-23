#!/bin/bash
# K3s Worker Node Bootstrap Script
# This script retrieves the join token from SSM and joins the K3s cluster

set -e

# Log output for debugging
exec > >(tee /var/log/k3s-worker-setup.log) 2>&1
echo "Starting K3s worker setup at $(date)"

# Update system packages
apt-get update -y
apt-get install -y curl unzip jq

# Install AWS CLI v2
echo "Installing AWS CLI..."
curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

# Get instance metadata
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
PRIVATE_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

echo "Instance ID: $INSTANCE_ID"
echo "Private IP: $PRIVATE_IP"
echo "Region: $REGION"

# Wait for master to be ready and SSM parameters to be available
echo "Waiting for master node to be ready..."
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    MASTER_IP=$(aws ssm get-parameter \
        --region "$REGION" \
        --name "/k3s/master-ip" \
        --query "Parameter.Value" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$MASTER_IP" ] && [ "$MASTER_IP" != "None" ]; then
        echo "Master IP found: $MASTER_IP"
        break
    fi
    
    echo "Master not ready yet, retrying in 10 seconds... ($RETRY_COUNT/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 10
done

if [ -z "$MASTER_IP" ] || [ "$MASTER_IP" == "None" ]; then
    echo "ERROR: Failed to get master IP after $MAX_RETRIES retries"
    exit 1
fi

# Retrieve join token from SSM Parameter Store
echo "Retrieving join token from SSM Parameter Store..."
TOKEN=$(aws ssm get-parameter \
    --region "$REGION" \
    --name "/k3s/join-token" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text)

if [ -z "$TOKEN" ] || [ "$TOKEN" == "None" ]; then
    echo "ERROR: Failed to retrieve join token"
    exit 1
fi

echo "Join token retrieved successfully"

# Install K3s agent and join cluster
echo "Installing K3s agent and joining cluster..."
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN="${TOKEN}" sh -s - agent \
    --node-name "k3s-worker-${INSTANCE_ID}"

# Verify agent is running
echo "Verifying K3s agent is running..."
sleep 10

if systemctl is-active --quiet k3s-agent; then
    echo "K3s agent is running successfully"
else
    echo "WARNING: K3s agent may not be running properly"
    systemctl status k3s-agent || true
fi

echo "K3s worker setup completed successfully at $(date)"
echo "Worker node has joined the cluster."

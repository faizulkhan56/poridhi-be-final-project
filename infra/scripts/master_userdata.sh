#!/bin/bash
# K3s Master Node Bootstrap Script
# This script installs K3s server and stores the join token in SSM Parameter Store

set -e

# Log output for debugging
exec > >(tee /var/log/k3s-master-setup.log) 2>&1
echo "Starting K3s master setup at $(date)"

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
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "")
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

echo "Instance ID: $INSTANCE_ID"
echo "Private IP: $PRIVATE_IP"
echo "Public IP: $PUBLIC_IP"
echo "Region: $REGION"

# Install K3s server
echo "Installing K3s server..."
curl -sfL https://get.k3s.io | sh -s - server \
    --tls-san "$PUBLIC_IP" \
    --tls-san "$PRIVATE_IP" \
    --node-name "k3s-master" \
    --write-kubeconfig-mode 644

# Wait for K3s to be ready
echo "Waiting for K3s to be ready..."
sleep 30

# Verify K3s is running
until kubectl get nodes; do
    echo "Waiting for K3s API server..."
    sleep 5
done

# Get the K3s join token
TOKEN=$(cat /var/lib/rancher/k3s/server/node-token)
echo "K3s token retrieved successfully"

# Store join token in SSM Parameter Store
echo "Storing join token in SSM Parameter Store..."
aws ssm put-parameter \
    --region "$REGION" \
    --name "/k3s/join-token" \
    --value "$TOKEN" \
    --type SecureString \
    --overwrite

# Store master IP in SSM Parameter Store (use private IP for internal communication)
echo "Storing master IP in SSM Parameter Store..."
aws ssm put-parameter \
    --region "$REGION" \
    --name "/k3s/master-ip" \
    --value "$PRIVATE_IP" \
    --type String \
    --overwrite

# Store master public IP (for external access)
if [ -n "$PUBLIC_IP" ]; then
    aws ssm put-parameter \
        --region "$REGION" \
        --name "/k3s/master-public-ip" \
        --value "$PUBLIC_IP" \
        --type String \
        --overwrite
fi

echo "K3s master setup completed successfully at $(date)"
echo "Master node is ready. Workers can now join the cluster."

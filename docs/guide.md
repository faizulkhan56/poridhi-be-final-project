# K3s Cluster Deployment Guide

This guide provides step-by-step instructions to deploy a K3s Kubernetes cluster on AWS using Pulumi with Python.

## Table of Contents

### Phase 1: K3s Cluster
1. [Prerequisites](#prerequisites)
2. [AWS Configuration](#aws-configuration)
3. [Project Setup](#project-setup)
4. [Configuration](#configuration)
5. [Deployment](#deployment)
6. [Verification](#verification)
7. [Accessing the Cluster](#accessing-the-cluster)
8. [Cleanup](#cleanup)
9. [Troubleshooting](#troubleshooting)

### Phase 2: Autoscaler
10. [Prometheus and Autoscaler Setup](#phase-2-prometheus-and-autoscaler-setup)
11. [Testing the Autoscaler Manually](#testing-the-autoscaler-manually)
12. [Monitoring and Logs](#monitoring-and-logs)
13. [Complete Cleanup](#complete-cleanup-all-resources)

---

## Prerequisites

Before you begin, ensure you have the following installed:

### 1. Python 3.8+

**Ubuntu/Linux:**
```bash
# Check if Python is installed
python3 --version

# Install if not present
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

**Windows:**
```powershell
# Check Python version
python --version

# Install via winget if not present
winget install Python.Python.3.11
```

### 2. Pulumi CLI

**Ubuntu/Linux:**
```bash
# Install Pulumi
curl -fsSL https://get.pulumi.com | sh

# Add to PATH (add this to ~/.bashrc for persistence)
export PATH=$PATH:$HOME/.pulumi/bin

# Verify installation
pulumi version
```

**Windows (PowerShell):**
```powershell
# Using winget
winget install Pulumi.Pulumi

# Or using Chocolatey
choco install pulumi

# Verify installation
pulumi version
```

### 3. AWS CLI

**Ubuntu/Linux:**
```bash
# Download and install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt install -y unzip
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# Verify installation
aws --version
```

**Windows (PowerShell):**
```powershell
# Install via winget
winget install Amazon.AWSCLI

# Verify installation
aws --version
```

---

## AWS Configuration

### 1. Configure AWS Credentials

You need AWS credentials with permissions for EC2, VPC, IAM, and SSM.

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `ap-southeast-1`)
- Default output format (`json`)

### 2. Create SSH Key Pair

Create an SSH key pair for accessing EC2 instances:

**Ubuntu/Linux:**
```bash
# Create .ssh directory if it doesn't exist
mkdir -p ~/.ssh

# Create key pair
aws ec2 create-key-pair \
    --key-name k3s-key \
    --query 'KeyMaterial' \
    --output text > ~/.ssh/k3s-key.pem

# Set proper permissions (REQUIRED on Linux)
chmod 400 ~/.ssh/k3s-key.pem
```

**Windows PowerShell:**
```powershell
# Create .ssh directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh"

# Create key pair
aws ec2 create-key-pair `
    --key-name k3s-key `
    --query 'KeyMaterial' `
    --output text | Out-File -Encoding ascii "$env:USERPROFILE\.ssh\k3s-key.pem"
```

> [!IMPORTANT]
> Save the key file securely. You'll need it to SSH into your nodes.

### 3. Required IAM Permissions

Your AWS user/role needs the following permissions:
- `ec2:*` (for VPC, subnets, security groups, instances)
- `iam:*` (for creating roles and instance profiles)
- `ssm:*` (for Parameter Store access)

---

## Project Setup

### 1. Navigate to Infrastructure Directory

```bash
cd infra
```

### 2. Create Pulumi Account (if needed)

If you haven't already, create a free Pulumi account:
```bash
pulumi login
```

Or use local state storage:
```bash
pulumi login --local
```

### 3. Create Python Virtual Environment

**Ubuntu/Linux:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

**Windows PowerShell:**
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate.bat
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize Pulumi Stack

```bash
# Initialize the 'dev' stack
pulumi stack init dev

# Or select existing stack
pulumi stack select dev
```

---

## Configuration

### 1. Review Default Configuration

The default configuration is in `Pulumi.dev.yaml`:

```yaml
config:
  aws:region: ap-southeast-1
  k3s-cluster:vpc_cidr: "10.0.0.0/16"
  k3s-cluster:master_instance_type: t3.medium
  k3s-cluster:worker_instance_type: t3.small
  k3s-cluster:worker_count: "2"
  k3s-cluster:ssh_key_name: k3s-key
```

### 2. Modify Configuration (Optional)

Change region:
```bash
pulumi config set aws:region us-east-1
```

Change worker count:
```bash
pulumi config set k3s-cluster:worker_count 3
```

Change instance types:
```bash
pulumi config set k3s-cluster:master_instance_type t3.large
pulumi config set k3s-cluster:worker_instance_type t3.medium
```

Change SSH key name:
```bash
pulumi config set k3s-cluster:ssh_key_name your-key-name
```

---

## Deployment

### 1. Preview Changes

Before deploying, preview what will be created:

```bash
pulumi preview
```

This shows all resources that will be created without making any changes.

### 2. Deploy Infrastructure

Deploy the K3s cluster:

```bash
pulumi up
```

You'll see a preview of changes. Type `yes` to confirm.

**Expected resources created:**
- 1 VPC
- 2 Public Subnets (in 2 AZs)
- 1 Internet Gateway
- 1 Route Table
- 2 Security Groups (master + worker)
- 2 IAM Roles + Instance Profiles
- 1 Master EC2 Instance (t3.medium)
- 2 Worker EC2 Instances (t3.small)

> [!NOTE]
> Deployment takes approximately 5-10 minutes. The master node needs to initialize K3s and store the join token before workers can join.

### 3. View Outputs

After deployment, view the outputs:

```bash
pulumi stack output
```

Example output:
```
Current stack outputs (12):
    OUTPUT                  VALUE
    k3s_api_endpoint        https://54.123.45.67:6443
    master_instance_id      i-0abc123def456789
    master_private_ip       10.0.1.100
    master_public_ip        54.123.45.67
    ssh_master_command      ssh -i ~/.ssh/k3s-key.pem ubuntu@54.123.45.67
    vpc_id                  vpc-0abc123def
    worker_count            2
    worker_public_ips       ["54.123.45.68", "54.123.45.69"]
```

---

## Verification

### 1. Wait for Initialization

After deployment, wait 3-5 minutes for:
- Master node to install K3s and store join token
- Worker nodes to retrieve token and join cluster

### 2. SSH to Master Node

**Ubuntu/Linux:**
```bash
# Get the SSH command from outputs
pulumi stack output ssh_master_command

# SSH to master (example)
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>
```

**Windows PowerShell:**
```powershell
# Get the SSH command from outputs
pulumi stack output ssh_master_command

# SSH to master
ssh -i $env:USERPROFILE\.ssh\k3s-key.pem ubuntu@<master_public_ip>
```

### 3. Check Cluster Status

On the master node:

```bash
# Check K3s service status
sudo systemctl status k3s

# Check nodes (should show master + workers)
sudo kubectl get nodes

# Expected output (after workers join):
# NAME                      STATUS   ROLES                  AGE   VERSION
# k3s-master                Ready    control-plane,master   5m    v1.28.x+k3s1
# k3s-worker-i-0abc123...   Ready    <none>                 3m    v1.28.x+k3s1
# k3s-worker-i-0def456...   Ready    <none>                 3m    v1.28.x+k3s1
```

### 4. Check K3s Installation Logs

If workers haven't joined, check the logs:

**On Master:**
```bash
sudo cat /var/log/k3s-master-setup.log
```

**On Worker (SSH to worker first):**
```bash
sudo cat /var/log/k3s-worker-setup.log
```

### 5. Verify SSM Parameters

Check that tokens are stored correctly:

```bash
# From your local machine (not EC2)
aws ssm get-parameter --name "/k3s/master-ip" --query "Parameter.Value" --output text
aws ssm get-parameter --name "/k3s/join-token" --with-decryption --query "Parameter.Value" --output text
```

### 6. Test with a Sample Deployment

On the master node:

```bash
# Create a test deployment
sudo kubectl create deployment nginx --image=nginx --replicas=3

# Check pods are distributed across workers
sudo kubectl get pods -o wide

# Expose the deployment
sudo kubectl expose deployment nginx --port=80 --type=NodePort

# Get the NodePort
sudo kubectl get svc nginx

# Test access (use any worker's public IP with the NodePort)
curl http://<worker_public_ip>:<nodeport>
```

---

## Accessing the Cluster

### Option 1: SSH to Master

SSH to master and use `kubectl` directly:

**Ubuntu/Linux:**
```bash
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>
sudo kubectl get nodes
```

**Windows PowerShell:**
```powershell
ssh -i $env:USERPROFILE\.ssh\k3s-key.pem ubuntu@<master_public_ip>
sudo kubectl get nodes
```

### Option 2: Copy Kubeconfig Locally

Copy the kubeconfig to your local machine:

**Ubuntu/Linux:**
```bash
# Create .kube directory if it doesn't exist
mkdir -p ~/.kube

# Copy kubeconfig from master
scp -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>:/etc/rancher/k3s/k3s.yaml ~/.kube/k3s-config

# Update the server address in the config
# Replace 127.0.0.1 with master's public IP
sed -i 's/127.0.0.1/<master_public_ip>/g' ~/.kube/k3s-config

# Use the config
export KUBECONFIG=~/.kube/k3s-config
kubectl get nodes
```

**Windows PowerShell:**
```powershell
# Create .kube directory
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.kube"

# Copy kubeconfig
scp -i $env:USERPROFILE\.ssh\k3s-key.pem ubuntu@<master_public_ip>:/etc/rancher/k3s/k3s.yaml $env:USERPROFILE\.kube\k3s-config

# Update server address manually in the file
# Open $env:USERPROFILE\.kube\k3s-config and replace 127.0.0.1 with master's public IP
# Or use PowerShell:
(Get-Content "$env:USERPROFILE\.kube\k3s-config") -replace '127.0.0.1', '<master_public_ip>' | Set-Content "$env:USERPROFILE\.kube\k3s-config"

# Set environment variable
$env:KUBECONFIG = "$env:USERPROFILE\.kube\k3s-config"
kubectl get nodes
```
kubectl get nodes
```

---

## Cleanup

### 1. Destroy Infrastructure

When you're done, destroy all resources:

```bash
cd infra
pulumi destroy
```

Type `yes` to confirm.

### 2. Clean Up SSM Parameters

The SSM parameters are not managed by Pulumi, so clean them up manually:

```bash
aws ssm delete-parameter --name "/k3s/join-token"
aws ssm delete-parameter --name "/k3s/master-ip"
aws ssm delete-parameter --name "/k3s/master-public-ip"
```

### 3. Delete SSH Key (Optional)

```bash
aws ec2 delete-key-pair --key-name k3s-key
rm ~/.ssh/k3s-key.pem
```

### 4. Remove Pulumi Stack (Optional)

```bash
pulumi stack rm dev
```

---

## Troubleshooting

### Workers Not Joining

1. **Check worker logs:**
   ```bash
   ssh -i ~/.ssh/k3s-key.pem ubuntu@<worker_ip>
   sudo cat /var/log/k3s-worker-setup.log
   ```

2. **Check SSM parameters exist:**
   ```bash
   aws ssm get-parameter --name "/k3s/master-ip"
   aws ssm get-parameter --name "/k3s/join-token" --with-decryption
   ```

3. **Verify security groups allow traffic on port 6443**

4. **Restart K3s agent on worker:**
   ```bash
   sudo systemctl restart k3s-agent
   ```

### Master K3s Not Starting

1. **Check master logs:**
   ```bash
   sudo journalctl -u k3s -f
   sudo cat /var/log/k3s-master-setup.log
   ```

2. **Check K3s status:**
   ```bash
   sudo systemctl status k3s
   ```

### SSH Connection Issues

1. **Verify security group allows SSH (port 22)**
2. **Check your IP hasn't changed (if you restricted SSH access)**
3. **Verify key permissions:** `chmod 400 ~/.ssh/k3s-key.pem`

### IAM Permission Errors

Ensure your AWS credentials have permissions for:
- EC2 (create instances, VPCs, security groups)
- IAM (create roles, instance profiles)
- SSM (put/get parameters)

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   VPC (10.0.0.0/16)                   │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐     │  │
│  │  │   Public Subnet 1   │  │   Public Subnet 2   │     │  │
│  │  │   (10.0.1.0/24)     │  │   (10.0.2.0/24)     │     │  │
│  │  │   AZ-1              │  │   AZ-2              │     │  │
│  │  │                     │  │                     │     │  │
│  │  │  ┌───────────────┐  │  │  ┌───────────────┐  │     │  │
│  │  │  │  K3s Master   │  │  │  │  K3s Worker   │  │     │  │
│  │  │  │  t3.medium    │  │  │  │  t3.small     │  │     │  │
│  │  │  └───────────────┘  │  │  └───────────────┘  │     │  │
│  │  │  ┌───────────────┐  │  │                     │     │  │
│  │  │  │  K3s Worker   │  │  │                     │     │  │
│  │  │  │  t3.small     │  │  │                     │     │  │
│  │  │  └───────────────┘  │  │                     │     │  │
│  │  └─────────────────────┘  └─────────────────────┘     │  │
│  │                     │                                  │  │
│  │              ┌──────┴──────┐                          │  │
│  │              │   Internet   │                          │  │
│  │              │   Gateway    │                          │  │
│  │              └──────────────┘                          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────┐                                    │
│  │  SSM Parameter      │  Stores: /k3s/join-token           │
│  │  Store              │          /k3s/master-ip            │
│  └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

After the cluster is running, you can:

1. **Deploy Prometheus** for metrics collection
2. **Set up the Lambda autoscaler** (Phase 2 of the system design)
3. **Configure monitoring and alerting**
4. **Deploy your microservices**

Refer to the `SystemDesign.md` for the complete system architecture and remaining challenges.

---

## Phase 2: Prometheus and Autoscaler Setup

This section covers deploying Prometheus for metrics collection and enabling the Lambda autoscaler.

### Step 1: Deploy Prometheus on K3s

SSH to the master node and apply the Kubernetes manifests:

**Ubuntu/Linux:**
```bash
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>
```

**Windows PowerShell:**
```powershell
ssh -i $env:USERPROFILE\.ssh\k3s-key.pem ubuntu@<master_public_ip>
```

Then apply the manifests:

```bash
# Create directory for manifests
mkdir -p ~/k8s-manifests

# Copy manifests from your local machine or create them
# Option 1: Copy from local (run on local machine)
# scp -i ~/.ssh/k3s-key.pem infra/k8s/*.yaml ubuntu@<master_ip>:~/k8s-manifests/

# Option 2: Create files directly on master (already done in this case)
# The manifests are in the infra/k8s/ directory

# Apply Prometheus configuration
sudo kubectl apply -f ~/k8s-manifests/prometheus-config.yaml
sudo kubectl apply -f ~/k8s-manifests/prometheus-deployment.yaml
sudo kubectl apply -f ~/k8s-manifests/prometheus-service.yaml

# Apply kube-state-metrics for pending pod metrics
sudo kubectl apply -f ~/k8s-manifests/kube-state-metrics.yaml
```

### Step 2: Verify Prometheus Deployment

```bash
# Check Prometheus pod is running
sudo kubectl get pods -l app=prometheus

# Check kube-state-metrics is running
sudo kubectl get pods -l app=kube-state-metrics

# Check services
sudo kubectl get svc prometheus
```

Expected output:
```
NAME         TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
prometheus   NodePort   10.43.x.x      <none>        9090:30090/TCP   1m
```

### Step 3: Test Prometheus Access

From your local machine, test Prometheus is accessible:

**Ubuntu/Linux:**
```bash
# Get Prometheus URL from Pulumi outputs
pulumi stack output prometheus_url

# Test Prometheus health
curl http://<master_public_ip>:30090/-/healthy

# Query a metric
curl "http://<master_public_ip>:30090/api/v1/query?query=up"
```

**Windows PowerShell:**
```powershell
# Get Prometheus URL
pulumi stack output prometheus_url

# Test Prometheus (use browser or Invoke-RestMethod)
Invoke-RestMethod -Uri "http://<master_public_ip>:30090/-/healthy"
```

### Step 4: Verify Lambda Autoscaler

Check the Lambda function and EventBridge rule:

```bash
# Get Lambda function name
pulumi stack output lambda_function

# Get EventBridge rule name
pulumi stack output eventbridge_rule

# Check Lambda exists
aws lambda get-function --function-name k3s-autoscaler

# Check EventBridge rule
aws events describe-rule --name k3s-autoscaler-schedule
```

### Step 5: Verify DynamoDB Table

```bash
# Get table name
pulumi stack output dynamodb_table

# Check table exists
aws dynamodb describe-table --table-name k3s-cluster-state

# View current state
aws dynamodb get-item \
    --table-name k3s-cluster-state \
    --key '{"cluster_id": {"S": "k3s-main"}}'
```

---

## Testing the Autoscaler Manually

### Test 1: Trigger Lambda Manually

Invoke the Lambda function manually to test:

```bash
# Invoke Lambda
aws lambda invoke \
    --function-name k3s-autoscaler \
    --payload '{}' \
    /dev/stdout

# Check CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/k3s-autoscaler
aws logs tail /aws/lambda/k3s-autoscaler --follow
```

### Test 2: Simulate High CPU Load (Scale UP)

SSH to a worker node and generate CPU load:

```bash
# SSH to worker
ssh -i ~/.ssh/k3s-key.pem ubuntu@<worker_public_ip>

# Install stress tool
sudo apt-get update && sudo apt-get install -y stress

# Generate CPU load (run for 5 minutes)
stress --cpu 4 --timeout 300

# The autoscaler should detect high CPU and add a new worker
```

Monitor the autoscaler response:

```bash
# Watch Lambda logs
aws logs tail /aws/lambda/k3s-autoscaler --follow

# Check DynamoDB state
aws dynamodb get-item \
    --table-name k3s-cluster-state \
    --key '{"cluster_id": {"S": "k3s-main"}}'

# Check EC2 instances
aws ec2 describe-instances \
    --filters "Name=tag:Project,Values=k3s-cluster" \
              "Name=instance-state-name,Values=running,pending" \
    --query "Reservations[*].Instances[*].[InstanceId,Tags[?Key=='Name'].Value|[0]]" \
    --output table
```

### Test 3: Verify Scale DOWN (Low CPU)

After the load test, wait for the cooldown period (5 minutes) and observe:

1. CPU should drop below 30%
2. Lambda should detect low usage
3. Oldest autoscaled worker should be terminated

```bash
# Check nodes in K3s
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>
sudo kubectl get nodes

# Watch for node removal
watch -n 5 'sudo kubectl get nodes'
```

### Test 4: Verify Pending Pods Trigger

Create pending pods to trigger scale-up:

```bash
# SSH to master
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>

# Create pods that request more resources than available
sudo kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
name: resource-hog
namespace: default
spec:
  replicas: 10
  selector:
    matchLabels:
      app: resource-hog
  template:
    metadata:
      labels:
        app: resource-hog
    spec:
      containers:
      - name: hog
        image: nginx
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
EOF

# Check for pending pods
sudo kubectl get pods -l app=resource-hog

# Lambda should detect pending pods and scale up
```

Clean up after testing:

```bash
sudo kubectl delete deployment resource-hog
```

---

## Monitoring and Logs

### CloudWatch Logs

View Lambda execution logs:

```bash
# Get log stream names
aws logs describe-log-streams \
    --log-group-name /aws/lambda/k3s-autoscaler \
    --order-by LastEventTime \
    --descending

# View recent logs
aws logs tail /aws/lambda/k3s-autoscaler --since 1h
```

### Prometheus Queries (PromQL)

Access Prometheus UI at `http://<master_ip>:30090` and try these queries:

| Query | Description |
|-------|-------------|
| `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` | Average CPU usage % |
| `kube_pod_status_phase{phase="Pending"}` | Pending pods |
| `count(kube_node_status_condition{condition="Ready",status="true"})` | Ready node count |
| `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100` | Memory available % |

---

## Phase 2 Cleanup

To clean up Phase 2 resources after testing:

```bash
# Delete Prometheus from K3s
ssh -i ~/.ssh/k3s-key.pem ubuntu@<master_public_ip>
sudo kubectl delete -f ~/k8s-manifests/

# The Lambda, DynamoDB, and EventBridge will be cleaned up with pulumi destroy
```

---

## Complete Cleanup (All Resources)

```bash
cd infra
pulumi destroy

# Clean up SSM parameters
aws ssm delete-parameter --name "/k3s/join-token"
aws ssm delete-parameter --name "/k3s/master-ip"
aws ssm delete-parameter --name "/k3s/master-public-ip"
```

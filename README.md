# K3s Autoscaler on AWS

A custom K3s Kubernetes cluster autoscaler on AWS, using Pulumi for infrastructure as code.

## Overview

This project implements an automated K3s cluster on AWS with:
- **K3s Master Node** (t3.medium) - Control plane
- **K3s Worker Nodes** (t3.small) - Auto-scaling worker nodes
- **Auto-join Mechanism** - Workers automatically join the cluster via SSM Parameter Store
- **Multi-AZ Deployment** - High availability across 2 availability zones

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   VPC (10.0.0.0/16)                   │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐     │  │
│  │  │   Public Subnet 1   │  │   Public Subnet 2   │     │  │
│  │  │   (AZ-1)            │  │   (AZ-2)            │     │  │
│  │  │  ┌───────────────┐  │  │  ┌───────────────┐  │     │  │
│  │  │  │  K3s Master   │  │  │  │  K3s Worker   │  │     │  │
│  │  │  └───────────────┘  │  │  └───────────────┘  │     │  │
│  │  │  ┌───────────────┐  │  │                     │     │  │
│  │  │  │  K3s Worker   │  │  │                     │     │  │
│  │  │  └───────────────┘  │  │                     │     │  │
│  │  └─────────────────────┘  └─────────────────────┘     │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌─────────────────────┐                                    │
│  │  SSM Parameter Store │ (Join Token Storage)              │
│  └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.8+
- Pulumi CLI
- AWS CLI configured with admin credentials
- SSH key pair created in AWS

## Quick Start

```bash
# Navigate to infrastructure directory
cd infra

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Initialize Pulumi stack
pulumi stack init dev

# Deploy
pulumi up
```

## Project Structure

```
├── README.md                 # This file
├── SystemDesign.md           # Complete system design document
├── docs/
│   └── guide.md              # Step-by-step deployment guide
└── infra/
    ├── Pulumi.yaml           # Pulumi project config
    ├── Pulumi.dev.yaml       # Dev stack configuration
    ├── requirements.txt      # Python dependencies
    ├── __main__.py           # Main entry point
    ├── config.py             # Configuration loader
    ├── vpc.py                # VPC & networking
    ├── security_groups.py    # Security groups
    ├── master.py             # K3s master node
    ├── workers.py            # K3s worker nodes
    └── scripts/
        ├── master_userdata.sh  # Master bootstrap script
        └── worker_userdata.sh  # Worker bootstrap script
```

## Configuration

Edit `infra/Pulumi.dev.yaml` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `aws:region` | ap-southeast-1 | AWS region |
| `k3s-cluster:master_instance_type` | t3.medium | Master instance type |
| `k3s-cluster:worker_instance_type` | t3.small | Worker instance type |
| `k3s-cluster:worker_count` | 2 | Number of worker nodes |
| `k3s-cluster:ssh_key_name` | k3s-key | SSH key pair name |

## Documentation

- [Deployment Guide](docs/guide.md) - Complete step-by-step instructions
- [System Design](SystemDesign.md) - Full system design requirements

## Cleanup

```bash
cd infra
pulumi destroy

# Clean up SSM parameters
aws ssm delete-parameter --name "/k3s/join-token"
aws ssm delete-parameter --name "/k3s/master-ip"
aws ssm delete-parameter --name "/k3s/master-public-ip"
```

## Roadmap

- [x] Phase 1: K3s cluster infrastructure
- [ ] Phase 2: Prometheus monitoring
- [ ] Phase 3: Lambda autoscaler
- [ ] Phase 4: DynamoDB state management

## License

MIT

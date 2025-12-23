# System Design Challenge: Custom K3s Autoscaler on AWS

## Problem Statement

You are a DevOps engineer at a growing e-commerce startup. Your company runs a K3s (lightweight Kubernetes) cluster on AWS EC2 instances to host microservices. The traffic pattern is predictable during business hours but varies significantly:

- **Peak hours (9 AM - 9 PM):** High traffic with CPU usage averaging 70-80%
- **Off-peak hours (9 PM - 9 AM):** Low traffic with CPU usage around 20-30%
- **Flash sales:** Sudden spikes requiring immediate scaling

Currently, you're running 5 worker nodes 24/7, which is costly during off-peak hours and insufficient during peak times.

**Your task:** Design and implement a custom autoscaler that automatically scales K3s worker nodes based on real-time metrics from Prometheus, orchestrated by AWS Lambda.

---

## Objectives

Design a system that:

1. Monitors K3s cluster metrics using Prometheus
2. Makes scaling decisions based on resource utilization
3. Provisions/Deprovisions EC2 worker nodes automatically using AWS Lambda
4. Integrates new nodes seamlessly into the K3s cluster
5. Ensures safe scale-down without disrupting running workloads

---

## Requirements

### Functional Requirements

#### 1. Metric Collection
- Prometheus scrapes metrics from all K3s nodes (CPU, memory, pod count)
- Collect custom application metrics (e.g., pending pods, API latency)

#### 2. Scaling Logic
- **Scale UP when:** Average CPU > 70% OR pending pods exist for > 3 minutes
- **Scale DOWN when:** Average CPU < 30% for > 10 minutes AND no pending pods
- **Minimum nodes:** 2 (for high availability)
- **Maximum nodes:** 10 (cost constraint)

#### 3. Node Provisioning
- Launch new EC2 instances with pre-configured K3s agent
- Automatically join new nodes to the K3s cluster
- Health check: Wait for node to be "Ready" before considering scaling complete

#### 4. Node Deprovisioning
- Gracefully drain workloads from the node before termination
- Respect a 5-minute drain timeout
- Never terminate nodes with critical system pods

#### 5. State Management
- Track active scaling operations to prevent race conditions
- Store cluster state (node count, last scaling time) in DynamoDB

### Non-Functional Requirements

1. **Performance:** Scaling decision latency < 3 minutes
2. **Reliability:** Handle Lambda failures gracefully (retry mechanism)
3. **Cost:** Lambda execution time < 30 seconds per invocation
4. **Security:** Use IAM roles, no hardcoded credentials
5. **Observability:** Log all scaling events to CloudWatch

---

## Technical Components

### 1. K3s Cluster Setup
- **Master Node:** 1x t3.medium (control plane)
- **Worker Nodes:** t3.small instances (auto-scaled)
- **Networking:** VPC with public subnets across 2 AZs

### 2. Prometheus Configuration
- Deployed as a pod on the master node
- Scrape interval: 15 seconds
- Retention: 7 days
- Exposes metrics via HTTP API (e.g., `/api/v1/query`)

### 3. AWS Lambda Function
- Runtime: Python 3.11
- Memory: 256 MB
- Timeout: 60 seconds
- Trigger: EventBridge rule (every 2 minutes)
- Permissions: EC2 (launch/terminate), S3 (read), DynamoDB (read/write)

### 4. Supporting AWS Services
- **S3 Bucket:** Store K3s join token and node configuration scripts
- **DynamoDB Table:** Store cluster state (attributes: `cluster_id`, `node_count`, `last_scale_time`, `scaling_in_progress`)
- **CloudWatch Logs:** Lambda execution logs and scaling events
- **IAM Roles:** Lambda execution role with least privilege

---

## Design Challenges to Address

### 1. Race Condition Prevention
- **Problem:** Multiple Lambda invocations could try to scale simultaneously.
- **Questions:**
  - How do you use DynamoDB's conditional writes to prevent concurrent scaling?
  - What happens if Lambda times out during a scaling operation?

### 2. Node Join Automation
- **Problem:** New EC2 instances need to authenticate and join the K3s cluster.
- **Questions:**
  - How do you securely store and retrieve the K3s join token?
  - What if the master node IP changes?
  - How do you handle instance metadata for node identification?

### 3. Graceful Scale-Down
- **Problem:** Terminating a node with running pods causes service disruption.
- **Questions:**
  - How do you identify which node is safe to remove?
  - What if `kubectl drain` fails or times out?
  - How do you handle stateful applications?

### 4. Prometheus Connectivity
- **Problem:** Lambda needs to reach Prometheus inside the K3s cluster.
- **Questions:**
  - Should Prometheus be exposed via LoadBalancer, NodePort, or Ingress?
  - How do you secure the Prometheus endpoint?
  - What if Prometheus is temporarily unavailable?

### 5. Cost Optimization
- **Problem:** Lambda invocations every 2 minutes add up over time.
- **Questions:**
  - Could you increase the interval during off-peak hours?
  - Should you use an EventBridge scheduler with dynamic intervals?
  - What's the trade-off between response time and cost?

---

## Expected Deliverables

### 1. Architecture Diagram
- Complete system architecture showing all AWS services and data flows
- Network diagram (VPC, subnets, security groups)

### 2. Component Specifications

#### Lambda Function
- Pseudocode or Python code for the scaling logic
- Environment variables
- IAM policy (JSON)

#### Prometheus Configuration
- `prometheus.yml` scrape configs
- Key PromQL queries

#### DynamoDB Schema
- Table structure and example items

#### EC2 User Data Script
- Bash script to install K3s agent and join cluster

### 3. Scaling Algorithm
- Detailed logic with thresholds, cooldown periods, and edge case handling

### 4. Monitoring & Alerting
- Key CloudWatch metrics
- Alarms for scaling failures
- Dashboard layout

### 5. Testing Strategy
- Load simulation
- Scale-down testing
- Failure scenario handling (e.g., Lambda timeout, EC2 quota)

---

## Bonus Challenges (Optional)

- Add multi-AZ awareness
- Mix in Spot instances with graceful interruption handling
- Pre-scale predictively
- Incorporate custom app metrics
- Manage configs GitOps-style
- Send Slack notifications for actions and failures

---

## Flexibility & Innovation Welcome

You have near-total freedom to design a more effective, cost-optimized solution beyond the baseline constraints, provided you explain the rationale, trade-offs, cost impact, feasibility, safety, and provide technical artifacts.

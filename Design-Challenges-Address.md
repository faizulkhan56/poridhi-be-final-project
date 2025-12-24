# Design Challenges & Solutions

This document details how we addressed the distributed system challenges outlined in the System Design, with specific references to the implemented code.

---

## 1. Race Condition Prevention

**Problem:** Multiple Lambda invocations could try to scale simultaneously, leading to over-provisioning or conflicting decisions.

**Solution:** We use **DynamoDB Conditional Writes** to implement a locking mechanism. Before any scaling action, the Lambda attempts to acquire a lock by setting a `scaling_in_progress` flag.

### Code Reference
**File:** [`infra/lambda/state.py`](infra/lambda/state.py)

```python
def set_scaling_lock(self, cluster_id: str, lock: bool) -> bool:
    """
    Acquire or release lock using DynamoDB conditional writes.
    Returns True if successful, False if lock was already held by another process.
    """
    try:
        if lock:
            # Try to acquire lock: Succeeds ONLY if 'scaling_in_progress' is False or doesn't exist
            self.table.update_item(
                Key={'cluster_id': cluster_id},
                UpdateExpression="SET scaling_in_progress = :val, last_updated = :time",
                # This condition is the key to preventing race conditions
                ConditionExpression="attribute_not_exists(scaling_in_progress) OR scaling_in_progress = :false",
                ExpressionAttributeValues={
                    ':val': True,
                    ':time': datetime.now().isoformat(),
                    ':false': False
                }
            )
        else:
            # Release lock
            self.table.update_item(
                Key={'cluster_id': cluster_id},
                UpdateExpression="SET scaling_in_progress = :val",
                ExpressionAttributeValues={':val': False}
            )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False  # Lock acquisition failed - another Lambda is working
        raise
```

---

## 2. Node Join Automation

**Problem:** New EC2 instances need to securely retrieve credentials and join the K3s cluster automatically upon boot.

**Solution:** We use **AWS SSM Parameter Store** to securely store the K3s join token and Master IP. The worker node's `User Data` script (which runs on boot) retrieves these values using the instance's IAM role.

### Code Reference
**File 1: Storing Token (Master)** - [`infra/scripts/master_userdata.sh`](infra/scripts/master_userdata.sh)
```bash
# Retrieve token from K3s
K3S_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token)
MASTER_PRIVATE_IP=$(hostname -I | awk '{print $1}')

# Store in SSM Parameter Store
aws ssm put-parameter --name "/k3s/join-token" --value "$K3S_TOKEN" --type "SecureString" --overwrite
aws ssm put-parameter --name "/k3s/master-ip" --value "$MASTER_PRIVATE_IP" --type "String" --overwrite
```

**File 2: Retrieving & Joining (Worker)** - [`infra/lambda/ec2_manager.py`](infra/lambda/ec2_manager.py) (Injected into User Data)
```bash
# Retrieve credentials from SSM
K3S_TOKEN=$(aws ssm get-parameter --name "/k3s/join-token" --with-decryption --query "Parameter.Value" --output text)
K3S_URL="https://$(aws ssm get-parameter --name "/k3s/master-ip" --query "Parameter.Value" --output text):6443"

# Join Cluster
curl -sfL https://get.k3s.io | K3S_URL=$K3S_URL K3S_TOKEN=$K3S_TOKEN sh -
```

---

## 3. Graceful Scale-Down

**Problem:** We need to ensure we don't terminate static nodes (like the initial ones) and prioritize removing older, potentially less stable autoscaled nodes.

**Solution:** The autoscaler tags all instances it creates with `ManagedBy: autoscaler`. When scaling down, it **filters** to find only these supported instances and sorts them by `LaunchTime` to terminate the oldest one.

### Code Reference
**File:** [`infra/lambda/ec2_manager.py`](infra/lambda/ec2_manager.py)

```python
def terminate_worker(self) -> str:
    # 1. Filter for instances tagged as 'ManagedBy: autoscaler'
    # This ensures we NEVER terminate the initial static nodes
    response = self.ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ManagedBy', 'Values': ['autoscaler']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )

    # 2. Sort by LaunchTime (Oldest first) mechanism
    instances.sort(key=lambda x: x['LaunchTime'])
    oldest_instance = instances[0]

    # 3. Terminate
    self.ec2.terminate_instances(InstanceIds=[oldest_instance['InstanceId']])
```

---

## 4. Prometheus Connectivity

**Problem:** The Lambda function running outside the K3s cluster network needs to reach the Prometheus API running inside pods.

**Solution:** We verified exposing Prometheus via a **NodePort Service** on port `30090`. This opens the port on the EC2 host level, allowing the Lambda to access it via the Master Node's IP (which is stable/known).

### Code Reference
**File 1: Service Definition** - [`infra/k8s/prometheus-service.yaml`](infra/k8s/prometheus-service.yaml)
```yaml
apiVersion: v1
kind: Service
metadata:
  name: prometheus
spec:
  type: NodePort  # Expose externally
  ports:
    - port: 9090
      targetPort: 9090
      nodePort: 30090  # Fixed port known to Lambda
  selector:
    app: prometheus
```

**File 2: Security Group** - [`infra/security_groups.py`](infra/security_groups.py)
```python
# Open Port 30090 in Master SG
aws.ec2.SecurityGroupRule(
    "master-prometheus-ingress",
    type="ingress",
    from_port=30090,
    to_port=30090,
    protocol="tcp",
    cidr_blocks=["0.0.0.0/0"], # Allowed for Lambda access
)
```

---

## 5. Cost Optimization

**Problem:** Frequent Lambda invocations can be costly if configured continuously.

**Solution:** We used **EventBridge Rules** to trigger the Lambda on a fixed schedule (every 2 minutes). This provides a predictable cost model and avoids the need for a continuously running "monitor" server, adhering to the Serverless philosophy.

### Code Reference
**File:** [`infra/lambda_autoscaler.py`](infra/lambda_autoscaler.py)

```python
def create_eventbridge_rule(config: dict, lambda_func):
    # Scheduled Trigger
    rule = aws.cloudwatch.EventRule(
        "k3s-autoscaler-schedule",
        schedule_expression="rate(2 minutes)",  # Optimized interval
    )
```

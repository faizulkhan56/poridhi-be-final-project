"""
EC2 Manager for K3s autoscaler.
Handles launching and terminating worker instances.
"""

import boto3
import os
import logging
import time

logger = logging.getLogger()


class EC2Manager:
    """Manages EC2 worker node lifecycle."""
    
    def __init__(self):
        self.ec2 = boto3.client("ec2")
        self.ssm = boto3.client("ssm")
        
        # Configuration from environment
        self.security_group_id = os.environ.get("WORKER_SECURITY_GROUP")
        self.subnet_ids = [
            os.environ.get("SUBNET_1"),
            os.environ.get("SUBNET_2"),
        ]
        self.iam_profile = os.environ.get("WORKER_IAM_PROFILE")
        self.instance_type = os.environ.get("WORKER_INSTANCE_TYPE", "t2.small")
        self.key_name = os.environ.get("SSH_KEY_NAME", "k3s-key")
    
    def _get_ubuntu_ami(self) -> str:
        """Get latest Ubuntu 22.04 AMI."""
        response = self.ec2.describe_images(
            Owners=["099720109477"],  # Canonical
            Filters=[
                {"Name": "name", "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]},
                {"Name": "virtualization-type", "Values": ["hvm"]},
                {"Name": "state", "Values": ["available"]},
            ]
        )
        
        # Sort by creation date and get the most recent
        images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)
        if images:
            return images[0]["ImageId"]
        raise Exception("No Ubuntu AMI found")
    
    def _get_user_data(self) -> str:
        """Get user data script for worker node."""
        return '''#!/bin/bash
set -e

exec > >(tee /var/log/k3s-worker-setup.log) 2>&1
echo "Starting K3s worker setup at $(date)"

apt-get update -y
apt-get install -y curl unzip jq

# Install AWS CLI v2
curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"

# Wait for master to be ready
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    MASTER_IP=$(aws ssm get-parameter --region "$REGION" --name "/k3s/master-ip" --query "Parameter.Value" --output text 2>/dev/null || echo "")
    
    if [ -n "$MASTER_IP" ] && [ "$MASTER_IP" != "None" ]; then
        echo "Master IP found: $MASTER_IP"
        break
    fi
    
    echo "Master not ready yet, retrying... ($RETRY_COUNT/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 10
done

if [ -z "$MASTER_IP" ] || [ "$MASTER_IP" == "None" ]; then
    echo "ERROR: Failed to get master IP"
    exit 1
fi

TOKEN=$(aws ssm get-parameter --region "$REGION" --name "/k3s/join-token" --with-decryption --query "Parameter.Value" --output text)

if [ -z "$TOKEN" ] || [ "$TOKEN" == "None" ]; then
    echo "ERROR: Failed to retrieve join token"
    exit 1
fi

echo "Installing K3s agent..."
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN="${TOKEN}" sh -s - agent --node-name "k3s-worker-${INSTANCE_ID}"

echo "K3s worker setup completed at $(date)"
'''
    
    def launch_worker(self) -> str:
        """Launch a new worker node."""
        try:
            ami_id = self._get_ubuntu_ami()
            user_data = self._get_user_data()
            
            # Alternate between subnets for distribution
            subnet_id = self.subnet_ids[0] if self.subnet_ids[0] else self.subnet_ids[1]
            
            response = self.ec2.run_instances(
                ImageId=ami_id,
                InstanceType=self.instance_type,
                MinCount=1,
                MaxCount=1,
                KeyName=self.key_name,
                SecurityGroupIds=[self.security_group_id],
                SubnetId=subnet_id,
                IamInstanceProfile={"Name": self.iam_profile},
                UserData=user_data,
                BlockDeviceMappings=[{
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeSize": 20,
                        "VolumeType": "gp3",
                        "DeleteOnTermination": True,
                    }
                }],
                TagSpecifications=[{
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": "k3s-worker-autoscaled"},
                        {"Key": "Project", "Value": "k3s-cluster"},
                        {"Key": "ManagedBy", "Value": "autoscaler"},
                    ]
                }],
            )
            
            instance_id = response["Instances"][0]["InstanceId"]
            logger.info(f"Launched new worker instance: {instance_id}")
            return instance_id
            
        except Exception as e:
            logger.error(f"Failed to launch worker: {e}")
            return None
    
    def terminate_worker(self) -> str:
        """
        Terminate a worker node gracefully.
        Selects the oldest autoscaled worker.
        """
        try:
            # Find autoscaled workers
            response = self.ec2.describe_instances(
                Filters=[
                    {"Name": "tag:ManagedBy", "Values": ["autoscaler"]},
                    {"Name": "tag:Project", "Values": ["k3s-cluster"]},
                    {"Name": "instance-state-name", "Values": ["running"]},
                ]
            )
            
            instances = []
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instances.append({
                        "id": instance["InstanceId"],
                        "launch_time": instance["LaunchTime"],
                    })
            
            if not instances:
                logger.warning("No autoscaled workers found to terminate")
                return None
            
            # Sort by launch time and pick oldest
            instances.sort(key=lambda x: x["launch_time"])
            target_instance = instances[0]["id"]
            
            # TODO: In production, drain the node first via K8s API
            # For now, we just terminate
            logger.info(f"Terminating worker: {target_instance}")
            
            self.ec2.terminate_instances(InstanceIds=[target_instance])
            
            return target_instance
            
        except Exception as e:
            logger.error(f"Failed to terminate worker: {e}")
            return None
    
    def get_worker_count(self) -> int:
        """Get count of running worker instances."""
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {"Name": "tag:Project", "Values": ["k3s-cluster"]},
                    {"Name": "tag:Name", "Values": ["k3s-worker-*"]},
                    {"Name": "instance-state-name", "Values": ["running", "pending"]},
                ]
            )
            
            count = 0
            for reservation in response["Reservations"]:
                count += len(reservation["Instances"])
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to get worker count: {e}")
            return 0

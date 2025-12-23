"""
K3s Worker Nodes infrastructure.
Creates worker nodes that automatically join the K3s cluster.
"""

import pulumi
import pulumi_aws as aws
from config import get_common_tags


def get_ubuntu_ami():
    """Get the latest Ubuntu 22.04 LTS AMI."""
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],  # Canonical
        filters=[
            aws.ec2.GetAmiFilterArgs(
                name="name",
                values=["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
            ),
            aws.ec2.GetAmiFilterArgs(
                name="virtualization-type",
                values=["hvm"],
            ),
        ],
    )
    return ami.id


def create_worker_iam_role(config: dict):
    """Create IAM role for worker nodes with SSM read access."""
    
    # IAM role assume policy
    assume_role_policy = """{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }"""
    
    # Create IAM role
    role = aws.iam.Role(
        "k3s-worker-role",
        assume_role_policy=assume_role_policy,
        tags=get_common_tags(config, "k3s-worker-role"),
    )
    
    # SSM policy for retrieving parameters (read-only)
    ssm_policy = aws.iam.RolePolicy(
        "k3s-worker-ssm-policy",
        role=role.id,
        policy="""{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters"
                    ],
                    "Resource": "arn:aws:ssm:*:*:parameter/k3s/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:DescribeInstances",
                        "ec2:DescribeTags"
                    ],
                    "Resource": "*"
                }
            ]
        }""",
    )
    
    # Create instance profile
    instance_profile = aws.iam.InstanceProfile(
        "k3s-worker-instance-profile",
        role=role.name,
        tags=get_common_tags(config, "k3s-worker-instance-profile"),
    )
    
    return {
        "role": role,
        "instance_profile": instance_profile,
    }


def create_worker_nodes(config: dict, subnets: list, security_group, iam_profile, master_instance):
    """Create K3s worker nodes that auto-join the cluster."""
    
    # Read user data script
    import os
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "worker_userdata.sh")
    with open(script_path, "r") as f:
        user_data = f.read()
    
    # Get Ubuntu AMI
    ami_id = get_ubuntu_ami()
    
    workers = []
    worker_count = config["worker_count"]
    
    for i in range(worker_count):
        # Distribute workers across subnets (AZs)
        subnet = subnets[i % len(subnets)]
        
        worker = aws.ec2.Instance(
            f"k3s-worker-{i+1}",
            instance_type=config["worker_instance_type"],
            ami=ami_id,
            subnet_id=subnet.id,
            vpc_security_group_ids=[security_group.id],
            key_name=config["ssh_key_name"],
            iam_instance_profile=iam_profile.name,
            user_data=user_data,
            root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
                volume_size=20,
                volume_type="gp3",
                delete_on_termination=True,
            ),
            tags=get_common_tags(config, f"k3s-worker-{i+1}"),
            # Enable detailed monitoring
            monitoring=True,
            # Ensure master is created first
            opts=pulumi.ResourceOptions(depends_on=[master_instance]),
        )
        workers.append(worker)
    
    return workers

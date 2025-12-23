"""
K3s Master Node infrastructure.
Creates the master/control plane node with K3s server.
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


def create_master_iam_role(config: dict):
    """Create IAM role for master node with SSM access."""
    
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
        "k3s-master-role",
        assume_role_policy=assume_role_policy,
        tags=get_common_tags(config, "k3s-master-role"),
    )
    
    # SSM policy for storing/retrieving parameters
    ssm_policy = aws.iam.RolePolicy(
        "k3s-master-ssm-policy",
        role=role.id,
        policy="""{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:PutParameter",
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:DeleteParameter"
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
        "k3s-master-instance-profile",
        role=role.name,
        tags=get_common_tags(config, "k3s-master-instance-profile"),
    )
    
    return {
        "role": role,
        "instance_profile": instance_profile,
    }


def create_master_node(config: dict, subnet, security_group, iam_profile):
    """Create the K3s master node."""
    
    # Read user data script
    import os
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "master_userdata.sh")
    with open(script_path, "r") as f:
        user_data = f.read()
    
    # Get Ubuntu AMI
    ami_id = get_ubuntu_ami()
    
    # Create master instance
    master = aws.ec2.Instance(
        "k3s-master",
        instance_type=config["master_instance_type"],
        ami=ami_id,
        subnet_id=subnet.id,
        vpc_security_group_ids=[security_group.id],
        key_name=config["ssh_key_name"],
        iam_instance_profile=iam_profile.name,
        user_data=user_data,
        root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
            volume_size=30,
            volume_type="gp3",
            delete_on_termination=True,
        ),
        tags=get_common_tags(config, "k3s-master"),
        # Enable detailed monitoring
        monitoring=True,
    )
    
    return master

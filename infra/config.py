"""
Configuration loader for K3s cluster infrastructure.
Loads values from Pulumi config with sensible defaults.
"""

import pulumi


def get_config():
    """Load configuration values from Pulumi config."""
    config = pulumi.Config("k3s-cluster")
    aws_config = pulumi.Config("aws")
    
    return {
        # AWS Settings
        "region": aws_config.get("region") or "ap-southeast-1",
        
        # VPC Settings
        "vpc_cidr": config.get("vpc_cidr") or "10.0.0.0/16",
        "public_subnet_cidrs": [
            config.get("subnet1_cidr") or "10.0.1.0/24",
            config.get("subnet2_cidr") or "10.0.2.0/24",
        ],
        
        # Instance Settings
        "master_instance_type": config.get("master_instance_type") or "t3.medium",
        "worker_instance_type": config.get("worker_instance_type") or "t3.small",
        "worker_count": config.get_int("worker_count") or 2,
        
        # SSH Key
        "ssh_key_name": config.get("ssh_key_name") or "k3s-key",
        
        # Tags
        "project_name": "k3s-cluster",
        "environment": pulumi.get_stack(),
    }


def get_common_tags(config: dict, name: str = None) -> dict:
    """Generate common tags for resources."""
    tags = {
        "Project": config["project_name"],
        "Environment": config["environment"],
        "ManagedBy": "Pulumi",
    }
    if name:
        tags["Name"] = name
    return tags

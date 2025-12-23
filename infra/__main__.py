"""
K3s Cluster Infrastructure - Main Entry Point
This module orchestrates all infrastructure components.
"""

import pulumi

# Import Phase 1 modules
from config import get_config
from vpc import create_vpc
from security_groups import create_security_groups
from master import create_master_node, create_master_iam_role
from workers import create_worker_nodes, create_worker_iam_role

# Import Phase 2 modules
from dynamodb import create_dynamodb_table, initialize_cluster_state
from lambda_autoscaler import create_lambda_role, create_lambda_function, create_eventbridge_rule


def main():
    """Main function to create all infrastructure."""
    
    # Load configuration
    config = get_config()
    
    # ===== Phase 1: K3s Cluster =====
    
    # Create VPC and networking
    vpc_resources = create_vpc(config)
    
    # Create security groups
    sg_resources = create_security_groups(config, vpc_resources["vpc"].id)
    
    # Create IAM roles and instance profiles
    master_iam = create_master_iam_role(config)
    worker_iam = create_worker_iam_role(config)
    
    # Create master node (in first subnet/AZ)
    master = create_master_node(
        config=config,
        subnet=vpc_resources["public_subnets"][0],
        security_group=sg_resources["master_sg"],
        iam_profile=master_iam["instance_profile"],
    )
    
    # Create worker nodes (distributed across all subnets/AZs)
    workers = create_worker_nodes(
        config=config,
        subnets=vpc_resources["public_subnets"],
        security_group=sg_resources["worker_sg"],
        iam_profile=worker_iam["instance_profile"],
        master_instance=master,
    )
    
    # ===== Phase 2: Autoscaler =====
    
    # Create DynamoDB table for state management
    dynamodb_table = create_dynamodb_table(config)
    initialize_cluster_state(dynamodb_table, config)
    
    # Create Lambda autoscaler
    lambda_role = create_lambda_role(config)
    lambda_func = create_lambda_function(
        config=config,
        role=lambda_role,
        dynamodb_table=dynamodb_table,
        master_instance=master,
        worker_sg=sg_resources["worker_sg"],
        subnets=vpc_resources["public_subnets"],
        worker_iam_profile=worker_iam["instance_profile"],
    )
    
    # Create EventBridge trigger
    eventbridge_rule = create_eventbridge_rule(config, lambda_func)
    
    # ===== Export Outputs =====
    
    # VPC outputs
    pulumi.export("vpc_id", vpc_resources["vpc"].id)
    pulumi.export("vpc_cidr", vpc_resources["vpc"].cidr_block)
    pulumi.export("availability_zones", vpc_resources["azs"])
    pulumi.export("public_subnet_ids", [s.id for s in vpc_resources["public_subnets"]])
    
    # Master node outputs
    pulumi.export("master_instance_id", master.id)
    pulumi.export("master_private_ip", master.private_ip)
    pulumi.export("master_public_ip", master.public_ip)
    pulumi.export("k3s_api_endpoint", master.public_ip.apply(lambda ip: f"https://{ip}:6443"))
    pulumi.export("prometheus_url", master.public_ip.apply(lambda ip: f"http://{ip}:30090"))
    
    # Worker node outputs
    pulumi.export("worker_instance_ids", [w.id for w in workers])
    pulumi.export("worker_private_ips", [w.private_ip for w in workers])
    pulumi.export("worker_public_ips", [w.public_ip for w in workers])
    
    # SSH commands (for convenience)
    pulumi.export("ssh_master_command", master.public_ip.apply(
        lambda ip: f"ssh -i ~/.ssh/{config['ssh_key_name']}.pem ubuntu@{ip}"
    ))
    
    # Phase 2 outputs
    pulumi.export("dynamodb_table", dynamodb_table.name)
    pulumi.export("lambda_function", lambda_func.name)
    pulumi.export("eventbridge_rule", eventbridge_rule.name)
    
    # Configuration info
    pulumi.export("worker_count", config["worker_count"])
    pulumi.export("master_instance_type", config["master_instance_type"])
    pulumi.export("worker_instance_type", config["worker_instance_type"])


# Run main
main()


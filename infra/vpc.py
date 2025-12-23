"""
VPC and networking infrastructure for K3s cluster.
Creates VPC with 2 public subnets across 2 AZs.
"""

import pulumi
import pulumi_aws as aws
from config import get_common_tags


def create_vpc(config: dict):
    """Create VPC with public subnets across 2 availability zones."""
    
    # Get available AZs
    available_azs = aws.get_availability_zones(state="available")
    azs = available_azs.names[:2]  # Use first 2 AZs
    
    # Create VPC
    vpc = aws.ec2.Vpc(
        "k3s-vpc",
        cidr_block=config["vpc_cidr"],
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags=get_common_tags(config, "k3s-vpc"),
    )
    
    # Create Internet Gateway
    igw = aws.ec2.InternetGateway(
        "k3s-igw",
        vpc_id=vpc.id,
        tags=get_common_tags(config, "k3s-igw"),
    )
    
    # Create public subnets in each AZ
    public_subnets = []
    for i, (az, cidr) in enumerate(zip(azs, config["public_subnet_cidrs"])):
        subnet = aws.ec2.Subnet(
            f"k3s-public-subnet-{i+1}",
            vpc_id=vpc.id,
            cidr_block=cidr,
            availability_zone=az,
            map_public_ip_on_launch=True,
            tags=get_common_tags(config, f"k3s-public-subnet-{i+1}"),
        )
        public_subnets.append(subnet)
    
    # Create route table for public subnets
    public_rt = aws.ec2.RouteTable(
        "k3s-public-rt",
        vpc_id=vpc.id,
        routes=[
            aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=igw.id,
            ),
        ],
        tags=get_common_tags(config, "k3s-public-rt"),
    )
    
    # Associate subnets with route table
    for i, subnet in enumerate(public_subnets):
        aws.ec2.RouteTableAssociation(
            f"k3s-public-rta-{i+1}",
            subnet_id=subnet.id,
            route_table_id=public_rt.id,
        )
    
    return {
        "vpc": vpc,
        "igw": igw,
        "public_subnets": public_subnets,
        "public_rt": public_rt,
        "azs": azs,
    }

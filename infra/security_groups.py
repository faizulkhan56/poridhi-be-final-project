"""
Security groups for K3s cluster.
Defines firewall rules for master and worker nodes.
"""

import pulumi_aws as aws
from config import get_common_tags


def create_security_groups(config: dict, vpc_id):
    """Create security groups for K3s cluster nodes."""
    
    # Master node security group
    master_sg = aws.ec2.SecurityGroup(
        "k3s-master-sg",
        vpc_id=vpc_id,
        description="Security group for K3s master node",
        tags=get_common_tags(config, "k3s-master-sg"),
    )
    
    # Worker node security group
    worker_sg = aws.ec2.SecurityGroup(
        "k3s-worker-sg",
        vpc_id=vpc_id,
        description="Security group for K3s worker nodes",
        tags=get_common_tags(config, "k3s-worker-sg"),
    )
    
    # ===== Master Security Group Rules =====
    
    # SSH access (restrict to your IP in production)
    aws.ec2.SecurityGroupRule(
        "master-ssh-ingress",
        type="ingress",
        from_port=22,
        to_port=22,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],  # Restrict this in production!
        security_group_id=master_sg.id,
        description="SSH access",
    )
    
    # K3s API server (6443)
    aws.ec2.SecurityGroupRule(
        "master-k3s-api-ingress",
        type="ingress",
        from_port=6443,
        to_port=6443,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],  # Restrict this in production!
        security_group_id=master_sg.id,
        description="K3s API server",
    )
    
    # Kubelet API (from workers)
    aws.ec2.SecurityGroupRule(
        "master-kubelet-ingress",
        type="ingress",
        from_port=10250,
        to_port=10250,
        protocol="tcp",
        source_security_group_id=worker_sg.id,
        security_group_id=master_sg.id,
        description="Kubelet API from workers",
    )
    
    # Flannel VXLAN (from workers)
    aws.ec2.SecurityGroupRule(
        "master-flannel-ingress",
        type="ingress",
        from_port=8472,
        to_port=8472,
        protocol="udp",
        source_security_group_id=worker_sg.id,
        security_group_id=master_sg.id,
        description="Flannel VXLAN from workers",
    )
    
    # Allow all egress
    aws.ec2.SecurityGroupRule(
        "master-all-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=master_sg.id,
        description="Allow all outbound traffic",
    )
    
    # Prometheus NodePort (for Lambda autoscaler access)
    aws.ec2.SecurityGroupRule(
        "master-prometheus-ingress",
        type="ingress",
        from_port=30090,
        to_port=30090,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],  # Lambda needs access
        security_group_id=master_sg.id,
        description="Prometheus NodePort for autoscaler",
    )
    
    # ===== Worker Security Group Rules =====
    
    # SSH access (restrict to your IP in production)
    aws.ec2.SecurityGroupRule(
        "worker-ssh-ingress",
        type="ingress",
        from_port=22,
        to_port=22,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],  # Restrict this in production!
        security_group_id=worker_sg.id,
        description="SSH access",
    )
    
    # Kubelet API (from master)
    aws.ec2.SecurityGroupRule(
        "worker-kubelet-ingress",
        type="ingress",
        from_port=10250,
        to_port=10250,
        protocol="tcp",
        source_security_group_id=master_sg.id,
        security_group_id=worker_sg.id,
        description="Kubelet API from master",
    )
    
    # Flannel VXLAN (from master and other workers)
    aws.ec2.SecurityGroupRule(
        "worker-flannel-from-master",
        type="ingress",
        from_port=8472,
        to_port=8472,
        protocol="udp",
        source_security_group_id=master_sg.id,
        security_group_id=worker_sg.id,
        description="Flannel VXLAN from master",
    )
    
    aws.ec2.SecurityGroupRule(
        "worker-flannel-from-workers",
        type="ingress",
        from_port=8472,
        to_port=8472,
        protocol="udp",
        self=True,
        security_group_id=worker_sg.id,
        description="Flannel VXLAN from other workers",
    )
    
    # NodePort services (30000-32767)
    aws.ec2.SecurityGroupRule(
        "worker-nodeport-ingress",
        type="ingress",
        from_port=30000,
        to_port=32767,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=worker_sg.id,
        description="NodePort services",
    )
    
    # Allow all egress
    aws.ec2.SecurityGroupRule(
        "worker-all-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=worker_sg.id,
        description="Allow all outbound traffic",
    )
    
    # Allow all internal communication between workers
    aws.ec2.SecurityGroupRule(
        "worker-internal-ingress",
        type="ingress",
        from_port=0,
        to_port=65535,
        protocol="tcp",
        self=True,
        security_group_id=worker_sg.id,
        description="Internal communication between workers",
    )
    
    return {
        "master_sg": master_sg,
        "worker_sg": worker_sg,
    }

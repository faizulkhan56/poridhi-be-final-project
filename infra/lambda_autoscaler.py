"""
Lambda function for K3s autoscaler.
Queries Prometheus metrics and makes scaling decisions.
"""

import pulumi
import pulumi_aws as aws
import json
import os
from config import get_common_tags


def create_lambda_role(config: dict):
    """Create IAM role for Lambda with required permissions."""
    
    # Assume role policy for Lambda
    assume_role_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    })
    
    role = aws.iam.Role(
        "k3s-autoscaler-lambda-role",
        assume_role_policy=assume_role_policy,
        tags=get_common_tags(config, "k3s-autoscaler-lambda-role"),
    )
    
    # Lambda execution policy
    lambda_policy = aws.iam.RolePolicy(
        "k3s-autoscaler-lambda-policy",
        role=role.id,
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:RunInstances",
                        "ec2:TerminateInstances",
                        "ec2:DescribeInstances",
                        "ec2:DescribeInstanceStatus",
                        "ec2:CreateTags",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeSecurityGroups",
                        "ec2:DescribeImages"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": ["iam:PassRole"],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Query"
                    ],
                    "Resource": "arn:aws:dynamodb:*:*:table/k3s-cluster-state"
                },
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
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "arn:aws:logs:*:*:*"
                }
            ]
        }),
    )
    
    return role


def create_lambda_function(config: dict, role, dynamodb_table, master_instance, worker_sg, subnets, worker_iam_profile):
    """Create Lambda function for autoscaling."""
    
    # Read Lambda code
    lambda_dir = os.path.join(os.path.dirname(__file__), "lambda")
    
    # Create a zip archive of the Lambda code
    lambda_archive = pulumi.asset.AssetArchive({
        "handler.py": pulumi.asset.FileAsset(os.path.join(lambda_dir, "handler.py")),
        "metrics.py": pulumi.asset.FileAsset(os.path.join(lambda_dir, "metrics.py")),
        "scaler.py": pulumi.asset.FileAsset(os.path.join(lambda_dir, "scaler.py")),
        "ec2_manager.py": pulumi.asset.FileAsset(os.path.join(lambda_dir, "ec2_manager.py")),
        "state.py": pulumi.asset.FileAsset(os.path.join(lambda_dir, "state.py")),
    })
    
    # Environment variables for Lambda
    environment_vars = pulumi.Output.all(
        master_instance.public_ip,
        worker_sg.id,
        subnets[0].id,
        subnets[1].id if len(subnets) > 1 else subnets[0].id,
        worker_iam_profile.name,
        config["worker_instance_type"],
        config["ssh_key_name"],
    ).apply(lambda args: {
        "PROMETHEUS_URL": f"http://{args[0]}:30090",
        "DYNAMODB_TABLE": "k3s-cluster-state",
        "CLUSTER_ID": "k3s-main",
        "WORKER_SECURITY_GROUP": args[1],
        "SUBNET_1": args[2],
        "SUBNET_2": args[3],
        "WORKER_IAM_PROFILE": args[4],
        "WORKER_INSTANCE_TYPE": args[5],
        "SSH_KEY_NAME": args[6],
        "MIN_NODES": "2",
        "MAX_NODES": "10",
        "SCALE_UP_CPU_THRESHOLD": "70",
        "SCALE_DOWN_CPU_THRESHOLD": "30",
        "SCALE_DOWN_WAIT_MINUTES": "10",
        "COOLDOWN_MINUTES": "5",
    })
    
    # Create Lambda function
    lambda_func = aws.lambda_.Function(
        "k3s-autoscaler",
        name="k3s-autoscaler",
        role=role.arn,
        runtime="python3.11",
        handler="handler.lambda_handler",
        code=lambda_archive,
        timeout=60,
        memory_size=256,
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables=environment_vars,
        ),
        tags=get_common_tags(config, "k3s-autoscaler"),
    )
    
    return lambda_func


def create_eventbridge_rule(config: dict, lambda_func):
    """Create EventBridge rule to trigger Lambda every 2 minutes."""
    
    # EventBridge rule
    rule = aws.cloudwatch.EventRule(
        "k3s-autoscaler-schedule",
        name="k3s-autoscaler-schedule",
        description="Trigger K3s autoscaler every 2 minutes",
        schedule_expression="rate(2 minutes)",
        tags=get_common_tags(config, "k3s-autoscaler-schedule"),
    )
    
    # Target Lambda
    target = aws.cloudwatch.EventTarget(
        "k3s-autoscaler-target",
        rule=rule.name,
        arn=lambda_func.arn,
    )
    
    # Permission for EventBridge to invoke Lambda
    permission = aws.lambda_.Permission(
        "k3s-autoscaler-permission",
        action="lambda:InvokeFunction",
        function=lambda_func.name,
        principal="events.amazonaws.com",
        source_arn=rule.arn,
    )
    
    return rule

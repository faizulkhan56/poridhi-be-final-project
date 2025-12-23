"""
DynamoDB table for K3s autoscaler state management.
Stores cluster state and prevents race conditions.
"""

import pulumi
import pulumi_aws as aws
from config import get_common_tags


def create_dynamodb_table(config: dict):
    """Create DynamoDB table for cluster state management."""
    
    table = aws.dynamodb.Table(
        "k3s-cluster-state",
        name="k3s-cluster-state",
        billing_mode="PAY_PER_REQUEST",  # On-demand pricing
        hash_key="cluster_id",
        attributes=[
            aws.dynamodb.TableAttributeArgs(
                name="cluster_id",
                type="S",
            ),
        ],
        tags=get_common_tags(config, "k3s-cluster-state"),
    )
    
    return table


def initialize_cluster_state(table, config: dict):
    """Create initial cluster state item."""
    
    # Initial state item
    initial_state = aws.dynamodb.TableItem(
        "k3s-initial-state",
        table_name=table.name,
        hash_key=table.hash_key,
        item=pulumi.Output.all(config["worker_count"]).apply(lambda args: f'''{{
            "cluster_id": {{"S": "k3s-main"}},
            "node_count": {{"N": "{args[0]}"}},
            "min_nodes": {{"N": "2"}},
            "max_nodes": {{"N": "10"}},
            "last_scale_time": {{"S": "1970-01-01T00:00:00Z"}},
            "scaling_in_progress": {{"BOOL": false}},
            "cooldown_until": {{"S": "1970-01-01T00:00:00Z"}}
        }}'''),
    )
    
    return initial_state

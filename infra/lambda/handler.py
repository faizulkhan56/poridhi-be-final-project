"""
Lambda handler for K3s autoscaler.
Entry point for the Lambda function.
"""

import json
import os
import logging
from metrics import PrometheusMetrics
from scaler import ScalingDecision
from ec2_manager import EC2Manager
from state import ClusterState

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Main Lambda handler for K3s autoscaling.
    
    This function:
    1. Fetches metrics from Prometheus
    2. Gets current cluster state from DynamoDB
    3. Makes scaling decisions
    4. Executes scale up/down if needed
    5. Updates cluster state
    """
    logger.info("K3s Autoscaler Lambda started")
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Initialize components
        prometheus_url = os.environ.get("PROMETHEUS_URL")
        cluster_id = os.environ.get("CLUSTER_ID", "k3s-main")
        
        metrics = PrometheusMetrics(prometheus_url)
        state = ClusterState(cluster_id)
        ec2_manager = EC2Manager()
        scaler = ScalingDecision()
        
        # Check if scaling is already in progress
        cluster_state = state.get_state()
        if cluster_state.get("scaling_in_progress", False):
            logger.info("Scaling already in progress, skipping this invocation")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Scaling in progress, skipped"})
            }
        
        # Check cooldown
        if state.is_in_cooldown():
            logger.info("In cooldown period, skipping this invocation")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "In cooldown, skipped"})
            }
        
        # Fetch metrics from Prometheus
        try:
            avg_cpu = metrics.get_average_cpu()
            pending_pods = metrics.get_pending_pods()
            node_count = metrics.get_node_count()
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
            # Use state from DynamoDB as fallback
            avg_cpu = 50  # Neutral value
            pending_pods = 0
            node_count = cluster_state.get("node_count", 2)
        
        logger.info(f"Metrics - CPU: {avg_cpu}%, Pending Pods: {pending_pods}, Nodes: {node_count}")
        
        # Make scaling decision
        decision = scaler.decide(
            avg_cpu=avg_cpu,
            pending_pods=pending_pods,
            current_nodes=node_count,
            min_nodes=int(os.environ.get("MIN_NODES", 2)),
            max_nodes=int(os.environ.get("MAX_NODES", 10)),
        )
        
        logger.info(f"Scaling decision: {decision['action']}")
        
        if decision["action"] == "none":
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No scaling needed", "metrics": {
                    "cpu": avg_cpu,
                    "pending_pods": pending_pods,
                    "nodes": node_count
                }})
            }
        
        # Acquire lock
        if not state.acquire_lock():
            logger.warning("Failed to acquire scaling lock")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Could not acquire lock"})
            }
        
        try:
            if decision["action"] == "scale_up":
                logger.info("Executing scale UP")
                new_instance = ec2_manager.launch_worker()
                if new_instance:
                    state.update_node_count(node_count + 1)
                    logger.info(f"Launched new worker: {new_instance}")
                else:
                    logger.error("Failed to launch new worker")
                    
            elif decision["action"] == "scale_down":
                logger.info("Executing scale DOWN")
                terminated = ec2_manager.terminate_worker()
                if terminated:
                    state.update_node_count(node_count - 1)
                    logger.info(f"Terminated worker: {terminated}")
                else:
                    logger.error("Failed to terminate worker")
                    
        finally:
            # Release lock and set cooldown
            state.release_lock()
            state.set_cooldown()
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Scaling {decision['action']} completed",
                "metrics": {
                    "cpu": avg_cpu,
                    "pending_pods": pending_pods,
                    "nodes": node_count
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Error in autoscaler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

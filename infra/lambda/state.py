"""
State management for K3s autoscaler.
Uses DynamoDB for cluster state and race condition prevention.
"""

import boto3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger()


class ClusterState:
    """Manages cluster state in DynamoDB."""
    
    def __init__(self, cluster_id: str):
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ.get("DYNAMODB_TABLE", "k3s-cluster-state")
        self.table = self.dynamodb.Table(self.table_name)
        self.cluster_id = cluster_id
        self.cooldown_minutes = int(os.environ.get("COOLDOWN_MINUTES", 5))
    
    def get_state(self) -> dict:
        """Get current cluster state."""
        try:
            response = self.table.get_item(
                Key={"cluster_id": self.cluster_id}
            )
            return response.get("Item", {})
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return {}
    
    def acquire_lock(self) -> bool:
        """
        Acquire scaling lock using DynamoDB conditional write.
        Returns True if lock acquired, False otherwise.
        """
        try:
            self.table.update_item(
                Key={"cluster_id": self.cluster_id},
                UpdateExpression="SET scaling_in_progress = :val",
                ConditionExpression="scaling_in_progress = :false OR attribute_not_exists(scaling_in_progress)",
                ExpressionAttributeValues={
                    ":val": True,
                    ":false": False,
                }
            )
            logger.info("Acquired scaling lock")
            return True
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            logger.warning("Failed to acquire lock - scaling already in progress")
            return False
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False
    
    def release_lock(self) -> bool:
        """Release scaling lock."""
        try:
            self.table.update_item(
                Key={"cluster_id": self.cluster_id},
                UpdateExpression="SET scaling_in_progress = :val",
                ExpressionAttributeValues={
                    ":val": False,
                }
            )
            logger.info("Released scaling lock")
            return True
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            return False
    
    def update_node_count(self, count: int) -> bool:
        """Update node count and last scale time."""
        try:
            now = datetime.utcnow().isoformat() + "Z"
            self.table.update_item(
                Key={"cluster_id": self.cluster_id},
                UpdateExpression="SET node_count = :count, last_scale_time = :time",
                ExpressionAttributeValues={
                    ":count": count,
                    ":time": now,
                }
            )
            logger.info(f"Updated node count to {count}")
            return True
        except Exception as e:
            logger.error(f"Failed to update node count: {e}")
            return False
    
    def set_cooldown(self) -> bool:
        """Set cooldown period after scaling action."""
        try:
            cooldown_until = (datetime.utcnow() + timedelta(minutes=self.cooldown_minutes)).isoformat() + "Z"
            self.table.update_item(
                Key={"cluster_id": self.cluster_id},
                UpdateExpression="SET cooldown_until = :time",
                ExpressionAttributeValues={
                    ":time": cooldown_until,
                }
            )
            logger.info(f"Set cooldown until {cooldown_until}")
            return True
        except Exception as e:
            logger.error(f"Failed to set cooldown: {e}")
            return False
    
    def is_in_cooldown(self) -> bool:
        """Check if cluster is in cooldown period."""
        try:
            state = self.get_state()
            cooldown_until = state.get("cooldown_until", "1970-01-01T00:00:00Z")
            
            # Parse ISO timestamp
            cooldown_time = datetime.fromisoformat(cooldown_until.rstrip("Z"))
            now = datetime.utcnow()
            
            in_cooldown = now < cooldown_time
            if in_cooldown:
                logger.info(f"In cooldown until {cooldown_until}")
            return in_cooldown
        except Exception as e:
            logger.error(f"Failed to check cooldown: {e}")
            return False  # Assume not in cooldown on error

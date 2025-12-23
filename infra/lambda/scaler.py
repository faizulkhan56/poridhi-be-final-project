"""
Scaling decision logic for K3s autoscaler.
"""

import os
import logging

logger = logging.getLogger()


class ScalingDecision:
    """Makes scaling decisions based on metrics."""
    
    def __init__(self):
        self.scale_up_cpu_threshold = int(os.environ.get("SCALE_UP_CPU_THRESHOLD", 70))
        self.scale_down_cpu_threshold = int(os.environ.get("SCALE_DOWN_CPU_THRESHOLD", 30))
    
    def decide(
        self,
        avg_cpu: float,
        pending_pods: int,
        current_nodes: int,
        min_nodes: int = 2,
        max_nodes: int = 10,
    ) -> dict:
        """
        Make a scaling decision based on metrics.
        
        Scaling Logic:
        - Scale UP when: avg_cpu > 70% OR pending_pods > 0
        - Scale DOWN when: avg_cpu < 30% AND pending_pods == 0
        
        Constraints:
        - Never go below min_nodes
        - Never exceed max_nodes
        
        Returns:
            dict with 'action' ('scale_up', 'scale_down', or 'none') and 'reason'
        """
        logger.info(f"Evaluating: CPU={avg_cpu}%, pending={pending_pods}, nodes={current_nodes}")
        
        # Check for scale UP
        if pending_pods > 0:
            if current_nodes < max_nodes:
                return {
                    "action": "scale_up",
                    "reason": f"Pending pods detected: {pending_pods}",
                    "target_nodes": current_nodes + 1
                }
            else:
                logger.warning(f"Want to scale up but at max nodes ({max_nodes})")
                return {
                    "action": "none",
                    "reason": f"At max nodes ({max_nodes}), cannot scale up"
                }
        
        if avg_cpu > self.scale_up_cpu_threshold:
            if current_nodes < max_nodes:
                return {
                    "action": "scale_up",
                    "reason": f"High CPU: {avg_cpu}% > {self.scale_up_cpu_threshold}%",
                    "target_nodes": current_nodes + 1
                }
            else:
                logger.warning(f"High CPU but at max nodes ({max_nodes})")
                return {
                    "action": "none",
                    "reason": f"High CPU but at max nodes ({max_nodes})"
                }
        
        # Check for scale DOWN
        if avg_cpu < self.scale_down_cpu_threshold and pending_pods == 0:
            if current_nodes > min_nodes:
                return {
                    "action": "scale_down",
                    "reason": f"Low CPU: {avg_cpu}% < {self.scale_down_cpu_threshold}%",
                    "target_nodes": current_nodes - 1
                }
            else:
                logger.info(f"Low CPU but at min nodes ({min_nodes})")
                return {
                    "action": "none",
                    "reason": f"At min nodes ({min_nodes}), cannot scale down"
                }
        
        # No scaling needed
        return {
            "action": "none",
            "reason": "Metrics within acceptable range"
        }

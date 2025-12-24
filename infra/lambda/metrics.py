"""
Prometheus metrics collection for K3s autoscaler.
"""

import urllib.request
import urllib.error
import json
import logging

logger = logging.getLogger()


class PrometheusMetrics:
    """Fetches metrics from Prometheus."""
    
    def __init__(self, prometheus_url: str):
        self.base_url = prometheus_url.rstrip("/")
        self.query_url = f"{self.base_url}/api/v1/query"
    
    def _query(self, promql: str) -> dict:
        """Execute a PromQL query."""
        try:
            url = f"{self.query_url}?query={urllib.parse.quote(promql)}"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.URLError as e:
            logger.error(f"Failed to query Prometheus: {e}")
            raise
        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            raise
    
    def get_average_cpu(self) -> float:
        """
        Get average CPU usage across all nodes.
        Uses cAdvisor metrics since node-exporter might not be present.
        Returns percentage (0-100).
        """
        # Query: Sum of CPU usage of all root containers / Total cores * 100
        query = 'sum(rate(container_cpu_usage_seconds_total{id="/"}[5m])) / sum(machine_cpu_cores) * 100'
        
        try:
            result = self._query(query.strip())
            if result.get("status") == "success":
                data = result.get("data", {})
                results = data.get("result", [])
                if results:
                    value = float(results[0].get("value", [0, 0])[1])
                    return round(value, 2)
            return 0.0  # Default low value to avoid accidental scaling
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return 0.0
    
    def get_pending_pods(self) -> int:
        """Get count of pending pods in the cluster."""
        query = 'kube_pod_status_phase{phase="Pending"}'
        
        try:
            result = self._query(query)
            if result.get("status") == "success":
                data = result.get("data", {})
                results = data.get("result", [])
                # Count number of pending pods
                pending_count = 0
                for r in results:
                    value = int(float(r.get("value", [0, 0])[1]))
                    pending_count += value
                return pending_count
            return 0
        except Exception as e:
            logger.warning(f"Failed to get pending pods: {e}")
            return 0
    
    def get_node_count(self) -> int:
        """Get count of ready nodes in the cluster."""
        query = 'count(kube_node_status_condition{condition="Ready",status="true"})'
        
        try:
            result = self._query(query)
            if result.get("status") == "success":
                data = result.get("data", {})
                results = data.get("result", [])
                if results:
                    return int(float(results[0].get("value", [0, 0])[1]))
            return 2  # Default minimum
        except Exception as e:
            logger.warning(f"Failed to get node count: {e}")
            return 2
    
    def get_memory_usage(self) -> float:
        """Get average memory usage percentage across nodes."""
        query = '''
        (1 - avg(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
        '''
        
        try:
            result = self._query(query.strip())
            if result.get("status") == "success":
                data = result.get("data", {})
                results = data.get("result", [])
                if results:
                    return round(float(results[0].get("value", [0, 0])[1]), 2)
            return 50.0
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return 50.0
    
    def is_healthy(self) -> bool:
        """Check if Prometheus is reachable."""
        try:
            url = f"{self.base_url}/-/healthy"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False


# Import for URL encoding
import urllib.parse

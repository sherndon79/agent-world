"""
Unified metrics reporting system for Agent World Extensions.

Ensures consistent metrics implementation across all extensions while allowing 
extension-specific metrics registration. Eliminates code duplication and prevents drift.

Usage:
    from agent_world_metrics import WorldExtensionMetrics
    
    # In api_interface.py
    self.metrics = WorldExtensionMetrics('worldbuilder')
    self.metrics.start_server()  # Call when server starts
    
    # Register extension-specific metrics
    self.metrics.register_counter('elements_created', 'Total elements created')
    self.metrics.register_gauge('scene_objects', 'Objects in scene', 
                               lambda: self.scene_builder.get_object_count())
    
    # In http_handler.py
    def _handle_metrics(self):
        return self.api_interface.metrics.get_json_metrics()
    
    def _get_prometheus_metrics(self):
        return self.api_interface.metrics.get_prometheus_metrics()
"""

import time
import threading
from typing import Dict, Any, Callable, Optional, List
import logging

logger = logging.getLogger(__name__)


class WorldExtensionMetrics:
    """
    Centralized metrics management for World* extensions.
    
    Provides consistent metrics collection and reporting across all extensions:
    - Standard base metrics (requests, errors, uptime)
    - Extension-specific counters and gauges
    - Thread-safe operations
    - JSON and Prometheus output formats
    - Unified naming conventions
    """
    
    def __init__(self, extension_name: str):
        """
        Initialize metrics system for an extension.
        
        Args:
            extension_name: Name of extension (e.g. 'worldbuilder', 'worldviewer')
        """
        self.extension_name = extension_name.lower()
        self.prefix = self.extension_name
        
        # Core metrics (identical across all extensions)
        self._core_stats = {
            'requests_received': 0,
            'errors': 0, 
            'start_time': None,
            'server_running': False,
            'auth_failures': 0,
            'rate_limited': 0,
            'request_duration_ms_sum': 0.0,
            'request_duration_ms_count': 0,
        }
        
        # Extension-specific metrics registry
        self._custom_counters: Dict[str, Dict[str, Any]] = {}
        self._custom_gauges: Dict[str, Dict[str, Any]] = {}
        self._custom_stats: Dict[str, Any] = {}
        # Per-endpoint simple counters (no labels in JSON, labels in Prom)
        self._endpoint_requests: Dict[str, int] = {}
        
        # Thread safety
        self._lock = threading.Lock()
    
    def start_server(self):
        """Call when HTTP server starts - initializes start_time."""
        with self._lock:
            self._core_stats['start_time'] = time.time()
            self._core_stats['server_running'] = True
            logger.debug(f"{self.extension_name} metrics system started")
    
    def stop_server(self):
        """Call when HTTP server stops."""
        with self._lock:
            self._core_stats['server_running'] = False
            logger.debug(f"{self.extension_name} metrics system stopped")
    
    def increment_requests(self):
        """Increment request counter - call on each HTTP request."""
        with self._lock:
            self._core_stats['requests_received'] += 1
    
    def increment_errors(self):
        """Increment error counter - call on each HTTP error response."""
        with self._lock:
            self._core_stats['errors'] += 1
    
    def register_counter(self, name: str, description: str):
        """
        Register a custom counter metric.
        
        Args:
            name: Metric name (e.g. 'elements_created')
            description: Human-readable description
        """
        with self._lock:
            self._custom_counters[name] = {
                'value': 0,
                'description': description,
                'type': 'counter'
            }
            logger.debug(f"Registered counter: {self.prefix}_{name}")
    
    def register_gauge(self, name: str, description: str, value_func: Callable[[], Any]):
        """
        Register a custom gauge metric with a function that returns current value.
        
        Args:
            name: Metric name (e.g. 'active_waypoints')  
            description: Human-readable description
            value_func: Function that returns current gauge value
        """
        with self._lock:
            self._custom_gauges[name] = {
                'func': value_func,
                'description': description,
                'type': 'gauge'
            }
            logger.debug(f"Registered gauge: {self.prefix}_{name}")
    
    def increment_counter(self, name: str, amount: int = 1):
        """
        Increment a custom counter.
        
        Args:
            name: Counter name (must be registered first)
            amount: Amount to increment by
        """
        with self._lock:
            if name in self._custom_counters:
                self._custom_counters[name]['value'] += amount
            else:
                logger.warning(f"Attempted to increment unregistered counter: {name}")
    
    def set_custom_stat(self, name: str, value: Any):
        """Set a custom statistic value."""
        with self._lock:
            self._custom_stats[name] = value

    def increment_endpoint(self, endpoint: str):
        """Increment per-endpoint request counter."""
        with self._lock:
            self._endpoint_requests[endpoint] = self._endpoint_requests.get(endpoint, 0) + 1
    
    def get_uptime(self) -> float:
        """Calculate server uptime in seconds."""
        start_time = self._core_stats.get('start_time', 0)
        if start_time and isinstance(start_time, (int, float)):
            return max(0.0, time.time() - start_time)
        return 0.0

    # Security/backpressure helpers
    def increment_auth_failures(self):
        with self._lock:
            self._core_stats['auth_failures'] += 1

    def increment_rate_limited(self):
        with self._lock:
            self._core_stats['rate_limited'] += 1

    # Request timing aggregation (simple sum/count for avg)
    def record_request_duration_ms(self, duration_ms: float):
        with self._lock:
            self._core_stats['request_duration_ms_sum'] += float(duration_ms)
            self._core_stats['request_duration_ms_count'] += 1
    
    def get_json_metrics(self) -> Dict[str, Any]:
        """
        Get metrics in JSON format for /metrics endpoint.
        
        Returns:
            Dictionary with success flag and metrics data
        """
        try:
            with self._lock:
                uptime = self.get_uptime()
                
                # Base metrics (consistent across all extensions)
                metrics = {
                    'requests_received': self._core_stats['requests_received'],
                    'errors': self._core_stats['errors'],
                    'uptime_seconds': uptime,
                    'server_running': self._core_stats['server_running'],
                    'start_time': self._core_stats['start_time'],
                    'auth_failures': self._core_stats['auth_failures'],
                    'rate_limited': self._core_stats['rate_limited'],
                    'request_duration_ms_sum': self._core_stats['request_duration_ms_sum'],
                    'request_duration_ms_count': self._core_stats['request_duration_ms_count'],
                }
                
                # Add custom counters
                for name, counter in self._custom_counters.items():
                    metrics[name] = counter['value']
                
                # Add custom gauges (call their functions)
                for name, gauge in self._custom_gauges.items():
                    try:
                        metrics[name] = gauge['func']()
                    except Exception as e:
                        logger.warning(f"Error calling gauge function {name}: {e}")
                        metrics[name] = 0
                
                # Add custom stats
                metrics.update(self._custom_stats)
                
                return {'success': True, 'metrics': metrics}
                
        except Exception as e:
            logger.error(f"Error generating JSON metrics: {e}")
            return {'success': False, 'error': f'Metrics error: {e}'}
    
    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus format for /metrics.prom endpoint.
        
        Returns:
            Prometheus formatted metrics string
        """
        try:
            with self._lock:
                uptime = self.get_uptime()
                metrics = []
                
                # Core metrics (consistent naming pattern)
                metrics.extend([
                    f"# HELP {self.prefix}_requests_total Total number of requests",
                    f"# TYPE {self.prefix}_requests_total counter",
                    f"{self.prefix}_requests_total {self._core_stats['requests_received']}",
                    f"# HELP {self.prefix}_errors_total Total number of errors",
                    f"# TYPE {self.prefix}_errors_total counter", 
                    f"{self.prefix}_errors_total {self._core_stats['errors']}",
                    f"# HELP {self.prefix}_auth_failures_total Total number of auth failures",
                    f"# TYPE {self.prefix}_auth_failures_total counter",
                    f"{self.prefix}_auth_failures_total {self._core_stats['auth_failures']}",
                    f"# HELP {self.prefix}_rate_limited_total Total number of rate-limited requests",
                    f"# TYPE {self.prefix}_rate_limited_total counter",
                    f"{self.prefix}_rate_limited_total {self._core_stats['rate_limited']}",
                    f"# HELP {self.prefix}_request_duration_ms_sum Aggregate request duration milliseconds",
                    f"# TYPE {self.prefix}_request_duration_ms_sum counter",
                    f"{self.prefix}_request_duration_ms_sum {self._core_stats['request_duration_ms_sum']}",
                    f"# HELP {self.prefix}_request_duration_ms_count Count of measured requests",
                    f"# TYPE {self.prefix}_request_duration_ms_count counter",
                    f"{self.prefix}_request_duration_ms_count {self._core_stats['request_duration_ms_count']}",
                    f"# HELP {self.prefix}_uptime_seconds Server uptime in seconds",
                    f"# TYPE {self.prefix}_uptime_seconds gauge",
                    f"{self.prefix}_uptime_seconds {uptime}"
                ])
                
                # Custom counters
                for name, counter in self._custom_counters.items():
                    metrics.extend([
                        f"# HELP {self.prefix}_{name} {counter['description']}", 
                        f"# TYPE {self.prefix}_{name} {counter['type']}",
                        f"{self.prefix}_{name} {counter['value']}"
                    ])
                
                # Custom gauges
                for name, gauge in self._custom_gauges.items():
                    try:
                        value = gauge['func']()
                        metrics.extend([
                            f"# HELP {self.prefix}_{name} {gauge['description']}",
                            f"# TYPE {self.prefix}_{name} {gauge['type']}",
                            f"{self.prefix}_{name} {value}"
                        ])
                    except Exception as e:
                        logger.warning(f"Error calling gauge function {name}: {e}")
                        # Skip failed gauge calculations
                
                metrics.append("")  # Final newline
                return "\\n".join(metrics)
                
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return f"# Error generating metrics: {e}\\n"
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """
        Get raw stats dictionary for backward compatibility.
        Used by existing code that accesses _api_stats directly.
        """
        with self._lock:
            stats = self._core_stats.copy()
            
            # Add counter values
            for name, counter in self._custom_counters.items():
                stats[name] = counter['value']
            
            # Add custom stats
            stats.update(self._custom_stats)
            
            return stats


# Extension-specific metrics setup functions

def setup_worldbuilder_metrics() -> WorldExtensionMetrics:
    """Setup metrics for WorldBuilder extension with its specific counters/gauges."""
    metrics = WorldExtensionMetrics("worldbuilder")
    
    # Register WorldBuilder-specific counters
    metrics.register_counter("elements_created", "Total primitive elements created")
    metrics.register_counter("batches_created", "Total batches created")
    metrics.register_counter("assets_placed", "Total USD assets placed")
    metrics.register_counter("objects_queried", "Total object query operations")
    metrics.register_counter("transformations_applied", "Total object transformations")
    
    # Note: Gauges would be registered when scene_builder is available
    # metrics.register_gauge("scene_objects", "Objects in current scene",
    #                       lambda: scene_builder.get_object_count())
    
    return metrics


def setup_worldviewer_metrics() -> WorldExtensionMetrics:
    """Setup metrics for WorldViewer extension with its specific counters/gauges."""
    metrics = WorldExtensionMetrics("worldviewer")
    
    # Register WorldViewer-specific counters
    metrics.register_counter("camera_moves", "Total camera position changes")
    metrics.register_counter("cinematic_operations", "Total cinematic operations")
    metrics.register_counter("frame_operations", "Total frame operations")
    metrics.register_counter("orbit_operations", "Total orbit camera operations")
    
    # Note: Gauges would be registered when camera_controller is available
    # metrics.register_gauge("active_movements", "Active camera movements", 
    #                       lambda: len(camera_controller.active_movements))
    
    return metrics


def setup_worldsurveyor_metrics() -> WorldExtensionMetrics:
    """Setup metrics for WorldSurveyor extension with its specific counters/gauges."""
    metrics = WorldExtensionMetrics("worldsurveyor")
    
    # Register WorldSurveyor-specific counters
    metrics.register_counter("waypoints_created", "Total waypoints created")
    metrics.register_counter("groups_created", "Total waypoint groups created")
    metrics.register_counter("navigations_performed", "Total navigation operations")
    metrics.register_counter("waypoints_deleted", "Total waypoints deleted")
    
    # Note: Gauges would be registered when waypoint_manager is available
    # metrics.register_gauge("active_waypoints", "Current number of waypoints", 
    #                       lambda: len(waypoint_manager.get_all_waypoints()))
    
    return metrics


def setup_worldrecorder_metrics() -> WorldExtensionMetrics:
    """Setup metrics for WorldRecorder extension with its specific counters/gauges."""
    metrics = WorldExtensionMetrics("worldrecorder")
    
    # Register WorldRecorder-specific counters  
    metrics.register_counter("recordings_started", "Total recordings started")
    metrics.register_counter("frames_captured", "Total frames captured")
    metrics.register_counter("videos_created", "Total videos created")
    metrics.register_counter("capture_errors", "Total capture errors")
    
    # Note: Gauges would be registered when recorder is available
    # metrics.register_gauge("recording_active", "Whether recording is active",
    #                       lambda: 1 if recorder.is_recording() else 0)
    
    return metrics


def setup_videocapture_metrics() -> WorldExtensionMetrics:
    """Setup metrics for VideoCapture extension."""
    metrics = WorldExtensionMetrics("videocapture")
    metrics.register_counter("videos_started", "Total video captures started")
    metrics.register_counter("captures_stopped", "Total captures stopped")
    metrics.register_counter("capture_errors", "Total capture errors")
    return metrics


# Unified HTTP handler methods that extensions can use directly

class MetricsHandlerMixin:
    """
    Mixin class that provides standard metrics HTTP handler methods.
    Extensions can inherit from this to get consistent metrics endpoints.
    """
    
    def _handle_metrics_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Handle metrics HTTP requests.
        
        Args:
            endpoint: Either 'metrics' for JSON or 'metrics.prom' for Prometheus
            
        Returns:
            Response dictionary
        """
        if not hasattr(self, 'api_interface') or not hasattr(self.api_interface, 'metrics'):
            return {'success': False, 'error': 'Metrics system not initialized'}
        
        if endpoint == 'metrics' or endpoint == 'metrics.json':
            return self.api_interface.metrics.get_json_metrics()
        elif endpoint == 'metrics.prom':
            return {'success': True, '_raw_text': self.api_interface.metrics.get_prometheus_metrics()}
        else:
            return {'success': False, 'error': f'Unknown metrics endpoint: {endpoint}'}


if __name__ == "__main__":
    # Test the metrics system
    print("Agent World Extensions Metrics System")
    
    # Test each extension's metrics setup
    extensions = [
        ('worldbuilder', setup_worldbuilder_metrics),
        ('worldviewer', setup_worldviewer_metrics), 
        ('worldsurveyor', setup_worldsurveyor_metrics),
        ('worldrecorder', setup_worldrecorder_metrics)
    ]
    
    for name, setup_func in extensions:
        print(f"\\n{name} metrics:")
        metrics = setup_func()
        metrics.start_server()
        
        # Simulate some activity
        metrics.increment_requests()
        metrics.increment_requests()
        
        # Show JSON output
        json_result = metrics.get_json_metrics()
        print(f"  Requests: {json_result['metrics']['requests_received']}")
        print(f"  Uptime: {json_result['metrics']['uptime_seconds']:.2f}s")
        print(f"  Counters: {len(metrics._custom_counters)}")
        print(f"  Gauges: {len(metrics._custom_gauges)}")

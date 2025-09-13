"""
Connection Manager for WorldStreamer (SRT)

Handles basic network info and returns protocol metadata. The SRT extension
constructs its SRT URI from unified config; URL generation here is not used.
"""

import logging
import socket
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages network connections and IP detection for SRT streaming.
    """
    
    def __init__(self, ip_detection_timeout: float = 5.0):
        """
        Initialize connection manager.
        
        Args:
            ip_detection_timeout: Timeout for IP detection services
        """
        self._ip_detection_timeout = ip_detection_timeout
        self._cached_public_ip = None
        self._cached_local_ip = None
        self._last_ip_check = None
        self._ip_cache_duration = 300.0  # 5 minutes
        
    def get_public_ip(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get public IP address for remote streaming access.
        
        Args:
            force_refresh: Force refresh of cached IP
            
        Returns:
            Public IP address string or None if detection fails
        """
        # Check cache validity
        if not force_refresh and self._is_ip_cache_valid():
            return self._cached_public_ip
        
        try:
            # Try multiple IP detection services for reliability
            ip_services = [
                'https://api.ipify.org',
                'https://icanhazip.com', 
                'https://checkip.amazonaws.com',
                'https://ipecho.net/plain'
            ]
            
            for service in ip_services:
                try:
                    response = requests.get(service, timeout=self._ip_detection_timeout)
                    if response.status_code == 200:
                        public_ip = response.text.strip()
                        if self._validate_ip_address(public_ip):
                            self._cached_public_ip = public_ip
                            self._last_ip_check = datetime.utcnow()
                            logger.info(f"Public IP detected: {public_ip}")
                            return public_ip
                        else:
                            logger.warning(f"Invalid IP format from {service}: {public_ip}")
                            continue
                except Exception as e:
                    logger.debug(f"IP detection service {service} failed: {e}")
                    continue
            
            # All services failed, try fallback method
            fallback_ip = self._get_fallback_ip()
            if fallback_ip:
                self._cached_public_ip = fallback_ip
                self._last_ip_check = datetime.utcnow()
                logger.info(f"Using fallback IP detection: {fallback_ip}")
                return fallback_ip
            
            logger.error("All IP detection methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Public IP detection failed: {e}")
            return None
    
    def get_local_ip(self) -> Optional[str]:
        """
        Get local network IP address.
        
        Returns:
            Local IP address string or None if detection fails
        """
        if self._cached_local_ip:
            return self._cached_local_ip
            
        try:
            # Use socket connection to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to a remote address (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                
                if self._validate_ip_address(local_ip):
                    self._cached_local_ip = local_ip
                    logger.info(f"Local IP detected: {local_ip}")
                    return local_ip
                else:
                    logger.warning(f"Invalid local IP format: {local_ip}")
                    return None
                    
        except Exception as e:
            logger.error(f"Local IP detection failed: {e}")
            return None
    
    # Note: SRT URI construction is handled in StreamingInterface via unified config
    
    def validate_rtmp_connection(self, rtmp_url: str, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Validate RTMP connection by testing the endpoint.
        
        Args:
            rtmp_url: RTMP URL to test
            timeout: Connection timeout in seconds
            
        Returns:
            Dict with connection validation results
        """
        try:
            # Parse RTMP URL to extract host and port
            if not rtmp_url.startswith('rtmp://'):
                return {
                    'success': False,
                    'error': 'Invalid RTMP URL format'
                }
            
            # Remove rtmp:// prefix and parse
            url_parts = rtmp_url[7:].split('/')
            if not url_parts:
                return {
                    'success': False,
                    'error': 'Invalid RTMP URL structure'
                }
            
            host_port = url_parts[0]
            if ':' in host_port:
                host, port_str = host_port.split(':')
                try:
                    port = int(port_str)
                except ValueError:
                    return {
                        'success': False,
                        'error': f'Invalid port in RTMP URL: {port_str}'
                    }
            else:
                host = host_port
                port = 1935  # Default RTMP port
            
            # Test TCP connection to RTMP port
            return self.validate_connection(host, port, timeout)
            
        except Exception as e:
            return {
                'success': False,
                'error': f'RTMP validation error: {e}'
            }
    
    def validate_connection(self, host: str, port: int, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Validate network connection to specified host and port.
        
        Args:
            host: Target host address
            port: Target port number
            timeout: Connection timeout in seconds
            
        Returns:
            Dict with connection validation results
        """
        try:
            start_time = datetime.utcnow()
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex((host, port))
                
                end_time = datetime.utcnow()
                response_time = (end_time - start_time).total_seconds()
                
                if result == 0:
                    return {
                        'success': True,
                        'reachable': True,
                        'response_time': response_time,
                        'host': host,
                        'port': port
                    }
                else:
                    return {
                        'success': True,
                        'reachable': False,
                        'error_code': result,
                        'response_time': response_time,
                        'host': host,
                        'port': port
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'reachable': False,
                'error': str(e),
                'host': host,
                'port': port
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection manager status.
        
        Returns:
            Dict with connection status information
        """
        return {
            'public_ip_cached': self._cached_public_ip,
            'local_ip_cached': self._cached_local_ip,
            'last_ip_check': self._last_ip_check.isoformat() if self._last_ip_check else None,
            'ip_cache_valid': self._is_ip_cache_valid(),
            'ip_detection_timeout': self._ip_detection_timeout,
            'protocol': 'SRT',
            'default_port': 9000
        }
    
    def _generate_client_urls(self, rtmp_port: int, local_ip: Optional[str], 
                            public_ip: Optional[str], stream_key: str) -> Dict[str, str]:
        """
        Generate URLs for client consumption (Agent Adventures platform).
        
        Args:
            rtmp_port: RTMP port
            local_ip: Local network IP
            public_ip: Public IP
            stream_key: Stream key
            
        Returns:
            Dict with client consumption URLs
        """
        client_urls = {}
        
        # HLS URLs (for web browsers)
        if local_ip:
            client_urls['hls_local'] = f"http://{local_ip}:8080/hls/{stream_key}.m3u8"
        
        if public_ip:
            client_urls['hls_public'] = f"http://{public_ip}:8080/hls/{stream_key}.m3u8"
        
        # Direct RTMP URLs (for streaming applications)
        client_urls['rtmp_direct'] = f"rtmp://localhost:{rtmp_port}/live/{stream_key}"
        
        if local_ip:
            client_urls['rtmp_local_network'] = f"rtmp://{local_ip}:{rtmp_port}/live/{stream_key}"
        
        # HTTP FLV URLs (for compatibility)
        if local_ip:
            client_urls['flv_local'] = f"http://{local_ip}:8080/live/{stream_key}.flv"
        
        if public_ip:
            client_urls['flv_public'] = f"http://{public_ip}:8080/live/{stream_key}.flv"
        
        return client_urls
    
    def _generate_platform_examples(self, stream_key: str) -> Dict[str, str]:
        """
        Generate example URLs for popular streaming platforms.
        
        Args:
            stream_key: Stream key to use
            
        Returns:
            Dict with platform URL examples
        """
        return {
            'twitch': f"rtmp://live.twitch.tv/live/{stream_key}",
            'youtube': f"rtmp://a.rtmp.youtube.com/live2/{stream_key}",
            'facebook': f"rtmps://live-api-s.facebook.com:443/rtmp/{stream_key}",
            'local_nginx': f"rtmp://localhost:1935/live/{stream_key}",
            'obs_studio': f"rtmp://localhost:1935/{stream_key}",
            'agent_adventures': f"rtmp://localhost:1935/{stream_key}"
        }
    
    def _validate_ip_address(self, ip: str) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip: IP address string to validate
            
        Returns:
            True if valid IP address format
        """
        try:
            # Basic IP validation
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            
            return True
            
        except (ValueError, AttributeError):
            return False
    
    def _is_ip_cache_valid(self) -> bool:
        """
        Check if IP cache is still valid.
        
        Returns:
            True if cache is valid and within duration
        """
        if not self._last_ip_check or not self._cached_public_ip:
            return False
            
        cache_age = (datetime.utcnow() - self._last_ip_check).total_seconds()
        return cache_age < self._ip_cache_duration
    
    def _get_fallback_ip(self) -> Optional[str]:
        """
        Get IP using fallback method (local IP detection).
        
        Returns:
            Fallback IP address or None
        """
        try:
            # Use local IP as fallback for public IP
            local_ip = self.get_local_ip()
            if local_ip:
                logger.info(f"Using local IP as fallback for public IP: {local_ip}")
                return local_ip
                
            return None
            
        except Exception as e:
            logger.error(f"Fallback IP detection failed: {e}")
            return None
    
    def _get_rtmp_recommendations(self) -> List[str]:
        """
        Get RTMP connection recommendations based on current network setup.
        
        Returns:
            List of RTMP recommendation strings
        """
        recommendations = []
        
        # RTMP compatibility
        recommendations.append("Use OBS Studio or similar RTMP client for testing")
        recommendations.append("Ensure RTMP port (1935) is not blocked by firewall")
        
        # Network considerations
        if self._cached_public_ip:
            recommendations.append("Public IP detected - external RTMP access available")
            recommendations.append("Configure router port forwarding for external access")
        else:
            recommendations.append("No public IP - RTMP streaming limited to local network")
        
        # Performance recommendations
        recommendations.append("Use hardware encoding (NVENC/VA-API) for best performance")
        recommendations.append("Monitor bandwidth usage for stable streaming")
        
        # Integration recommendations
        recommendations.append("Set up RTMP router for multi-platform broadcasting")
        recommendations.append("Consider HLS/web playback conversion for browser access")
        
        return recommendations
    
    def clear_cache(self):
        """Clear cached IP addresses to force refresh."""
        self._cached_public_ip = None
        self._cached_local_ip = None
        self._last_ip_check = None
        logger.info("Connection manager cache cleared")

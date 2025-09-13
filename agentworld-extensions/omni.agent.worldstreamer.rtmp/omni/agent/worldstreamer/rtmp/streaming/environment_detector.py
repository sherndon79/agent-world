"""
Environment Detector for WorldStreamer

Handles LIVESTREAM mode detection and environment configuration.
Focused solely on Isaac Sim streaming environment setup.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EnvironmentDetector:
    """
    Detects and validates Isaac Sim streaming environment configuration.
    
    Handles LIVESTREAM environment variable detection and validates
    Isaac Sim RTMP streaming prerequisites.
    """
    
    def __init__(self):
        """Initialize environment detector."""
        self._detected_mode = None
        self._environment_valid = None
        
    def detect_livestream_mode(self) -> int:
        """
        Detect LIVESTREAM environment configuration.
        
        Returns:
            1: Public networks (requires STUN/TURN)
            2: Private/local networks (simpler setup)  
            0: Not configured (will default to 2)
        """
        if self._detected_mode is not None:
            return self._detected_mode
            
        try:
            livestream_env = os.environ.get('LIVESTREAM', '0')
            mode = int(livestream_env)
            
            if mode == 1:
                logger.info("LIVESTREAM=1 detected: Public network streaming mode")
                self._detected_mode = 1
            elif mode == 2:
                logger.info("LIVESTREAM=2 detected: Local/private network streaming mode")
                self._detected_mode = 2
            else:
                logger.info("LIVESTREAM not configured, defaulting to mode 2 (local)")
                self._detected_mode = 2
                
            return self._detected_mode
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid LIVESTREAM environment value '{livestream_env}': {e}")
            logger.info("Defaulting to mode 2 (local)")
            self._detected_mode = 2
            return self._detected_mode
    
    def validate_isaac_environment(self) -> Dict[str, Any]:
        """
        Validate Isaac Sim environment for RTMP streaming.
        
        Returns:
            Dict with validation results and recommendations
        """
        try:
            validation_result = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'recommendations': [],
                'environment_details': {}
            }
            
            # Check LIVESTREAM configuration
            mode = self.detect_livestream_mode()
            validation_result['environment_details']['livestream_mode'] = mode
            validation_result['environment_details']['livestream_env'] = os.environ.get('LIVESTREAM', 'not set')
            
            # Check for GPU requirements (RTMP encoding benefits from NVENC)
            gpu_info = self._check_gpu_requirements()
            validation_result['environment_details']['gpu_info'] = gpu_info
            
            if not gpu_info['nvenc_available']:
                validation_result['warnings'].append("NVENC not detected - RTMP streaming will use software encoding")
                validation_result['recommendations'].append("Use RTX or other GPU with NVENC support for streaming")
            
            # Check network configuration for public mode
            if mode == 1:
                network_info = self._check_network_configuration()
                validation_result['environment_details']['network_info'] = network_info
                
                if not network_info['stun_turn_configured']:
                    validation_result['warnings'].append("STUN/TURN servers not configured for public streaming")
                    validation_result['recommendations'].append("Configure STUN/TURN servers for external streaming access")
            
            # Check Isaac Sim version compatibility
            isaac_info = self._check_isaac_compatibility()
            validation_result['environment_details']['isaac_info'] = isaac_info
            
            if not isaac_info['compatible']:
                validation_result['errors'].append(f"Isaac Sim version {isaac_info['version']} may not support viewport capture")
                validation_result['valid'] = False
            
            # Overall validation status
            if validation_result['errors']:
                validation_result['valid'] = False
            
            self._environment_valid = validation_result['valid']
            return validation_result
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return {
                'valid': False,
                'errors': [f"Environment validation error: {e}"],
                'warnings': [],
                'recommendations': [],
                'environment_details': {}
            }
    
    def _check_gpu_requirements(self) -> Dict[str, Any]:
        """
        Check GPU requirements for RTMP streaming.
        
        Returns:
            Dict with GPU information and NVENC availability
        """
        try:
            # Basic GPU detection - in real implementation would check NVENC
            gpu_info = {
                'nvenc_available': True,  # Assume available unless detected otherwise
                'gpu_detected': True,
                'gpu_type': 'unknown'
            }
            
            # Check for A100 (known to lack NVENC)
            nvidia_visible_devices = os.environ.get('NVIDIA_VISIBLE_DEVICES', '')
            if 'a100' in nvidia_visible_devices.lower():
                gpu_info['nvenc_available'] = False
                gpu_info['gpu_type'] = 'A100'
                
            return gpu_info
            
        except Exception as e:
            logger.warning(f"GPU requirements check failed: {e}")
            return {
                'nvenc_available': False,
                'gpu_detected': False,
                'gpu_type': 'unknown',
                'error': str(e)
            }
    
    def _check_network_configuration(self) -> Dict[str, Any]:
        """
        Check network configuration for public streaming.
        
        Returns:
            Dict with network configuration status
        """
        try:
            # Check for STUN/TURN configuration
            # In real implementation, would check Isaac Sim settings
            network_info = {
                'stun_turn_configured': False,
                'public_ip_detectable': True,
                'port_accessible': True
            }
            
            # Basic checks for network accessibility
            return network_info
            
        except Exception as e:
            logger.warning(f"Network configuration check failed: {e}")
            return {
                'stun_turn_configured': False,
                'public_ip_detectable': False,
                'port_accessible': False,
                'error': str(e)
            }
    
    def _check_isaac_compatibility(self) -> Dict[str, Any]:
        """
        Check Isaac Sim version compatibility.
        
        Returns:
            Dict with Isaac Sim compatibility information
        """
        try:
            # Basic compatibility check
            isaac_info = {
                'compatible': True,
                'version': 'unknown',
                'viewport_capture_available': True
            }
            
            # In real implementation, would check actual Isaac Sim version
            # and viewport capture extension availability
            
            return isaac_info
            
        except Exception as e:
            logger.warning(f"Isaac Sim compatibility check failed: {e}")
            return {
                'compatible': False,
                'version': 'unknown',
                'viewport_capture_available': False,
                'error': str(e)
            }
    
    def get_recommended_configuration(self) -> Dict[str, Any]:
        """
        Get recommended configuration based on detected environment.
        
        Returns:
            Dict with recommended settings
        """
        try:
            mode = self.detect_livestream_mode()
            
            recommendations = {
                'livestream_mode': mode,
                'recommended_settings': {}
            }
            
            if mode == 1:
                # Public network recommendations
                recommendations['recommended_settings'] = {
                    'allow_relay': True,
                    'stun_servers_required': True,
                    'turn_servers_required': True,
                    'security_considerations': [
                        'Use HTTPS for web client access',
                        'Configure firewall rules for RTMP ports',
                        'Consider VPN access for sensitive environments'
                    ]
                }
            else:
                # Local network recommendations
                recommendations['recommended_settings'] = {
                    'allow_relay': False,
                    'stun_servers_required': False,
                    'turn_servers_required': False,
                    'security_considerations': [
                        'Ensure local network security',
                        'Restrict access to streaming port'
                    ]
                }
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommended configuration: {e}")
            return {
                'livestream_mode': 2,
                'recommended_settings': {},
                'error': str(e)
            }
    
    def is_environment_valid(self) -> Optional[bool]:
        """
        Check if environment has been validated.
        
        Returns:
            True if valid, False if invalid, None if not yet validated
        """
        return self._environment_valid
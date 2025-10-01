"""
Status Tracker for WorldStreamer

Manages streaming state tracking and status synchronization.
Focused solely on streaming status management - no external application logic.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class StreamingState(Enum):
    """Streaming state enumeration."""
    INACTIVE = "inactive"
    STARTING = "starting" 
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"


class StatusTracker:
    """
    Tracks and manages RTMP streaming status and state transitions.
    
    Provides centralized state management for streaming operations
    and synchronization with Isaac Sim streaming state.
    """
    
    def __init__(self):
        """Initialize status tracker."""
        self._current_state = StreamingState.INACTIVE
        self._previous_state = None
        self._state_history = []
        self._last_state_change = None
        self._stream_port = None
        self._stream_urls = {}
        self._error_message = None
        self._start_time = None
        self._stop_time = None
        self._state_metadata = {}
        
    def set_streaming_state(self, new_state: StreamingState, 
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set new streaming state with transition validation.
        
        Args:
            new_state: New streaming state to set
            metadata: Optional metadata for the state change
            
        Returns:
            True if state change was valid and applied
        """
        try:
            # Validate state transition
            if not self._is_valid_transition(self._current_state, new_state):
                logger.warning(f"Invalid state transition: {self._current_state.value} -> {new_state.value}")
                return False
            
            # Record state change
            self._previous_state = self._current_state
            self._current_state = new_state
            self._last_state_change = datetime.utcnow()
            
            # Store metadata
            if metadata:
                self._state_metadata.update(metadata)
            
            # Add to history
            self._state_history.append({
                'state': new_state.value,
                'timestamp': self._last_state_change,
                'previous_state': self._previous_state.value if self._previous_state else None,
                'metadata': metadata or {}
            })
            
            # Limit history size
            if len(self._state_history) > 50:
                self._state_history.pop(0)
            
            # Handle specific state actions
            self._handle_state_change(new_state, metadata)
            
            logger.info(f"Streaming state changed: {self._previous_state.value if self._previous_state else 'None'} -> {new_state.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set streaming state: {e}")
            return False
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """
        Get current streaming status information.
        
        Returns:
            Dict with comprehensive streaming status
        """
        try:
            status = {
                'state': self._current_state.value,
                'previous_state': self._previous_state.value if self._previous_state else None,
                'last_state_change': self._last_state_change.isoformat() if self._last_state_change else None,
                'is_active': self._current_state == StreamingState.ACTIVE,
                'is_error': self._current_state == StreamingState.ERROR,
                'port': self._stream_port,
                'urls': self._stream_urls.copy(),
                'metadata': self._state_metadata.copy()
            }
            
            # Add timing information
            if self._start_time:
                status['start_time'] = self._start_time.isoformat()
                if self._current_state == StreamingState.ACTIVE:
                    uptime = (datetime.utcnow() - self._start_time).total_seconds()
                    status['uptime_seconds'] = uptime
            
            if self._stop_time:
                status['stop_time'] = self._stop_time.isoformat()
            
            # Add error information if in error state
            if self._current_state == StreamingState.ERROR and self._error_message:
                status['error_message'] = self._error_message
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get streaming status: {e}")
            return {
                'state': 'error',
                'error_message': f"Status retrieval failed: {e}",
                'is_active': False,
                'is_error': True
            }
    
    def update_stream_info(self, port: int, urls: Dict[str, Any]):
        """
        Update stream connection information.
        
        Args:
            port: RTMP streaming port
            urls: Dictionary of streaming URLs
        """
        try:
            self._stream_port = port
            self._stream_urls = urls.copy()
            
            # Update metadata
            self._state_metadata.update({
                'port': port,
                'urls_updated': datetime.utcnow().isoformat()
            })
            
            logger.debug(f"Stream info updated: port={port}")
            
        except Exception as e:
            logger.error(f"Failed to update stream info: {e}")
    
    def set_error(self, error_message: str):
        """
        Set streaming to error state with error message.
        
        Args:
            error_message: Error description
        """
        try:
            self._error_message = error_message
            self.set_streaming_state(StreamingState.ERROR, {
                'error_message': error_message,
                'error_timestamp': datetime.utcnow().isoformat()
            })
            
            logger.error(f"Streaming error set: {error_message}")
            
        except Exception as e:
            logger.error(f"Failed to set error state: {e}")
    
    def clear_error(self):
        """Clear error state and message."""
        try:
            self._error_message = None
            if self._current_state == StreamingState.ERROR:
                self.set_streaming_state(StreamingState.INACTIVE, {
                    'error_cleared': datetime.utcnow().isoformat()
                })
            
            logger.info("Streaming error cleared")
            
        except Exception as e:
            logger.error(f"Failed to clear error: {e}")
    
    def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get streaming state history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of state history entries
        """
        try:
            # Return most recent entries first
            history = self._state_history[-limit:] if limit > 0 else self._state_history[:]
            return list(reversed(history))
            
        except Exception as e:
            logger.error(f"Failed to get state history: {e}")
            return []
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get status tracker health information.
        
        Returns:
            Dict with health status
        """
        return {
            'tracker_functional': True,
            'current_state': self._current_state.value,
            'has_error': self._current_state == StreamingState.ERROR,
            'error_message': self._error_message,
            'history_entries': len(self._state_history),
            'last_activity': self._last_state_change.isoformat() if self._last_state_change else None
        }
    
    def _is_valid_transition(self, current: StreamingState, new: StreamingState) -> bool:
        """
        Validate state transition rules.
        
        Args:
            current: Current streaming state
            new: Proposed new state
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            StreamingState.INACTIVE: [StreamingState.STARTING, StreamingState.ERROR],
            StreamingState.STARTING: [StreamingState.ACTIVE, StreamingState.ERROR, StreamingState.INACTIVE],
            StreamingState.ACTIVE: [StreamingState.STOPPING, StreamingState.ERROR],
            StreamingState.STOPPING: [StreamingState.INACTIVE, StreamingState.ERROR],
            StreamingState.ERROR: [StreamingState.INACTIVE, StreamingState.STARTING]
        }
        
        # Allow staying in same state
        if current == new:
            return True
        
        # Check if transition is allowed
        allowed_transitions = valid_transitions.get(current, [])
        return new in allowed_transitions
    
    def _handle_state_change(self, new_state: StreamingState, metadata: Optional[Dict[str, Any]]):
        """
        Handle actions for specific state changes.
        
        Args:
            new_state: New state that was set
            metadata: Metadata for the state change
        """
        try:
            if new_state == StreamingState.STARTING:
                self._start_time = datetime.utcnow()
                self._stop_time = None
                self._error_message = None
                
            elif new_state == StreamingState.ACTIVE:
                # Ensure start time is set
                if not self._start_time:
                    self._start_time = datetime.utcnow()
                    
            elif new_state == StreamingState.STOPPING:
                # Keep start time but prepare for stop
                pass
                
            elif new_state == StreamingState.INACTIVE:
                self._stop_time = datetime.utcnow()
                # Keep error message if transitioning from error state
                if self._previous_state != StreamingState.ERROR:
                    self._error_message = None
                    
            elif new_state == StreamingState.ERROR:
                self._stop_time = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
    
    def reset(self):
        """Reset status tracker to initial state."""
        try:
            self._current_state = StreamingState.INACTIVE
            self._previous_state = None
            self._state_history.clear()
            self._last_state_change = None
            self._stream_port = None
            self._stream_urls.clear()
            self._error_message = None
            self._start_time = None
            self._stop_time = None
            self._state_metadata.clear()
            
            logger.info("Status tracker reset")
            
        except Exception as e:
            logger.error(f"Failed to reset status tracker: {e}")
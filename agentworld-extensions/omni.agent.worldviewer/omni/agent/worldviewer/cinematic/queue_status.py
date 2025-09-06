"""
Thread-safe queue status management for WorldViewer cinematic system.

This module provides atomic status operations to prevent timing issues
and race conditions in queue state reporting and transitions.
"""

import threading
import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class QueueStatus:
    """Thread-safe status container with atomic operations"""
    
    def __init__(self):
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._state = "idle"
        self._active_movement = None
        self._queue_size = 0
        self._timestamp = time.time()
        self._paused_movement = None
        self._queue_start_time = 0.0
        
    def get_status(self) -> Dict[str, Any]:
        """Get current status atomically"""
        with self._lock:
            return {
                'state': self._state,
                'active_movement': self._active_movement,
                'queue_size': self._queue_size,
                'timestamp': self._timestamp,
                'paused_movement': self._paused_movement,
                'queue_start_time': self._queue_start_time
            }
    
    def get_state(self) -> str:
        """Get current state atomically"""
        with self._lock:
            return self._state
    
    def set_state(self, new_state: str) -> bool:
        """Set queue state atomically"""
        with self._lock:
            old_state = self._state
            self._state = new_state
            self._timestamp = time.time()
            logger.debug(f"Queue state transition: {old_state} -> {new_state}")
            return True
    
    def set_active_movement(self, movement) -> None:
        """Set active movement atomically"""
        with self._lock:
            self._active_movement = movement
            self._timestamp = time.time()
    
    def get_active_movement(self):
        """Get active movement atomically"""
        with self._lock:
            return self._active_movement
    
    def set_paused_movement(self, movement) -> None:
        """Set paused movement atomically"""
        with self._lock:
            self._paused_movement = movement
            self._timestamp = time.time()
    
    def get_paused_movement(self):
        """Get paused movement atomically"""
        with self._lock:
            return self._paused_movement
    
    def set_queue_size(self, size: int) -> None:
        """Set queue size atomically"""
        with self._lock:
            self._queue_size = size
            self._timestamp = time.time()
    
    def get_queue_size(self) -> int:
        """Get queue size atomically"""
        with self._lock:
            return self._queue_size
    
    def set_queue_start_time(self, start_time: float) -> None:
        """Set queue start time atomically"""
        with self._lock:
            self._queue_start_time = start_time
            self._timestamp = time.time()
    
    def update_multiple(self, **kwargs) -> None:
        """Update multiple status fields atomically"""
        with self._lock:
            if 'state' in kwargs:
                old_state = self._state
                self._state = kwargs['state']
                logger.debug(f"Queue state updated: {old_state} -> {self._state}")
            if 'active_movement' in kwargs:
                self._active_movement = kwargs['active_movement']
            if 'queue_size' in kwargs:
                self._queue_size = kwargs['queue_size']
            if 'paused_movement' in kwargs:
                self._paused_movement = kwargs['paused_movement']
            if 'queue_start_time' in kwargs:
                self._queue_start_time = kwargs['queue_start_time']
            
            self._timestamp = time.time()


class MovementTransition:
    """Manages transitions between queue states with validation"""
    
    def __init__(self, queue_status: QueueStatus):
        self.status = queue_status
        self._transition_lock = threading.Lock()
        
        # Valid state transitions
        self.VALID_TRANSITIONS = {
            'idle': ['running', 'stopped', 'pending'],
            'running': ['paused', 'stopped', 'idle', 'pending'],
            'paused': ['running', 'stopped', 'idle'],
            'stopped': ['idle', 'running', 'pending'],
            'pending': ['running', 'stopped', 'idle'],
            'error': ['idle', 'stopped']
        }
    
    def transition_to_state(self, new_state: str) -> bool:
        """Safely transition to new queue state with validation"""
        with self._transition_lock:
            current_state = self.status.get_state()
            
            if self._validate_transition(current_state, new_state):
                self.status.set_state(new_state)
                logger.info(f"Queue state transition: {current_state} -> {new_state}")
                return True
            else:
                logger.warning(f"Invalid queue state transition: {current_state} -> {new_state}")
                return False
    
    def _validate_transition(self, from_state: str, to_state: str) -> bool:
        """Validate if state transition is allowed"""
        valid_targets = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets
    
    def get_valid_transitions(self, from_state: Optional[str] = None) -> list:
        """Get valid target states from current or specified state"""
        if from_state is None:
            from_state = self.status.get_state()
        
        return self.VALID_TRANSITIONS.get(from_state, [])
    
    def can_transition_to(self, new_state: str) -> bool:
        """Check if transition to new state is valid without executing it"""
        current_state = self.status.get_state()
        return self._validate_transition(current_state, new_state)
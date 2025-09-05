"""
Queue management for WorldViewer cinematic camera movements.

This module handles all queue-related functionality:
- Queue state management (idle, running, paused, stopped)  
- Movement queue processing and transitions
- Queue control operations (play/pause/stop)
- Queue status reporting and metrics
- Movement scheduling and timing
"""

import logging
import time
from collections import deque
from typing import Dict, List, Optional, Tuple, Deque
from .movement_state import MovementState
from .duration_calculator import calculate_distance, calculate_duration


logger = logging.getLogger(__name__)


class QueueManager:
    """Manages movement queue state, processing, and timing"""
    
    # Constants
    MAX_QUEUE_SIZE = 10  # Maximum number of movements (1 active + 9 queued)
    MOVEMENT_TRANSITION_DELAY = 0.2  # Small delay between movements for capture sync
    
    def __init__(self):
        # Queue state
        self.queue_state = "idle"  # idle, running, paused, stopped
        self.active_movement: Optional[MovementState] = None
        self.movement_queue: Deque[Tuple[str, str, Dict]] = deque()  # (movement_id, operation, params)
        self.paused_movement: Optional[MovementState] = None
        
        # Timing and metrics
        self.queue_start_time = 0.0
        self.total_queue_duration = 0.0
        
        logger.info("QueueManager initialized")
    
    def play_queue(self) -> Dict:
        """Start/resume queue processing"""
        try:
            if self.queue_state == "running":
                return {
                    'success': True,
                    'message': 'Queue is already running',
                    'queue_state': self.queue_state
                }
            
            if self.queue_state == "paused":
                # Resume from paused state
                if self.paused_movement:
                    self.active_movement = self.paused_movement
                    self.paused_movement = None
                    logger.info("Resuming paused movement")
                
                self.queue_state = "running"
                return {
                    'success': True, 
                    'message': 'Queue resumed from pause',
                    'queue_state': self.queue_state
                }
            
            elif self.queue_state in ["idle", "stopped"]:
                # Start fresh queue processing
                if not self.movement_queue and not self.active_movement:
                    return {
                        'success': False,
                        'error': 'No movements in queue to start',
                        'queue_state': self.queue_state
                    }
                
                self.queue_state = "running"
                self.queue_start_time = time.time()
                
                logger.info(f"Queue started - {len(self.movement_queue)} movements queued")
                return {
                    'success': True,
                    'message': f'Queue started with {len(self.movement_queue)} movements',
                    'queue_state': self.queue_state
                }
            
            else:
                return {
                    'success': False,
                    'error': f'Cannot start queue from state: {self.queue_state}',
                    'queue_state': self.queue_state
                }
                
        except Exception as e:
            logger.error(f"Error starting queue: {e}")
            return {
                'success': False,
                'error': f'Failed to start queue: {str(e)}',
                'queue_state': self.queue_state
            }
    
    def pause_queue(self) -> Dict:
        """Pause queue processing (current movement continues, no new movements start)"""
        try:
            if self.queue_state != "running":
                return {
                    'success': False,
                    'error': f'Cannot pause queue from state: {self.queue_state}',
                    'queue_state': self.queue_state
                }
            
            # Preserve current active movement for resume
            if self.active_movement:
                self.paused_movement = self.active_movement
                logger.info(f"Pausing queue with active movement: {self.active_movement.movement_id}")
            
            self.queue_state = "paused"
            
            return {
                'success': True,
                'message': 'Queue paused - current movement continues, no new movements will start',
                'queue_state': self.queue_state,
                'active_movement_continues': self.active_movement is not None
            }
            
        except Exception as e:
            logger.error(f"Error pausing queue: {e}")
            return {
                'success': False,
                'error': f'Failed to pause queue: {str(e)}',
                'queue_state': self.queue_state
            }
    
    def stop_queue(self) -> Dict:
        """Stop and clear entire queue"""
        try:
            # Clear all queued movements
            queue_size_before = len(self.movement_queue)
            self.movement_queue.clear()
            
            # Clear active movement
            active_movement_id = self.active_movement.movement_id if self.active_movement else None
            self.active_movement = None
            self.paused_movement = None
            
            self.queue_state = "stopped"
            
            logger.info(f"Queue stopped and cleared - removed {queue_size_before} queued movements")
            
            return {
                'success': True,
                'message': f'Queue stopped and cleared ({queue_size_before} movements removed)',
                'queue_state': self.queue_state,
                'cleared_active_movement': active_movement_id,
                'cleared_queue_size': queue_size_before
            }
            
        except Exception as e:
            logger.error(f"Error stopping queue: {e}")
            return {
                'success': False,
                'error': f'Failed to stop queue: {str(e)}',
                'queue_state': self.queue_state
            }
    
    def add_movement(self, movement_id: str, operation: str, params: Dict) -> Dict:
        """Add movement to queue"""
        try:
            # Check queue size limit
            if len(self.movement_queue) >= self.MAX_QUEUE_SIZE:
                return {
                    'success': False,
                    'error': f'Queue is full (max {self.MAX_QUEUE_SIZE} movements)',
                    'queue_size': len(self.movement_queue)
                }
            
            # Add to queue
            self.movement_queue.append((movement_id, operation, params))
            
            logger.info(f"Added movement to queue: {movement_id} ({operation})")
            
            return {
                'success': True,
                'message': f'Movement added to queue: {movement_id}',
                'queue_size': len(self.movement_queue),
                'position': len(self.movement_queue)
            }
            
        except Exception as e:
            logger.error(f"Error adding movement to queue: {e}")
            return {
                'success': False,
                'error': f'Failed to add movement to queue: {str(e)}'
            }
    
    def remove_movement(self, movement_id: str) -> Dict:
        """Remove movement from queue by ID"""
        try:
            # Search queue for movement
            for i, (queued_id, operation, params) in enumerate(self.movement_queue):
                if queued_id == movement_id:
                    # Remove from queue
                    self.movement_queue.remove((queued_id, operation, params))
                    
                    logger.info(f"Removed movement from queue: {movement_id}")
                    return {
                        'success': True,
                        'message': f'Movement removed from queue: {movement_id}',
                        'queue_size': len(self.movement_queue)
                    }
            
            # Check if it's the active movement
            if self.active_movement and self.active_movement.movement_id == movement_id:
                return {
                    'success': False,
                    'error': f'Cannot remove active movement: {movement_id}. Use stop_movement() instead.'
                }
            
            return {
                'success': False,
                'error': f'Movement not found in queue: {movement_id}',
                'queue_size': len(self.movement_queue)
            }
            
        except Exception as e:
            logger.error(f"Error removing movement from queue: {e}")
            return {
                'success': False,
                'error': f'Failed to remove movement from queue: {str(e)}'
            }
    
    def get_next_movement(self) -> Optional[Tuple[str, str, Dict]]:
        """Get next movement from queue"""
        try:
            if self.movement_queue:
                return self.movement_queue.popleft()
            return None
        except Exception as e:
            logger.error(f"Error getting next movement: {e}")
            return None
    
    def get_queue_status(self) -> Dict:
        """Get comprehensive queue status"""
        try:
            # Get actual queue state
            actual_state = self._get_actual_queue_state()
            
            # Initialize response
            response = {
                'success': True,
                'queue_state': actual_state,
                'timestamp': time.time()
            }
            
            # Get active shot info
            active_shots = []
            if self.active_movement:
                elapsed = time.time() - self.active_movement.start_time
                progress = min(elapsed / self.active_movement.duration, 1.0)
                remaining_time = max(0, self.active_movement.duration - elapsed)
                
                active_shot = {
                    'movement_id': self.active_movement.movement_id,
                    'operation': self.active_movement.operation,
                    'progress': progress,
                    'remaining_time': remaining_time,
                    'total_duration': self.active_movement.duration,
                    'execution': self.active_movement.params.get('execution', 'auto'),
                    'params': self._extract_display_params(self.active_movement.params)
                }
                active_shots.append(active_shot)
            
            response['active_shots'] = active_shots
            response['active_count'] = len(active_shots)
            
            # Get queued shots info
            queued_shots = []
            estimated_start_time = active_shots[0]['remaining_time'] if active_shots else 0
            
            for i, (movement_id, operation, params) in enumerate(self.movement_queue):
                # Calculate duration for display
                estimated_duration = self._estimate_movement_duration(params)
                
                queued_shot = {
                    'movement_id': movement_id,
                    'operation': operation,
                    'estimated_duration': estimated_duration,
                    'estimated_start_time': estimated_start_time,
                    'execution': params.get('execution', 'auto'),
                    'position': i + 1,
                    'params': self._extract_display_params(params)
                }
                queued_shots.append(queued_shot)
                estimated_start_time += estimated_duration
            
            response['queued_shots'] = queued_shots
            response['queued_count'] = len(queued_shots)
            
            # Calculate timing metrics
            total_duration = sum(shot.get('estimated_duration', 0) for shot in queued_shots)
            if active_shots:
                total_duration += active_shots[0]['remaining_time']
            
            response['total_duration'] = total_duration
            response['estimated_remaining'] = total_duration
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {
                'success': False,
                'error': f'Failed to get queue status: {str(e)}',
                'queue_state': 'error'
            }
    
    def _get_actual_queue_state(self) -> str:
        """Determine actual queue state from current conditions"""
        try:
            # Check if we have any active or queued movements
            has_active = self.active_movement is not None
            has_queued = len(self.movement_queue) > 0
            
            if self.queue_state == "running":
                if not has_active and not has_queued:
                    # Queue completed - transition to idle
                    return "idle"
                elif has_active or has_queued:
                    return "running"
                else:
                    return "idle"
            
            elif self.queue_state == "paused":
                if not has_active and not has_queued:
                    return "idle"
                else:
                    return "paused"
            
            elif self.queue_state == "stopped":
                return "stopped"
            
            elif self.queue_state == "idle":
                if has_active or has_queued:
                    return "pending"  # Movements available but not started
                else:
                    return "idle"
            
            else:
                return self.queue_state
                
        except Exception as e:
            logger.error(f"Error determining queue state: {e}")
            return "error"
    
    def _estimate_movement_duration(self, params: Dict) -> float:
        """Estimate duration for a movement based on parameters"""
        try:
            # Check if duration is explicitly provided
            if 'duration' in params:
                return float(params['duration'])
            
            # Calculate based on positions and speed
            if 'start_position' in params and 'end_position' in params:
                start_pos = params['start_position']
                end_pos = params['end_position']
                speed = params.get('speed', 5.0)  # Default speed
                
                distance = calculate_distance(start_pos, end_pos)
                duration = calculate_duration(start_pos, end_pos, speed, None)
                return duration
            
            # Default fallback
            return 3.0
            
        except Exception as e:
            logger.error(f"Error estimating movement duration: {e}")
            return 3.0  # Fallback duration
    
    def _extract_display_params(self, params: Dict) -> Dict:
        """Extract key parameters for display"""
        display_params = {}
        
        # Extract key parameters for UI display
        if 'start_position' in params:
            display_params['start_position'] = params['start_position']
        if 'end_position' in params:  
            display_params['end_position'] = params['end_position']
        if 'start_target' in params:
            display_params['start_target'] = params['start_target']
        if 'end_target' in params:
            display_params['end_target'] = params['end_target']
        if 'speed' in params:
            display_params['speed'] = params['speed']
        if 'easing_type' in params:
            display_params['easing_type'] = params['easing_type']
        if 'execution' in params:
            display_params['execution'] = params['execution']
            
        return display_params
    
    def clear_queue(self) -> Dict:
        """Clear all queued movements but keep active movement"""
        try:
            queue_size = len(self.movement_queue)
            self.movement_queue.clear()
            
            logger.info(f"Cleared {queue_size} movements from queue")
            
            return {
                'success': True,
                'message': f'Cleared {queue_size} movements from queue',
                'cleared_count': queue_size,
                'active_movement_preserved': self.active_movement is not None
            }
            
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return {
                'success': False,
                'error': f'Failed to clear queue: {str(e)}'
            }
    
    def get_queue_metrics(self) -> Dict:
        """Get queue performance metrics"""
        try:
            return {
                'queue_size': len(self.movement_queue),
                'max_queue_size': self.MAX_QUEUE_SIZE,
                'queue_utilization': len(self.movement_queue) / self.MAX_QUEUE_SIZE,
                'has_active_movement': self.active_movement is not None,
                'queue_state': self.queue_state,
                'queue_start_time': self.queue_start_time,
                'total_queue_duration': self.total_queue_duration
            }
        except Exception as e:
            logger.error(f"Error getting queue metrics: {e}")
            return {'error': str(e)}


class QueueStateManager:
    """Handles queue state transitions and validation"""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        'idle': ['running', 'stopped'],
        'running': ['paused', 'stopped', 'idle'],
        'paused': ['running', 'stopped', 'idle'],
        'stopped': ['idle', 'running'],
        'error': ['idle', 'stopped']
    }
    
    def __init__(self, queue_manager: QueueManager):
        self.queue_manager = queue_manager
        
    def transition_to_state(self, new_state: str) -> bool:
        """Safely transition to new queue state"""
        try:
            current_state = self.queue_manager.queue_state
            
            if self.validate_state_transition(current_state, new_state):
                old_state = self.queue_manager.queue_state
                self.queue_manager.queue_state = new_state
                
                logger.info(f"Queue state transition: {old_state} -> {new_state}")
                return True
            else:
                logger.warning(f"Invalid queue state transition: {current_state} -> {new_state}")
                return False
                
        except Exception as e:
            logger.error(f"Error transitioning queue state: {e}")
            return False
    
    def validate_state_transition(self, from_state: str, to_state: str) -> bool:
        """Check if state transition is valid"""
        valid_targets = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets
    
    def get_valid_transitions(self, from_state: str) -> List[str]:
        """Get list of valid target states from current state"""
        return self.VALID_TRANSITIONS.get(from_state, [])
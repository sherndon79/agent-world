"""
XR WorldViewer Synchronous Cinematic Camera Controller

Provides smooth, interpolated camera movements using Isaac Sim's timer system.
No asyncio - all operations run on the main thread via timers.
"""

import logging
import math
import time
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import deque
from enum import Enum

import omni.usd
import omni.kit.app
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf, UsdGeom

# Import duration calculation utilities
from .cinematic.duration_calculator import calculate_distance, calculate_duration, validate_speed_parameters

# Import modular cinematic components
from .cinematic import (
    MovementState,
    EasingType,
    ShotType,
    FramingStyle,
    EasingFunctions,
    get_style_config,
    get_available_styles,
    rotation_to_target,
    CINEMATIC_STYLES,
    QueueManager,
    QueueStateManager
)

# Keyframe generation factory
from .cinematic.keyframe_generators import KeyframeGeneratorFactory

from .camera_controller import CameraController


logger = logging.getLogger(__name__)


class SynchronousCinematicController:
    """Synchronous cinematic camera controller using Isaac Sim timers"""
    
    # Configuration constants
    DEFAULT_FPS = 30
    MAX_DURATION = 60.0  # Maximum movement duration in seconds
    MIN_DURATION = 0.1   # Minimum movement duration in seconds
    MAX_QUEUE_SIZE = 10  # Maximum number of movements (1 active + 9 queued)
    MOVEMENT_TRANSITION_DELAY = 0.2  # Small delay between movements for capture sync
    SMOOTH_TRANSITION_THRESHOLD = 1.0  # Distance threshold for smooth transition
    
    def __init__(self, camera_controller: CameraController):
        self.camera_controller = camera_controller
        
        # Initialize modular queue manager
        self.queue_manager = QueueManager()
        self.queue_state_manager = QueueStateManager(self.queue_manager)
        
        # Initialize keyframe generator factory
        self.keyframe_generator_factory = KeyframeGeneratorFactory(camera_controller)
        
        # System attributes
        self.movement_timer = None
        self.fps = self.DEFAULT_FPS
        self.frame_duration = 1.0 / self.fps  # Time per frame in seconds
        
        # Easing function mapping
        self.easing_functions = {
            EasingType.LINEAR: EasingFunctions.linear,
            EasingType.EASE_IN: EasingFunctions.ease_in,
            EasingType.EASE_OUT: EasingFunctions.ease_out,
            EasingType.EASE_IN_OUT: EasingFunctions.ease_in_out,
            EasingType.BOUNCE: EasingFunctions.bounce,
            EasingType.ELASTIC: EasingFunctions.elastic
        }
        
        self._start_movement_timer()
    
    def _start_movement_timer(self):
        """Start the timer that processes movement frames"""
        try:
            def process_movements(dt):
                """Process all active movements"""
                self._update_movements()
            
            # Create timer to process movements at target FPS
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self.movement_timer = update_stream.create_subscription_to_pop(
                process_movements, name="cinematic_movement_timer"
            )
            
            logger.info(f"Cinematic movement timer started at {self.fps} FPS")
            
        except Exception as e:
            logger.error(f"Failed to start movement timer: {e}")
    
    def stop_movement_timer(self):
        """Stop the movement timer"""
        if self.movement_timer:
            self.movement_timer.unsubscribe()
            self.movement_timer = None
    
    def _update_movements(self):
        """Update the single active movement (sequential processing)"""
        if not self.queue_manager.active_movement:
            return  # No active movement
        
        # Check if queue is paused - pause execution but keep active movement
        if self.queue_manager.queue_state == 'paused':
            return  # Skip execution while paused
            
        current_time = time.time()
        movement = self.queue_manager.active_movement
        
        try:
            # Check if movement is complete
            elapsed = current_time - movement.start_time
            if elapsed >= movement.duration:
                # Complete the movement with final frame
                self._apply_final_frame(movement)
                logger.info(f"Completed cinematic movement: {movement.movement_id}")
                
                # Clear active movement and start next queued movement
                self.queue_manager.active_movement = None
                self._start_next_queued_movement()
                return
            
            # Calculate current frame
            progress = elapsed / movement.duration
            frame_index = int(progress * len(movement.keyframes))
            frame_index = min(frame_index, len(movement.keyframes) - 1)
            
            # Apply current frame
            if frame_index < len(movement.keyframes):
                frame = movement.keyframes[frame_index]
                self.camera_controller.set_position(
                    frame['position'], 
                    frame.get('target')
                )
                movement.current_frame = frame_index
            
        except Exception as e:
            logger.error(f"Error updating movement {movement.movement_id}: {e}")
            # Clear failed movement and try next in queue
            self.queue_manager.active_movement = None
            self._start_next_queued_movement()
    
    def _apply_final_frame(self, movement: MovementState):
        """Apply the final frame of a movement"""
        if movement.keyframes:
            final_frame = movement.keyframes[-1]
            self.camera_controller.set_position(
                final_frame['position'],
                final_frame.get('target')
            )
    
    def _start_next_queued_movement(self, manual_play=False):
        """Start the next movement in the queue with smooth transition"""
        if not self.queue_manager.movement_queue:
            # No queued movements - set state appropriately
            if self.queue_manager.queue_state == 'running':
                self.queue_manager.transition_manager.transition_to_state('idle')
            return
        
        # Don't start next movement if queue is stopped
        if self.queue_manager.queue_state == 'stopped':
            logger.info(f"Queue is stopped, not starting next movement")
            return
        
        # Get next movement from queue
        next_movement_data = self.queue_manager.movement_queue.popleft()
        movement_id, operation, params = next_movement_data
        
        # Check execution mode
        execution_mode = params.get('execution_mode', 'auto')
        
        if execution_mode == 'manual' and not manual_play:
            # Put movement back at front of queue and wait for manual play
            self.queue_manager.movement_queue.appendleft((movement_id, operation, params))
            logger.info(f"Next movement {movement_id} is in manual mode - waiting for play command")
            # Transition to pending state for manual trigger
            if self.queue_manager.transition_manager.transition_to_state('pending'):
                logger.info(f"Queue transitioned to pending state - waiting for manual trigger")
            else:
                # Fallback to direct state change if transition validation fails
                self.queue_manager.status.set_state('pending')
                logger.info(f"Queue set to pending state for manual movement (direct)")
            return
        elif execution_mode == 'manual' and manual_play:
            # Manual movement triggered by play button - execute it
            logger.info(f"Starting manual movement via play button: {movement_id} ({operation})")
            # Ensure we're in running state for manual execution
            current_state = self.queue_manager.queue_state
            if current_state != 'running':
                if self.queue_manager.transition_manager.transition_to_state('running'):
                    logger.info(f"Queue transitioned to running state for manual execution")
            else:
                logger.debug(f"Queue already in running state, no transition needed")
        elif self.queue_manager.queue_state == 'paused' and execution_mode == 'auto':
            # If we're paused but next movement is auto, transition to running
            logger.info(f"Auto movement following manual - transitioning from paused to running")
            if self.queue_manager.transition_manager.transition_to_state('running'):
                logger.info(f"Queue transitioned to running for auto movement {movement_id}")
            else:
                logger.warning(f"Failed to transition to running state for auto movement {movement_id}")
                return
        
        # Add smooth transition from current camera position if needed
        params = self._add_smooth_transition(params)
        
        # Start the movement immediately
        self._start_movement_immediately(movement_id, operation, params)
    
    def _add_smooth_transition(self, params: Dict) -> Dict:
        """Add smooth transition from current camera position to movement start"""
        try:
            # Get current camera status
            current_status = self.camera_controller.get_status()
            if not current_status.get('connected') or not current_status.get('position'):
                return params  # Can't get current position, proceed without transition
            
            current_pos = current_status['position']
            current_target = current_status.get('target')
            
            # If the movement has a start_position, ensure smooth transition
            if 'start_position' in params:
                start_pos = params['start_position']
                
                # Calculate distance to see if transition is needed
                distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(current_pos, start_pos)))
                
                # If camera is far from start position, update start position to current position
                if distance > self.SMOOTH_TRANSITION_THRESHOLD:
                    logger.info(f"Adding smooth transition from {current_pos} to {start_pos}")
                    params = params.copy()
                    params['start_position'] = current_pos
                    if current_target:
                        params['start_target'] = current_target
            
            return params
            
        except Exception as e:
            logger.warning(f"Failed to add smooth transition: {e}")
            return params
    
    def start_movement(self, movement_id: str, operation: str, params: Dict):
        """Start a new cinematic movement (sequential queuing system)"""
        try:
            # Validate duration/speed parameters 
            duration = params.get('duration')
            speed = params.get('speed')
            
            # If neither duration nor speed provided, use default duration
            if duration is None and speed is None:
                duration = 3.0
                params['duration'] = duration
            
            # If duration is provided, validate it
            if duration is not None:
                if not (self.MIN_DURATION <= duration <= self.MAX_DURATION):
                    raise ValueError(f"Duration must be between {self.MIN_DURATION} and {self.MAX_DURATION} seconds")
            
            # Check if queue is stopped
            if self.queue_manager.queue_state == 'stopped':
                # Reset to idle when new movements are added to stopped queue
                self.queue_manager.transition_manager.transition_to_state('idle')
            
            # Check queue capacity (prevent infinite queueing)
            total_queued = len(self.queue_manager.movement_queue) + (1 if self.queue_manager.active_movement else 0)
            if total_queued >= self.MAX_QUEUE_SIZE:
                raise ValueError(f"Movement queue full ({total_queued}/{self.MAX_QUEUE_SIZE}). Too many movements queued. Use 'stop_movement' API to cancel queued movements.")
            
            # Get execution mode (auto by default)
            execution_mode = params.get('execution_mode', 'auto')
            
            # Manual movements are always queued and require explicit play command
            if execution_mode == 'manual':
                self.queue_manager.add_movement(movement_id, operation, params)
                logger.info(f"Queueing manual movement: {movement_id} ({operation}). Position in queue: {len(self.queue_manager.movement_queue)}")
                    
            # Auto movements: start immediately only if no active movement, no queue, and not paused/stopped
            elif self.queue_manager.active_movement is None and len(self.queue_manager.movement_queue) == 0 and self.queue_manager.queue_state not in ['paused', 'stopped']:
                logger.info(f"Starting movement immediately: {movement_id} ({operation}) - auto mode")
                self.queue_manager.transition_manager.transition_to_state('running')
                self._start_movement_immediately(movement_id, operation, params)
            else:
                # Queue auto movement for later
                self.queue_manager.add_movement(movement_id, operation, params)
                logger.info(f"Queueing auto movement: {movement_id} ({operation}). Position in queue: {len(self.queue_manager.movement_queue)}")
                
                # Set queue to running state if idle (for auto movements)
                # Only transition to running if first movement in queue is not manual
                if self.queue_manager.queue_state == 'idle':
                    # Check if first movement in queue is manual
                    if self.queue_manager.movement_queue:
                        first_movement_id, first_operation, first_params = self.queue_manager.movement_queue[0]
                        first_execution_mode = first_params.get('execution_mode', 'auto')
                        if first_execution_mode != 'manual':
                            self.queue_manager.transition_manager.transition_to_state('running')
                        else:
                            logger.info(f"Queue remains in idle state - first movement is manual")
                    else:
                        # Empty queue, safe to transition to running
                        self.queue_manager.transition_manager.transition_to_state('running')
            
        except Exception as e:
            logger.error(f"Failed to start movement {movement_id}: {e}")
            raise  # Re-raise for API error handling
    
    def _start_movement_immediately(self, movement_id: str, operation: str, params: Dict):
        """Start a movement immediately (no queue checks)"""
        try:
            # Generate keyframes using factory pattern
            keyframes = self.keyframe_generator_factory.generate_keyframes(operation, params)
            
            # Create movement state
            movement = MovementState(
                movement_id=movement_id,
                operation=operation,
                start_time=time.time(),
                duration=params.get('duration', 3.0),
                keyframes=keyframes,
                current_frame=0,
                status='active',
                params=params
            )
            
            # Set as the single active movement
            self.queue_manager.active_movement = movement
            logger.info(f"Started cinematic movement: {movement_id} ({operation})")
            
        except Exception as e:
            logger.error(f"Failed to start movement immediately {movement_id}: {e}")
            raise
    
    def stop_movement(self) -> Dict:
        """Stop all camera movement and return current position details"""
        stopped_count = 0
        stopped_movement_id = None
        
        # Get current camera position before stopping
        current_position = None
        current_target = None
        try:
            camera_status = self.camera_controller.get_status()
            if camera_status.get('connected'):
                current_position = camera_status.get('position')
                current_target = camera_status.get('target')
        except Exception as e:
            logger.warning(f"Could not get current camera position: {e}")
        
        # Stop active movement
        if self.queue_manager.active_movement:
            stopped_movement_id = self.queue_manager.active_movement.movement_id
            operation = self.queue_manager.active_movement.operation
            progress = 0.0
            
            # Calculate progress if possible
            try:
                elapsed = time.time() - self.queue_manager.active_movement.start_time
                progress = min(elapsed / self.queue_manager.active_movement.duration, 1.0)
            except (AttributeError, ZeroDivisionError):
                pass
            
            logger.info(f"Stopping active movement: {stopped_movement_id} ({operation}) at {progress*100:.1f}% progress")
            self.queue_manager.active_movement = None
            stopped_count += 1
        
        # Clear entire queue
        if self.queue_manager.movement_queue:
            queue_count = len(self.queue_manager.movement_queue)
            logger.info(f"Clearing entire queue: {queue_count} movements")
            self.queue_manager.movement_queue.clear()
            stopped_count += queue_count
        
        # Update queue state to stopped
        self.queue_manager.transition_manager.transition_to_state('stopped')
        
        # Build response with position details
        response = {
            'success': True,
            'stopped_count': stopped_count,
            'message': f'Stopped all camera movement. Total stopped: {stopped_count} movements.'
        }
        
        # Add position information if available
        if current_position:
            response['stopped_at_position'] = current_position
        if current_target:
            response['stopped_at_target'] = current_target
        
        # Add interrupted movement details if there was one
        if stopped_movement_id:
            response['interrupted_movement_id'] = stopped_movement_id
            response['interrupted_operation'] = operation
            response['progress_when_stopped'] = f"{progress*100:.1f}%"
            response['message'] += f' Interrupted {operation} movement {stopped_movement_id} at {progress*100:.1f}% completion.'
        
        if stopped_count > 0:
            logger.info(f"Camera stopped at position {current_position}, looking at {current_target}")
        else:
            response['message'] = 'No active movements to stop. Camera already idle.'
        
        return response
    
    def get_movement_status(self, movement_id: str) -> Dict:
        """Get status of an active or queued movement"""
        # Check active movement
        if self.queue_manager.active_movement and self.queue_manager.active_movement.movement_id == movement_id:
            movement = self.queue_manager.active_movement
            elapsed = time.time() - movement.start_time
            progress = min(elapsed / movement.duration, 1.0)
            
            return {
                'success': True,
                'movement_id': movement_id,
                'operation': movement.operation,
                'status': 'active',
                'progress': progress,
                'elapsed_time': elapsed,
                'total_duration': movement.duration,
                'queue_position': 0  # Active movement is position 0
            }
        
        # Check queued movements
        for i, (queued_id, operation, params) in enumerate(self.queue_manager.movement_queue):
            if queued_id == movement_id:
                return {
                    'success': True,
                    'movement_id': movement_id,
                    'operation': operation,
                    'status': 'queued',
                    'progress': 0.0,
                    'elapsed_time': 0.0,
                    'total_duration': params.get('duration', 3.0),
                    'queue_position': i + 1  # Queue position (1-indexed)
                }
        
        return {'success': False, 'error': f'Movement {movement_id} not found'}
    
    def list_active_movements(self) -> Dict:
        """List active movement and queued movements"""
        movements = []
        
        # Add active movement
        if self.queue_manager.active_movement:
            elapsed = time.time() - self.queue_manager.active_movement.start_time
            progress = min(elapsed / self.queue_manager.active_movement.duration, 1.0)
            
            movements.append({
                'movement_id': self.queue_manager.active_movement.movement_id,
                'operation': self.queue_manager.active_movement.operation,
                'status': 'active',
                'progress': progress,
                'queue_position': 0
            })
        
        # Add queued movements
        for i, (movement_id, operation, params) in enumerate(self.queue_manager.movement_queue):
            movements.append({
                'movement_id': movement_id,
                'operation': operation,
                'status': 'queued',
                'progress': 0.0,
                'queue_position': i + 1
            })
        
        return {
            'success': True,
            'movements': movements,
            'active_count': 1 if self.queue_manager.active_movement else 0,
            'queued_count': len(self.queue_manager.movement_queue),
            'total_count': len(movements)
        }
    
    def get_queue_status(self) -> Dict:
        """Get comprehensive queue status with timing information"""
        try:
            # Get actual queue state
            queue_state = self._get_actual_queue_state()
            
            # Initialize response
            response = {
                'success': True,
                'queue_state': queue_state,
                'timestamp': time.time()
            }
            
            # Get active shot info
            active_shot = None
            if self.queue_manager.active_movement:
                elapsed = time.time() - self.queue_manager.active_movement.start_time
                progress = min(elapsed / self.queue_manager.active_movement.duration, 1.0)
                remaining_time = max(0, self.queue_manager.active_movement.duration - elapsed)
                
                active_shot = {
                    'movement_id': self.queue_manager.active_movement.movement_id,
                    'operation': self.queue_manager.active_movement.operation,
                    'progress': progress,
                    'remaining_time': remaining_time,
                    'total_duration': self.queue_manager.active_movement.duration,
                    'execution': self.queue_manager.active_movement.params.get('execution', 'auto'),
                    'params': self.queue_manager.active_movement.params
                }
            
            response['active_shot'] = active_shot
            response['active_shots'] = [active_shot] if active_shot else []
            
            # Get queued shots info
            queued_shots = []
            estimated_start_time = active_shot['remaining_time'] if active_shot else 0
            
            for i, (movement_id, operation, params) in enumerate(self.queue_manager.movement_queue):
                # Calculate duration for display
                if 'start_position' in params and 'end_position' in params:
                    start_pos = params['start_position']
                    end_pos = params['end_position']
                    speed = params.get('speed')
                    duration = params.get('duration')
                    if speed is not None or duration is None:
                        duration = calculate_duration(start_pos, end_pos, speed, duration)
                    else:
                        duration = duration or 3.0
                else:
                    duration = params.get('duration', 3.0)
                
                shot_info = {
                    'movement_id': movement_id,
                    'operation': operation,
                    'estimated_duration': duration,
                    'estimated_start_time': estimated_start_time,
                    'queue_position': i + 1,
                    'execution': params.get('execution_mode', 'auto'),
                    'params': params
                }
                
                queued_shots.append(shot_info)
                estimated_start_time += duration
            
            response['queued_shots'] = queued_shots
            
            # Calculate totals
            active_duration = active_shot['total_duration'] if active_shot else 0
            queued_duration = sum(shot['estimated_duration'] for shot in queued_shots)
            remaining_active = active_shot['remaining_time'] if active_shot else 0
            
            response.update({
                'total_duration': active_duration + queued_duration,
                'remaining_duration': remaining_active + queued_duration,
                'shot_count': len(queued_shots) + (1 if active_shot else 0),
                'active_count': 1 if active_shot else 0,
                'queued_count': len(queued_shots)
            })
            
            return response
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Queue Control Commands
    def play_queue(self) -> Dict:
        """Start/resume queue processing"""
        try:
            # Delegate to modular queue manager
            result = self.queue_manager.play_queue()
            
            # If queue was successfully started and we have movements to process, start execution
            if result.get('success') and self.queue_manager.queue_state == 'running' and not self.queue_manager.active_movement and self.queue_manager.movement_queue:
                self._start_next_queued_movement(manual_play=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in play_queue delegation: {e}")
            return {'success': False, 'error': str(e)}
    
    def pause_queue(self) -> Dict:
        """Pause queue processing (current movement continues, no new movements start)"""
        try:
            # Delegate to modular queue manager
            result = self.queue_manager.pause_queue()
            return result
            
        except Exception as e:
            logger.error(f"Error in pause_queue delegation: {e}")
            return {'success': False, 'error': str(e)}
    
    def stop_queue(self) -> Dict:
        """Stop and clear entire queue"""
        try:
            # Delegate to modular queue manager
            result = self.queue_manager.stop_queue()
            return result
            
        except Exception as e:
            logger.error(f"Error in stop_queue delegation: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_actual_queue_state(self) -> str:
        """Determine actual queue state from current conditions"""
        try:
            # Delegate to modular queue manager
            return self.queue_manager._get_actual_queue_state()
            
        except Exception as e:
            logger.error(f"Error getting actual queue state: {e}")
            return "error"
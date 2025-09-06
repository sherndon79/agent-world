"""
Thread-safe queue management system for WorldBuilder scene operations.

Provides centralized queue processing for elements, batches, assets, and removals
with proper thread safety and request lifecycle management.
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from collections import OrderedDict

from .scene_types import (
    SceneElement, 
    SceneBatch, 
    AssetPlacement,
    RequestStatus,
    RequestState,
    RequestType
)

try:
    from ..config import get_config
    config = get_config()
except ImportError:
    config = None

logger = logging.getLogger(__name__)


class WorldBuilderQueueManager:
    """Thread-safe queue manager for all WorldBuilder operations."""
    
    def __init__(self):
        """Initialize queue manager with thread-safe operations."""
        self._lock = threading.RLock()
        
        # Queue-based processing
        self._element_queue = []
        self._batch_queue = []
        self._removal_queue = []
        self._asset_queue = []
        self._completed_requests = OrderedDict()  # O(1) FIFO eviction
        self._request_counter = 0
        self._max_completed_requests = config.max_completed_requests if config else 100
        
        # Statistics
        self._stats = {
            'batches_created': 0,
            'elements_created': 0,
            'assets_placed': 0,
            'total_prims_added': 0,
            'last_operation_time': None,
            'queued_elements': 0,
            'queued_batches': 0,
            'queued_removals': 0,
            'queued_assets': 0,
            'elements_removed': 0,
            'completed_requests': 0
        }
        
        logger.info("Queue Manager initialized with thread-safe processing")
    
    def generate_request_id(self, request_type: str) -> str:
        """Generate unique request ID with thread safety."""
        with self._lock:
            self._request_counter += 1
            return f"{request_type}_{self._request_counter}_{int(time.time())}"
    
    def store_completed_request(self, request_id: str, result: Dict[str, Any]):
        """Store completed request with O(1) automatic eviction."""
        with self._lock:
            # Automatic eviction when at capacity
            if len(self._completed_requests) >= self._max_completed_requests:
                # Remove oldest request (FIFO) - O(1) operation
                self._completed_requests.popitem(last=False)
            
            # Store new request - O(1) operation
            self._completed_requests[request_id] = result
    
    def process_single_request(self, request_id: str, operation_func: Callable, 
                             success_msg: str = "", error_context: str = "") -> Dict[str, Any]:
        """Helper method to process a single request with consistent error handling."""
        try:
            result = operation_func()
            
            # Store completion result with automatic eviction
            self.store_completed_request(request_id, {
                'success': result['success'],
                'result': result,
                'completed_time': time.time()
            })
            
            if result['success']:
                if success_msg:
                    logger.info(f"✅ {success_msg} (ID: {request_id})")
            else:
                logger.error(f"❌ Failed {error_context}: {result.get('error')}")
            
            return result
                
        except Exception as e:
            logger.error(f"❌ Error processing {error_context}: {e}")
            error_result = {'success': False, 'error': str(e)}
            self.store_completed_request(request_id, {
                'success': False,
                'result': error_result,
                'completed_time': time.time()
            })
            return error_result
    
    def add_element_request(self, element: SceneElement) -> Dict[str, Any]:
        """
        Queue an element for creation. Thread-safe operation.
        
        Args:
            element: SceneElement to queue for creation
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        with self._lock:
            try:
                # Generate request ID
                request_id = self.generate_request_id("element")
                
                # Add to queue
                request_data = {
                    'request_id': request_id,
                    'element': element,
                    'queued_time': time.time()
                }
                
                self._element_queue.append(request_data)
                self._stats['queued_elements'] += 1
                
                logger.info(f"Queued element '{element.name}' for creation (ID: {request_id})")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f"Element '{element.name}' queued for creation"
                }
                
            except Exception as e:
                logger.error(f"❌ Error queuing element: {e}")
                return {'success': False, 'error': str(e)}
    
    def add_asset_request(self, asset: AssetPlacement, request_type: str = 'asset') -> Dict[str, Any]:
        """
        Queue an asset for placement or transformation. Thread-safe operation.
        
        Args:
            asset: AssetPlacement to queue
            request_type: 'asset' for placement, 'transform' for transformation
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        with self._lock:
            try:
                # Generate request ID
                request_id = self.generate_request_id("asset")
                
                # Add to queue
                request_data = {
                    'request_id': request_id,
                    'type': request_type,
                    'asset': asset,
                    'queued_time': time.time()
                }
                
                self._asset_queue.append(request_data)
                self._stats['queued_assets'] += 1
                
                action = "placement" if request_type == 'asset' else "transformation"
                logger.info(f"Queued asset '{asset.name}' for {action} (ID: {request_id})")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f"Asset '{asset.name}' queued for {action}"
                }
                
            except Exception as e:
                logger.error(f"❌ Error queuing asset: {e}")
                return {'success': False, 'error': str(e)}
    
    def add_transform_request(self, prim_path: str, position: Optional[List[float]] = None,
                            rotation: Optional[List[float]] = None, 
                            scale: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Queue an asset transformation request. Thread-safe operation.
        """
        with self._lock:
            try:
                # Generate request ID
                request_id = self.generate_request_id("transform")
                
                # Add to queue
                request_data = {
                    'request_id': request_id,
                    'type': 'transform',
                    'prim_path': prim_path,
                    'position': position,
                    'rotation': rotation,
                    'scale': scale,
                    'queued_time': time.time()
                }
                
                self._asset_queue.append(request_data)  # Reuse asset queue for transforms
                self._stats['queued_assets'] += 1
                
                logger.info(f"Queued transform for '{prim_path}' (ID: {request_id})")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f"Transform queued for '{prim_path}'"
                }
                
            except Exception as e:
                logger.error(f"❌ Error queuing transform: {e}")
                return {'success': False, 'error': str(e)}
    
    def add_removal_request(self, removal_type: str, **kwargs) -> Dict[str, Any]:
        """
        Queue a removal operation. Thread-safe operation.
        
        Args:
            removal_type: 'remove_element' or 'clear_path'
            **kwargs: Additional parameters based on removal type
        """
        with self._lock:
            try:
                # Generate request ID
                request_id = self.generate_request_id("removal")
                
                # Add to queue
                request_data = {
                    'request_id': request_id,
                    'type': removal_type,
                    'queued_time': time.time(),
                    **kwargs
                }
                
                self._removal_queue.append(request_data)
                self._stats['queued_removals'] += 1
                
                target = kwargs.get('element_path') or kwargs.get('path', 'unknown')
                logger.info(f"Queued {removal_type} for '{target}' (ID: {request_id})")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f"Removal queued for '{target}'"
                }
                
            except Exception as e:
                logger.error(f"❌ Error queuing removal: {e}")
                return {'success': False, 'error': str(e)}
    
    def add_batch_request(self, batch_name: str, elements: List[Dict], 
                         batch_transform: Dict = None) -> Dict[str, Any]:
        """
        Queue a batch creation request. Thread-safe operation.
        """
        with self._lock:
            try:
                # Generate request ID
                request_id = self.generate_request_id("batch")
                
                # Add to queue
                request_data = {
                    'request_id': request_id,
                    'batch_name': batch_name,
                    'elements': elements,
                    'batch_transform': batch_transform or {},
                    'queued_time': time.time()
                }
                
                self._batch_queue.append(request_data)
                self._stats['queued_batches'] += 1
                
                logger.info(f"Queued batch '{batch_name}' with {len(elements)} elements (ID: {request_id})")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f"Batch '{batch_name}' queued for creation"
                }
                
            except Exception as e:
                logger.error(f"❌ Error queuing batch: {e}")
                return {'success': False, 'error': str(e)}
    
    def process_queues(self, element_processor: Callable, batch_processor: Callable,
                      asset_processor: Callable, removal_processor: Callable) -> Dict[str, Any]:
        """
        Process all queues with provided processor functions. Thread-safe operation.
        
        Args:
            element_processor: Function to process element creation
            batch_processor: Function to process batch creation
            asset_processor: Function to process asset operations
            removal_processor: Function to process removal operations
            
        Returns:
            Processing statistics
        """
        with self._lock:
            processed_count = 0
            max_operations_per_update = config.max_operations_per_cycle if config else 5
            
            try:
                # Process element queue
                while self._element_queue and processed_count < max_operations_per_update:
                    request = self._element_queue.pop(0)
                    request_id = request['request_id']
                    
                    result = self.process_single_request(
                        request_id, 
                        lambda: element_processor(request['element']),
                        success_msg=f"Created element '{request['element'].name}'",
                        error_context=f"element request {request_id}"
                    )
                    
                    if result['success']:
                        self._stats['elements_created'] += 1
                    
                    processed_count += 1
                    self._stats['queued_elements'] -= 1
                    self._stats['completed_requests'] += 1
                
                # Process batch queue
                while self._batch_queue and processed_count < max_operations_per_update:
                    request = self._batch_queue.pop(0)
                    request_id = request['request_id']
                    
                    result = self.process_single_request(
                        request_id,
                        lambda: batch_processor(
                            request['batch_name'], 
                            request['elements'], 
                            request['batch_transform']
                        ),
                        success_msg=f"Created batch '{request['batch_name']}'",
                        error_context=f"batch request {request_id}"
                    )
                    
                    if result['success']:
                        self._stats['batches_created'] += 1
                    
                    processed_count += 1
                    self._stats['queued_batches'] -= 1
                    self._stats['completed_requests'] += 1
                
                # Process asset queue
                while self._asset_queue and processed_count < max_operations_per_update:
                    request = self._asset_queue.pop(0)
                    request_id = request['request_id']
                    request_type = request['type']
                    
                    if request_type == 'asset':
                        result = self.process_single_request(
                            request_id,
                            lambda: asset_processor('place', request['asset']),
                            success_msg=f"Placed asset '{request['asset'].name}'",
                            error_context=f"asset request {request_id}"
                        )
                    elif request_type == 'transform':
                        result = self.process_single_request(
                            request_id,
                            lambda: asset_processor('transform', {
                                'prim_path': request['prim_path'],
                                'position': request['position'],
                                'rotation': request['rotation'],
                                'scale': request['scale']
                            }),
                            success_msg=f"Transformed asset '{request['prim_path']}'",
                            error_context=f"transform request {request_id}"
                        )
                    else:
                        logger.error(f"❌ Unknown request type: {request_type}")
                        continue
                    
                    if result['success']:
                        self._stats['assets_placed'] += 1
                    
                    processed_count += 1
                    self._stats['queued_assets'] -= 1
                    self._stats['completed_requests'] += 1
                
                # Process removal queue  
                while self._removal_queue and processed_count < max_operations_per_update:
                    request = self._removal_queue.pop(0)
                    request_id = request['request_id']
                    
                    result = self.process_single_request(
                        request_id,
                        lambda: removal_processor(request),
                        success_msg=f"Completed removal operation",
                        error_context=f"removal request {request_id}"
                    )
                    
                    if result['success']:
                        self._stats['elements_removed'] += result.get('removed_count', 1)
                    
                    processed_count += 1
                    self._stats['queued_removals'] -= 1
                    self._stats['completed_requests'] += 1
                
                self._stats['last_operation_time'] = time.time()
                
                return {
                    'processed_count': processed_count,
                    'queue_lengths': {
                        'elements': len(self._element_queue),
                        'batches': len(self._batch_queue),
                        'assets': len(self._asset_queue),
                        'removals': len(self._removal_queue)
                    },
                    'completed_requests': len(self._completed_requests)
                }
                
            except Exception as e:
                logger.error(f"❌ Error processing queued requests: {e}")
                return {
                    'processed_count': processed_count,
                    'error': str(e)
                }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        with self._lock:
            return {
                'queue_lengths': {
                    'elements': len(self._element_queue),
                    'batches': len(self._batch_queue),
                    'assets': len(self._asset_queue),
                    'removals': len(self._removal_queue)
                },
                'statistics': self._stats.copy(),
                'completed_requests_count': len(self._completed_requests)
            }
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific request."""
        with self._lock:
            return self._completed_requests.get(request_id)
    
    def clear_completed_requests(self):
        """Clear all completed requests."""
        with self._lock:
            self._completed_requests.clear()
            logger.info("Cleared completed requests cache")
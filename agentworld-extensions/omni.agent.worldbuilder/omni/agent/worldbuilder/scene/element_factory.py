"""
USD element creation factory for WorldBuilder scene operations.

Provides factory pattern for creating different primitive types with proper USD handling.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from pxr import Usd, UsdGeom, Gf

from .scene_types import SceneElement, PrimitiveType

logger = logging.getLogger(__name__)


class ElementFactory:
    """Factory for creating USD primitive elements with proper transforms and materials."""
    
    def __init__(self, usd_context):
        """Initialize element factory with USD context."""
        self._usd_context = usd_context
        
        # Factory registry for primitive creators
        self._primitive_creators = {
            PrimitiveType.CUBE: self._create_cube_primitive,
            PrimitiveType.SPHERE: self._create_sphere_primitive,
            PrimitiveType.CYLINDER: self._create_cylinder_primitive,
            PrimitiveType.PLANE: self._create_plane_primitive,
            PrimitiveType.CONE: self._create_cone_primitive
        }
    
    def create_element(self, element: SceneElement) -> Dict[str, Any]:
        """
        Create USD element safely on Isaac Sim's main thread.
        
        Args:
            element: SceneElement with all creation parameters
            
        Returns:
            Result dictionary with creation details
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Create element using parent_path for hierarchical placement
            element_path = f"{element.parent_path}/{element.name}"
            logger.debug(f"🔍 Creating element '{element.name}' with parent_path='{element.parent_path}' -> element_path='{element_path}'")
            
            # Create primitive based on type using factory pattern
            prim = self._create_primitive(stage, element_path, element.primitive_type)
            if not prim:
                return {
                    'success': False,
                    'error': f"Failed to create {element.primitive_type.value} primitive"
                }
            
            # Set element transform - geometry objects like UsdGeom.Cube are Xformables
            if hasattr(prim, 'GetXformOpOrderAttr'):  # It's an Xformable (geometry object)
                self._set_transform(prim, element.position, element.rotation, element.scale)
            else:
                logger.warning(f"❌ Geometry object is not Xformable - cannot set transform")
            
            # Set color - pass the geometry object for color setting
            self._set_color(prim, element.color)
            
            return {
                'success': True,
                'element_name': element.name,
                'element_type': element.primitive_type.value,
                'usd_path': element_path,
                'position': element.position,
                'message': f"Created {element.name} in USD stage"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in element creation: {e}")
            return {
                'success': False,
                'error': str(e),
                'element_name': element.name
            }
    
    def _create_primitive(self, stage: Usd.Stage, path: str, prim_type: PrimitiveType) -> Optional[UsdGeom.Gprim]:
        """Create primitive based on type using factory pattern."""
        try:
            creator_func = self._primitive_creators.get(prim_type)
            if not creator_func:
                logger.error(f"❌ Unsupported primitive type: {prim_type}")
                return None
            
            return creator_func(stage, path)
            
        except Exception as e:
            logger.error(f"❌ Error creating {prim_type.value} primitive: {e}")
            return None
    
    def _create_cube_primitive(self, stage: Usd.Stage, path: str) -> Optional[UsdGeom.Cube]:
        """Create a USD Cube primitive."""
        cube = UsdGeom.Cube.Define(stage, path)
        if cube:
            cube.GetSizeAttr().Set(1.0)  # Default 1x1x1 cube
            return cube  # Return the geometry object, not the prim
        return None
    
    def _create_sphere_primitive(self, stage: Usd.Stage, path: str) -> Optional[UsdGeom.Sphere]:
        """Create a USD Sphere primitive."""
        sphere = UsdGeom.Sphere.Define(stage, path)
        if sphere:
            sphere.GetRadiusAttr().Set(0.5)  # Default radius 0.5
            return sphere
        return None
    
    def _create_cylinder_primitive(self, stage: Usd.Stage, path: str) -> Optional[UsdGeom.Cylinder]:
        """Create a USD Cylinder primitive."""
        cylinder = UsdGeom.Cylinder.Define(stage, path)
        if cylinder:
            cylinder.GetRadiusAttr().Set(0.5)   # Default radius 0.5
            cylinder.GetHeightAttr().Set(1.0)   # Default height 1.0
            return cylinder
        return None
    
    def _create_plane_primitive(self, stage: Usd.Stage, path: str) -> Optional[UsdGeom.Mesh]:
        """Create a USD Plane (quad mesh) primitive."""
        mesh = UsdGeom.Mesh.Define(stage, path)
        if mesh:
            # Define a simple quad (plane) mesh
            points = [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)]
            face_vertex_indices = [0, 1, 2, 3]
            face_vertex_counts = [4]
            
            mesh.GetPointsAttr().Set(points)
            mesh.GetFaceVertexIndicesAttr().Set(face_vertex_indices)
            mesh.GetFaceVertexCountsAttr().Set(face_vertex_counts)
            return mesh
        return None
    
    def _create_cone_primitive(self, stage: Usd.Stage, path: str) -> Optional[UsdGeom.Cone]:
        """Create a USD Cone primitive."""
        cone = UsdGeom.Cone.Define(stage, path)
        if cone:
            cone.GetRadiusAttr().Set(0.5)   # Default radius 0.5
            cone.GetHeightAttr().Set(1.0)   # Default height 1.0
            return cone
        return None
    
    def _set_transform(self, xformable: UsdGeom.Xformable, 
                      position: Tuple[float, float, float],
                      rotation: Tuple[float, float, float],
                      scale: Tuple[float, float, float]):
        """Apply transform operations to a USD Xformable prim."""
        try:
            # Clear existing transforms to ensure clean state
            xformable.ClearXformOpOrder()
            
            # Add transform operations in TRS order - ALWAYS add all three
            # This matches the working backup implementation
            translate_op = xformable.AddTranslateOp()
            rotate_xyz_op = xformable.AddRotateXYZOp()
            scale_op = xformable.AddScaleOp()
            
            # Set values
            translate_op.Set(Gf.Vec3d(position[0], position[1], position[2]))
            rotate_xyz_op.Set(Gf.Vec3f(rotation[0], rotation[1], rotation[2]))
            scale_op.Set(Gf.Vec3f(scale[0], scale[1], scale[2]))
                
        except Exception as e:
            logger.error(f"❌ Error setting transform: {e}")
    
    def _set_color(self, prim: UsdGeom.Gprim, color: Tuple[float, float, float]):
        """Set display color for a USD primitive."""
        try:
            if hasattr(prim, 'GetDisplayColorAttr'):
                # Set display color for geometric primitives
                gprim = UsdGeom.Gprim(prim)
                color_attr = gprim.GetDisplayColorAttr()
                if not color_attr:
                    color_attr = gprim.CreateDisplayColorAttr()
                color_attr.Set([Gf.Vec3f(*color)])
        except Exception as e:
            logger.error(f"❌ Error setting color: {e}")
    
    def get_supported_types(self) -> list:
        """Get list of supported primitive types."""
        return list(self._primitive_creators.keys())
    
    def validate_element(self, element: SceneElement) -> Dict[str, Any]:
        """Validate element parameters before creation."""
        errors = []
        
        # Check primitive type support
        if element.primitive_type not in self._primitive_creators:
            errors.append(f"Unsupported primitive type: {element.primitive_type}")
        
        # Validate name
        if not element.name or not element.name.strip():
            errors.append("Element name cannot be empty")
        
        # Validate color values
        if any(c < 0.0 or c > 1.0 for c in element.color):
            errors.append("Color values must be between 0.0 and 1.0")
        
        # Validate scale values
        if any(s <= 0.0 for s in element.scale):
            errors.append("Scale values must be positive")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
"""
SQLite database layer for hierarchical waypoint and group management.

Provides persistent storage with full CRUD operations, group hierarchies,
and many-to-many waypoint-group relationships.
"""

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import get_config
from .models import Waypoint

logger = logging.getLogger(__name__)


class WaypointDatabase:
    """SQLite database manager for waypoints and groups with thread safety."""
    
    def __init__(self, db_path: Optional[str] = None):
        self._config = get_config()
        
        # Database file location
        if db_path:
            self._db_path = Path(db_path)
        elif self._config.database_path:
            self._db_path = Path(self._config.database_path)
        else:
            # Store in data directory within extension
            extension_dir = Path(__file__).parent
            data_dir = extension_dir / "data"
            data_dir.mkdir(exist_ok=True)  # Create data directory if it doesn't exist
            self._db_path = data_dir / "waypoint_data.db"
        
        # Thread safety
        self._lock = threading.RLock()
        self._thread_local = threading.local()
        
        # Initialize database
        self._init_database()
        
        if self._config.debug_mode:
            logger.info(f"Initialized waypoint database: {self._db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._thread_local, 'connection'):
            self._thread_local.connection = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False
            )
            self._thread_local.connection.row_factory = sqlite3.Row
            # Ensure foreign key constraints are enforced
            try:
                self._thread_local.connection.execute("PRAGMA foreign_keys = ON;")
            except Exception:
                pass
        return self._thread_local.connection
    
    def _init_database(self):
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            
            # Create groups table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    parent_group_id TEXT,
                    created_at TEXT NOT NULL,
                    color TEXT DEFAULT '#4A90E2',
                    FOREIGN KEY (parent_group_id) REFERENCES groups(id)
                )
            """)
            
            # Create waypoints table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS waypoints (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    position_x REAL NOT NULL,
                    position_y REAL NOT NULL,
                    position_z REAL NOT NULL,
                    target_x REAL DEFAULT 0.0,
                    target_y REAL DEFAULT 0.0,
                    target_z REAL DEFAULT 0.0,
                    waypoint_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # Create waypoint-group membership table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS waypoint_groups (
                    waypoint_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    PRIMARY KEY (waypoint_id, group_id),
                    FOREIGN KEY (waypoint_id) REFERENCES waypoints(id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_type ON waypoints(waypoint_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_session ON waypoints(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_timestamp ON waypoints(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_type_timestamp ON waypoints(waypoint_type, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_session_timestamp ON waypoints(session_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoints_position ON waypoints(position_x, position_y, position_z)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_group_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoint_groups_waypoint ON waypoint_groups(waypoint_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoint_groups_group ON waypoint_groups(group_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_waypoint_groups_composite ON waypoint_groups(group_id, waypoint_id)")
            
            conn.commit()
    
    # =====================================================================
    # GROUP MANAGEMENT
    # =====================================================================
    
    def create_group(
        self,
        name: str,
        description: Optional[str] = None,
        parent_group_id: Optional[str] = None,
        color: str = "#4A90E2"
    ) -> str:
        """Create a new group."""
        with self._lock:
            group_id = f"grp_{uuid.uuid4().hex[:8]}"
            conn = self._get_connection()
            
            # Validate parent group exists if specified
            if parent_group_id:
                parent = conn.execute(
                    "SELECT id FROM groups WHERE id = ?", (parent_group_id,)
                ).fetchone()
                if not parent:
                    raise ValueError(f"Parent group {parent_group_id} not found")
            
            conn.execute("""
                INSERT INTO groups (id, name, description, parent_group_id, created_at, color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (group_id, name, description, parent_group_id, datetime.now().isoformat(), color))
            
            conn.commit()
            logger.info(f"Created group {group_id}: {name}")
            return group_id
    
    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get group by ID."""
        with self._lock:
            conn = self._get_connection()
            row = conn.execute(
                "SELECT * FROM groups WHERE id = ?", (group_id,)
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def list_groups(self, parent_group_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List groups, optionally filtered by parent."""
        with self._lock:
            conn = self._get_connection()
            
            if parent_group_id is None:
                # Get top-level groups (no parent)
                rows = conn.execute(
                    "SELECT * FROM groups WHERE parent_group_id IS NULL ORDER BY name"
                ).fetchall()
            else:
                # Get children of specific group
                rows = conn.execute(
                    "SELECT * FROM groups WHERE parent_group_id = ? ORDER BY name",
                    (parent_group_id,)
                ).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_group_hierarchy(self) -> Dict[str, Any]:
        """Get complete group hierarchy as nested structure."""
        with self._lock:
            conn = self._get_connection()
            
            # Get all groups
            all_groups = conn.execute("SELECT * FROM groups ORDER BY name").fetchall()
            groups_by_id = {row['id']: dict(row) for row in all_groups}
            
            # Build hierarchy tree
            def build_tree(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
                children = []
                for group_id, group in groups_by_id.items():
                    if group['parent_group_id'] == parent_id:
                        group_with_children = group.copy()
                        group_with_children['children'] = build_tree(group_id)
                        children.append(group_with_children)
                return children
            
            return {
                "hierarchy": build_tree(None),
                "total_groups": len(groups_by_id)
            }
    
    def remove_group(self, group_id: str, cascade: bool = False) -> bool:
        """Remove group. If cascade=True, removes child groups and unassigns waypoints."""
        with self._lock:
            conn = self._get_connection()
            
            # Check if group exists
            group = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                return False
            
            if cascade:
                # Remove all child groups recursively
                self._remove_group_cascade(conn, group_id)
            else:
                # Check for child groups
                children = conn.execute(
                    "SELECT id FROM groups WHERE parent_group_id = ?", (group_id,)
                ).fetchall()
                
                if children:
                    raise ValueError(f"Group {group_id} has {len(children)} child groups. Use cascade=True to remove them.")
            
            # Remove waypoint-group associations
            conn.execute("DELETE FROM waypoint_groups WHERE group_id = ?", (group_id,))
            
            # Remove the group
            conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            conn.commit()
            
            logger.info(f"Removed group {group_id} (cascade={cascade})")
            return True
    
    def _remove_group_cascade(self, conn: sqlite3.Connection, group_id: str):
        """Recursively remove group and all children."""
        # Get child groups
        children = conn.execute(
            "SELECT id FROM groups WHERE parent_group_id = ?", (group_id,)
        ).fetchall()
        
        # Recursively remove children
        for child in children:
            self._remove_group_cascade(conn, child['id'])
        
        # Remove waypoint associations for this group
        conn.execute("DELETE FROM waypoint_groups WHERE group_id = ?", (group_id,))
        
        # Remove the group itself
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    
    # =====================================================================
    # WAYPOINT MANAGEMENT
    # =====================================================================
    
    def create_waypoint(
        self,
        position: Tuple[float, float, float],
        waypoint_type: str = "point_of_interest",
        name: Optional[str] = None,
        target: Optional[Tuple[float, float, float]] = None,
        metadata: Optional[Dict] = None,
        group_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Create waypoint with optional group assignments."""
        with self._lock:
            conn = self._get_connection()
            
            # Check waypoint limit
            count = conn.execute("SELECT COUNT(*) as count FROM waypoints").fetchone()['count']
            if count >= self._config.max_waypoints:
                raise ValueError(f"Maximum waypoints ({self._config.max_waypoints}) reached")
            
            waypoint_id = f"wp_{uuid.uuid4().hex[:8]}"
            
            # Generate name based on database count (not in-memory cache)
            if not name:
                # Get count of existing waypoints of this type for better numbering
                existing_count = conn.execute(
                    "SELECT COUNT(*) as count FROM waypoints WHERE waypoint_type = ?", 
                    (waypoint_type,)
                ).fetchone()['count']
                name = f"{waypoint_type.replace('_', ' ').title()} {existing_count + 1}"
            
            # Insert waypoint
            conn.execute("""
                INSERT INTO waypoints 
                (id, name, position_x, position_y, position_z, target_x, target_y, target_z,
                 waypoint_type, timestamp, session_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                waypoint_id, name,
                position[0], position[1], position[2],
                target[0] if target else None, 
                target[1] if target else None, 
                target[2] if target else None,
                waypoint_type, datetime.now().isoformat(),
                session_id, json.dumps(metadata or {})
            ))
            
            # Add group memberships
            if group_ids:
                self._add_waypoint_to_groups(conn, waypoint_id, group_ids)
            
            conn.commit()
            logger.info(f"Created waypoint {waypoint_id}: {name} at {position}")
            return waypoint_id
    
    def get_waypoint(self, waypoint_id: str) -> Optional[Waypoint]:
        """Get waypoint by ID with group information."""
        with self._lock:
            conn = self._get_connection()
            row = conn.execute("SELECT * FROM waypoints WHERE id = ?", (waypoint_id,)).fetchone()
            
            if not row:
                return None
            
            # Get group memberships
            group_rows = conn.execute("""
                SELECT g.id, g.name FROM groups g
                JOIN waypoint_groups wg ON g.id = wg.group_id
                WHERE wg.waypoint_id = ?
            """, (waypoint_id,)).fetchall()
            
            groups = [{"id": g['id'], "name": g['name']} for g in group_rows]
            
            # Parse metadata and add groups
            metadata = json.loads(row['metadata'] or '{}')
            metadata['groups'] = groups
            
            return Waypoint(
                id=row['id'],
                name=row['name'],
                position=(row['position_x'], row['position_y'], row['position_z']),
                target=(row['target_x'], row['target_y'], row['target_z']),
                waypoint_type=row['waypoint_type'],
                timestamp=row['timestamp'],
                session_id=row['session_id'] or "",
                metadata=metadata
            )
    
    def list_waypoints(
        self,
        waypoint_type: Optional[str] = None,
        group_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[Waypoint]:
        """List waypoints with optional filtering."""
        with self._lock:
            conn = self._get_connection()
            
            # Build query based on filters
            query = "SELECT DISTINCT w.* FROM waypoints w"
            params = []
            conditions = []
            
            if group_id:
                query += " JOIN waypoint_groups wg ON w.id = wg.waypoint_id"
                conditions.append("wg.group_id = ?")
                params.append(group_id)
            
            if waypoint_type:
                conditions.append("w.waypoint_type = ?")
                params.append(waypoint_type)
            
            if session_id:
                conditions.append("w.session_id = ?")
                params.append(session_id)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY w.timestamp"
            
            # Optimize to eliminate N+1 query - get all group info in single query
            # Split query to properly place GROUP BY before ORDER BY
            order_by_pos = query.rfind(" ORDER BY")
            if order_by_pos != -1:
                query_base = query[:order_by_pos]
                order_clause = query[order_by_pos:]
            else:
                query_base = query
                order_clause = ""
            
            query_with_groups = query_base.replace("SELECT DISTINCT w.*", 
                "SELECT DISTINCT w.*, GROUP_CONCAT(g.id || '|' || g.name) as group_info")
            query_with_groups = query_with_groups.replace("FROM waypoints w", 
                "FROM waypoints w LEFT JOIN waypoint_groups wg2 ON w.id = wg2.waypoint_id LEFT JOIN groups g ON wg2.group_id = g.id")
            query_with_groups += " GROUP BY w.id" + order_clause
            
            rows = conn.execute(query_with_groups, params).fetchall()
            waypoints = []
            
            for row in rows:
                # Parse group info efficiently from concatenated result
                groups = []
                if row['group_info']:
                    for group_str in row['group_info'].split(','):
                        if '|' in group_str:
                            g_id, g_name = group_str.split('|', 1)
                            groups.append({"id": g_id, "name": g_name})
                
                metadata = json.loads(row['metadata'] or '{}')
                metadata['groups'] = groups
                
                waypoint = Waypoint(
                    id=row['id'],
                    name=row['name'],
                    position=(row['position_x'], row['position_y'], row['position_z']),
                    target=(row['target_x'], row['target_y'], row['target_z']),
                    waypoint_type=row['waypoint_type'],
                    timestamp=row['timestamp'],
                    session_id=row['session_id'] or "",
                    metadata=metadata
                )
                waypoints.append(waypoint)
            
            return waypoints
    
    def remove_waypoint(self, waypoint_id: str) -> bool:
        """Remove waypoint and all group associations."""
        with self._lock:
            conn = self._get_connection()
            
            # Check if waypoint exists
            exists = conn.execute("SELECT id FROM waypoints WHERE id = ?", (waypoint_id,)).fetchone()
            if not exists:
                return False
            
            # Remove group associations (CASCADE handles this automatically)
            conn.execute("DELETE FROM waypoints WHERE id = ?", (waypoint_id,))
            conn.commit()
            
            logger.info(f"Removed waypoint {waypoint_id}")
            return True
    
    def update_waypoint(self, waypoint_id: str, **updates) -> bool:
        """Update waypoint fields."""
        with self._lock:
            conn = self._get_connection()
            
            # Check if waypoint exists
            exists = conn.execute("SELECT id FROM waypoints WHERE id = ?", (waypoint_id,)).fetchone()
            if not exists:
                return False
            
            # Build update query
            set_clauses = []
            params = []
            
            # Handle direct field updates
            field_map = {
                'name': 'name',
                'waypoint_type': 'waypoint_type',
                'position': ('position_x', 'position_y', 'position_z'),
                'target': ('target_x', 'target_y', 'target_z')
            }
            
            for field, value in updates.items():
                if field == 'metadata':
                    set_clauses.append("metadata = ?")
                    params.append(json.dumps(value))
                elif field in field_map:
                    if field in ['position', 'target'] and isinstance(value, (list, tuple)):
                        # Handle coordinate updates
                        coord_fields = field_map[field]
                        for i, coord_field in enumerate(coord_fields):
                            set_clauses.append(f"{coord_field} = ?")
                            params.append(value[i])
                    else:
                        set_clauses.append(f"{field_map[field]} = ?")
                        params.append(value)
            
            if set_clauses:
                query = f"UPDATE waypoints SET {', '.join(set_clauses)} WHERE id = ?"
                params.append(waypoint_id)
                conn.execute(query, params)
                conn.commit()
                
                logger.info(f"Updated waypoint {waypoint_id}: {list(updates.keys())}")
            
            return True
    
    # =====================================================================
    # GROUP MEMBERSHIP MANAGEMENT
    # =====================================================================
    
    def add_waypoint_to_groups(self, waypoint_id: str, group_ids: List[str]) -> int:
        """Add waypoint to multiple groups."""
        with self._lock:
            conn = self._get_connection()
            return self._add_waypoint_to_groups(conn, waypoint_id, group_ids)
    
    def _add_waypoint_to_groups(self, conn: sqlite3.Connection, waypoint_id: str, group_ids: List[str]) -> int:
        """Internal method to add waypoint to groups."""
        added_count = 0
        
        for group_id in group_ids:
            # Validate group exists
            group = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                logger.warning(f"Group {group_id} not found, skipping")
                continue
            
            # Check if association already exists
            existing = conn.execute(
                "SELECT 1 FROM waypoint_groups WHERE waypoint_id = ? AND group_id = ?",
                (waypoint_id, group_id)
            ).fetchone()
            
            if not existing:
                conn.execute(
                    "INSERT INTO waypoint_groups (waypoint_id, group_id) VALUES (?, ?)",
                    (waypoint_id, group_id)
                )
                added_count += 1
        
        if added_count > 0:
            try:
                conn.commit()
            except Exception:
                pass
            logger.info(f"Added waypoint {waypoint_id} to {added_count} groups")
        
        return added_count
    
    def remove_waypoint_from_groups(self, waypoint_id: str, group_ids: List[str]) -> int:
        """Remove waypoint from multiple groups."""
        with self._lock:
            conn = self._get_connection()
            removed_count = 0
            
            for group_id in group_ids:
                result = conn.execute(
                    "DELETE FROM waypoint_groups WHERE waypoint_id = ? AND group_id = ?",
                    (waypoint_id, group_id)
                )
                if result.rowcount > 0:
                    removed_count += 1
            
            if removed_count > 0:
                conn.commit()
                logger.info(f"Removed waypoint {waypoint_id} from {removed_count} groups")
            
            return removed_count
    
    def get_waypoint_groups(self, waypoint_id: str) -> List[Dict[str, Any]]:
        """Get all groups that contain a waypoint."""
        with self._lock:
            conn = self._get_connection()
            rows = conn.execute("""
                SELECT g.* FROM groups g
                JOIN waypoint_groups wg ON g.id = wg.group_id
                WHERE wg.waypoint_id = ?
                ORDER BY g.name
            """, (waypoint_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_group_waypoints(self, group_id: str, include_nested: bool = False) -> List[Waypoint]:
        """Get all waypoints in a group, optionally including nested groups."""
        with self._lock:
            # Validate input
            if not group_id or not isinstance(group_id, str):
                raise ValueError("Invalid group_id provided")
            
            conn = self._get_connection()
            
            if include_nested:
                # Get all descendant group IDs
                group_ids = self._get_descendant_group_ids(group_id)
                group_ids.add(group_id)  # Include the group itself
                
                # Validate group IDs collection (prevent excessive queries)
                if not group_ids or len(group_ids) > 1000:
                    raise ValueError("Invalid group_ids collection")
                
                # Single optimized query with JOIN (eliminates N+1 problem)
                placeholders = ', '.join('?' * len(group_ids))
                query = f"""
                    SELECT DISTINCT w.id, w.name, w.position_x, w.position_y, w.position_z,
                           w.target_x, w.target_y, w.target_z, w.waypoint_type,
                           w.timestamp, w.session_id, w.metadata,
                           GROUP_CONCAT(g.id || '|' || g.name) as group_info
                    FROM waypoints w
                    JOIN waypoint_groups wg ON w.id = wg.waypoint_id
                    LEFT JOIN waypoint_groups wg2 ON w.id = wg2.waypoint_id
                    LEFT JOIN groups g ON wg2.group_id = g.id
                    WHERE wg.group_id IN ({placeholders})
                    GROUP BY w.id
                    ORDER BY w.timestamp
                """
                params = list(group_ids)
            else:
                # Single optimized query for direct members only
                query = """
                    SELECT DISTINCT w.id, w.name, w.position_x, w.position_y, w.position_z,
                           w.target_x, w.target_y, w.target_z, w.waypoint_type,
                           w.timestamp, w.session_id, w.metadata,
                           GROUP_CONCAT(g.id || '|' || g.name) as group_info
                    FROM waypoints w
                    JOIN waypoint_groups wg ON w.id = wg.waypoint_id
                    LEFT JOIN waypoint_groups wg2 ON w.id = wg2.waypoint_id
                    LEFT JOIN groups g ON wg2.group_id = g.id
                    WHERE wg.group_id = ?
                    GROUP BY w.id
                    ORDER BY w.timestamp
                """
                params = [group_id]
            
            rows = conn.execute(query, params).fetchall()
            waypoints = []
            
            for row in rows:
                # Parse group info efficiently
                groups = []
                if row['group_info']:
                    for group_str in row['group_info'].split(','):
                        if '|' in group_str:
                            g_id, g_name = group_str.split('|', 1)
                            groups.append({"id": g_id, "name": g_name})
                
                # Parse metadata efficiently
                try:
                    metadata = json.loads(row['metadata'] or '{}')
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
                metadata['groups'] = groups
                
                # Create waypoint object directly (bypass get_waypoint call)
                waypoint = Waypoint(
                    id=row['id'],
                    name=row['name'],
                    position=(row['position_x'], row['position_y'], row['position_z']),
                    target=(row['target_x'], row['target_y'], row['target_z']),
                    waypoint_type=row['waypoint_type'],
                    timestamp=row['timestamp'],
                    session_id=row['session_id'] or "",
                    metadata=metadata
                )
                waypoints.append(waypoint)
            
            return waypoints
    
    def _get_descendant_group_ids(self, group_id: str) -> Set[str]:
        """Get all descendant group IDs recursively."""
        conn = self._get_connection()
        descendants = set()
        
        # Get direct children
        children = conn.execute(
            "SELECT id FROM groups WHERE parent_group_id = ?", (group_id,)
        ).fetchall()
        
        for child in children:
            child_id = child['id']
            descendants.add(child_id)
            # Recursively get descendants
            descendants.update(self._get_descendant_group_ids(child_id))
        
        return descendants
    
    # =====================================================================
    # BULK OPERATIONS
    # =====================================================================
    
    def clear_waypoints(self) -> int:
        """Clear all waypoints."""
        with self._lock:
            conn = self._get_connection()
            count = conn.execute("SELECT COUNT(*) as count FROM waypoints").fetchone()['count']
            conn.execute("DELETE FROM waypoints")
            conn.commit()
            
            logger.info(f"Cleared {count} waypoints")
            return count
    
    def clear_groups(self) -> int:
        """Clear all groups and their associations."""
        with self._lock:
            conn = self._get_connection()
            count = conn.execute("SELECT COUNT(*) as count FROM groups").fetchone()['count']
            conn.execute("DELETE FROM groups")
            conn.commit()
            
            logger.info(f"Cleared {count} groups")
            return count
    
    # =====================================================================
    # EXPORT/IMPORT
    # =====================================================================
    
    def export_to_json(self, include_groups: bool = True) -> Dict[str, Any]:
        """Export waypoints and optionally groups to JSON structure."""
        with self._lock:
            export_data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "waypoints": [],
                "groups": [] if include_groups else None
            }
            
            # Export waypoints
            waypoints = self.list_waypoints()
            for wp in waypoints:
                # Extract group IDs from metadata for import compatibility
                group_ids = []
                if 'groups' in wp.metadata:
                    group_ids = [group['id'] for group in wp.metadata['groups']]
                
                wp_data = {
                    "id": wp.id,
                    "name": wp.name,
                    "position": wp.position,
                    "target": wp.target,
                    "waypoint_type": wp.waypoint_type,
                    "timestamp": wp.timestamp,
                    "metadata": wp.metadata,
                    "group_ids": group_ids
                }
                export_data["waypoints"].append(wp_data)
            
            # Export groups if requested
            if include_groups:
                hierarchy = self.get_group_hierarchy()
                export_data["groups"] = hierarchy["hierarchy"]
            
            return export_data
    
    def import_from_json(self, data: Dict[str, Any], merge_mode: str = "replace") -> Dict[str, int]:
        """Import waypoints and groups from JSON data."""
        with self._lock:
            conn = self._get_connection()
            stats = {"waypoints_imported": 0, "groups_imported": 0, "errors": 0}
            group_id_mapping = {}  # Maps old group IDs to new group IDs
            
            if merge_mode == "replace":
                # Clear existing data
                conn.execute("DELETE FROM waypoints")
                conn.execute("DELETE FROM groups")
            
            # Import groups first (to establish hierarchy) and build ID mapping
            if data.get("groups"):
                group_id_mapping = self._import_groups_recursive(conn, data["groups"])
                stats["groups_imported"] = len(group_id_mapping)
                logger.info(f"Built group ID mapping: {group_id_mapping}")
            
            # Import waypoints with mapped group IDs
            for wp_data in data.get("waypoints", []):
                try:
                    original_group_ids = wp_data.get("group_ids", [])
                    # Map old group IDs to new group IDs
                    mapped_group_ids = [group_id_mapping.get(old_id, old_id) for old_id in original_group_ids]
                    
                    logger.info(f"Importing waypoint {wp_data.get('name')} with original group_ids: {original_group_ids} -> mapped: {mapped_group_ids}")
                    
                    # Handle target data - convert null arrays to None
                    target_data = wp_data.get("target")
                    if target_data and any(x is not None for x in target_data):
                        target = tuple(target_data)
                    else:
                        target = None
                    
                    waypoint_id = self.create_waypoint(
                        position=tuple(wp_data["position"]),
                        waypoint_type=wp_data["waypoint_type"],
                        name=wp_data["name"],
                        target=target,
                        metadata=wp_data.get("metadata", {}),
                        group_ids=mapped_group_ids
                    )
                    stats["waypoints_imported"] += 1
                    logger.info(f"Successfully imported waypoint {waypoint_id}")
                except Exception as e:
                    logger.error(f"Failed to import waypoint {wp_data.get('name', 'unknown')}: {e}")
                    stats["errors"] += 1
            
            conn.commit()
            return stats
    
    def _import_groups_recursive(self, conn: sqlite3.Connection, groups: List[Dict], parent_id: Optional[str] = None, id_mapping: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Recursively import group hierarchy and return old_id -> new_id mapping."""
        if id_mapping is None:
            id_mapping = {}
        
        for group_data in groups:
            try:
                old_group_id = group_data["id"]  # Original ID from export
                new_group_id = self.create_group(
                    name=group_data["name"],
                    description=group_data.get("description"),
                    parent_group_id=parent_id,
                    color=group_data.get("color", "#4A90E2")
                )
                
                # Store the mapping
                id_mapping[old_group_id] = new_group_id
                logger.info(f"Group ID mapping: {old_group_id} -> {new_group_id}")
                
                # Import children (pass the mapped parent ID)
                if group_data.get("children"):
                    self._import_groups_recursive(
                        conn, group_data["children"], new_group_id, id_mapping
                    )
                    
            except Exception as e:
                logger.error(f"Failed to import group {group_data.get('name', 'unknown')}: {e}")
        
        return id_mapping
    
    # =====================================================================
    # STATISTICS AND UTILITIES
    # =====================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            conn = self._get_connection()
            
            waypoint_count = conn.execute("SELECT COUNT(*) as count FROM waypoints").fetchone()['count']
            group_count = conn.execute("SELECT COUNT(*) as count FROM groups").fetchone()['count']
            
            # Waypoint type breakdown
            type_breakdown = conn.execute("""
                SELECT waypoint_type, COUNT(*) as count 
                FROM waypoints 
                GROUP BY waypoint_type
            """).fetchall()
            
            # Group membership stats
            membership_stats = conn.execute("""
                SELECT 
                    COUNT(DISTINCT waypoint_id) as waypoints_with_groups,
                    COUNT(*) as total_memberships,
                    AVG(group_count) as avg_groups_per_waypoint
                FROM (
                    SELECT waypoint_id, COUNT(group_id) as group_count
                    FROM waypoint_groups
                    GROUP BY waypoint_id
                )
            """).fetchone()
            
            return {
                "database_path": str(self._db_path),
                "total_waypoints": waypoint_count,
                "total_groups": group_count,
                "waypoint_types": {row['waypoint_type']: row['count'] for row in type_breakdown},
                "group_memberships": {
                    "waypoints_with_groups": membership_stats['waypoints_with_groups'] or 0,
                    "total_memberships": membership_stats['total_memberships'] or 0,
                    "avg_groups_per_waypoint": round(membership_stats['avg_groups_per_waypoint'] or 0, 2)
                }
            }
    
    def migrate_from_memory(self, waypoints: Dict[str, Waypoint]) -> int:
        """Migrate existing in-memory waypoints to database."""
        with self._lock:
            migrated_count = 0
            
            for waypoint in waypoints.values():
                try:
                    # Extract any existing group info from metadata
                    group_ids = waypoint.metadata.get('groups', [])
                    if isinstance(group_ids, list) and all(isinstance(g, dict) for g in group_ids):
                        # Convert from group objects to IDs
                        group_ids = [g['id'] for g in group_ids if 'id' in g]
                    
                    self.create_waypoint(
                        position=waypoint.position,
                        waypoint_type=waypoint.waypoint_type,
                        name=waypoint.name,
                        target=waypoint.target,
                        metadata=waypoint.metadata,
                        group_ids=group_ids,
                        session_id=waypoint.session_id
                    )
                    migrated_count += 1
                except Exception as e:
                    logger.error(f"Failed to migrate waypoint {waypoint.id}: {e}")
            
            logger.info(f"Migrated {migrated_count} waypoints to database")
            return migrated_count
    
    def close(self):
        """Close database connections."""
        if hasattr(self._thread_local, 'connection'):
            try:
                self._thread_local.connection.close()
                delattr(self._thread_local, 'connection')
                logger.info("Database connection closed successfully")
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")

    def cleanup_connections(self):
        """Clean up all thread-local connections. Alias for close()."""
        self.close()

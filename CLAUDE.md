# Claude Code Reference Guide

## Isaac Sim Coordinate System

**Important:** Isaac Sim uses a different coordinate orientation than typical "architectural" thinking.

### Coordinate Axes (visible in viewport bottom-left):
- **X (red arrow)**: Left/Right movement
- **Y (green arrow)**: Forward/Back movement  
- **Z (blue arrow)**: Up/Down movement (vertical)

### Common Orientation Issues:
- When designing "vertical" structures (like towers, buildings, space stations), objects often appear lying on their side
- This happens because Isaac Sim's coordinate system differs from typical Y-up architectural conventions

### Solutions:
1. **For vertical structures**: Apply 90-degree rotation around X-axis: `rotation: [90, 0, 0]`
2. **For ground placement**: Use positive Z values for height (Z=0 is ground level)
3. **Combined transforms**: Apply both position AND rotation in same transform call to avoid overwriting

### Example:
```python
# Incorrect: Will lie on side
position: [0, 8, 0]  # This puts object "forward" not "up"

# Correct: Vertical structure on ground
position: [0, 0, 12]    # Move up in Z
rotation: [90, 0, 0]    # Rotate to vertical orientation
```

### Pro Tips:
- Take screenshots to verify orientation before complex positioning
- Use WorldViewer camera controls to examine structures from multiple angles
- Remember: Z is up, not Y!
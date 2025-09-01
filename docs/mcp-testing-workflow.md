# End-to-End MCP Testing Workflow

This document provides a comprehensive testing workflow for Model Context Protocol (MCP) servers in the Agent World ecosystem, covering everything from development testing to production validation.

## Overview

The Agent World MCP servers provide AI agents with standardized access to Isaac Sim through WorldBuilder, WorldViewer, WorldRecorder, WorldSurveyor, and Screenshot tools. This workflow ensures reliable, performant, and secure MCP implementations.

## Testing Architecture

### Test Pyramid Structure

```
    E2E Integration Tests
   ┌─────────────────────┐
  │  Multi-Server Flows │
  │  Full Scenarios     │
 └─────────────────────┘
       
    Component Tests
   ┌─────────────────────┐
  │  Individual MCP     │
  │  Server Functions   │
 └─────────────────────┘
       
      Unit Tests  
   ┌─────────────────────┐
  │  Tool Functions     │
  │  Auth & Validation  │
 └─────────────────────┘
```

### Test Environments

- **Development**: Local Isaac Sim + MCP servers
- **Staging**: Containerized environment with full stack
- **Production**: Live deployment validation

## Pre-Testing Setup

### 1. Environment Verification

**Check Isaac Sim Extensions Status:**
```bash
# Verify all extensions are running
curl -f http://localhost:8899/health  # WorldBuilder
curl -f http://localhost:8900/health  # WorldViewer  
curl -f http://localhost:8891/health  # WorldSurveyor
curl -f http://localhost:8892/health  # WorldRecorder
```

**Expected Health Response:**
```json
{
  "service": "Agent WorldBuilder API",
  "version": "0.1.0",
  "status": "healthy",
  "timestamp": 1756741736.8352048,
  "scene_object_count": 0
}
```

**Verify MCP Server Virtual Environments:**
```bash
# Check all MCP server venvs exist and are functional
for server in worldbuilder worldviewer worldsurveyor worldrecorder desktop-screenshot; do
    echo "Testing $server..."
    ./mcp-servers/$server/venv/bin/python -c "import mcp; print('✓ MCP available')"
done
```

### 2. Authentication Testing

**Test Auth Negotiation:**
```bash
# Test with auth disabled
export AGENT_EXT_AUTH_ENABLED=0
python -m mcp_servers.test_auth_flow

# Test with auth enabled
export AGENT_EXT_AUTH_ENABLED=1
export AGENT_EXT_HMAC_SECRET="test-secret"
export AGENT_EXT_AUTH_TOKEN="test-token"
python -m mcp_servers.test_auth_flow
```

**Expected Auth Flow:**
1. Initial request → 401 challenge
2. Auth negotiation → credentials exchange
3. Subsequent requests → authenticated successfully

## Unit Testing

### Tool Function Tests

**WorldBuilder Tool Tests:**
```python
import pytest
from mcp_agent_worldbuilder import WorldBuilderServer

@pytest.mark.asyncio
async def test_add_element_validation():
    server = WorldBuilderServer()
    
    # Test valid element creation
    result = await server.add_element({
        "element_type": "cube",
        "name": "test_cube", 
        "position": [0, 0, 1],
        "color": [1, 0, 0]
    })
    assert result["success"] == True
    
    # Test invalid element type
    with pytest.raises(ValueError):
        await server.add_element({
            "element_type": "invalid_shape",
            "name": "bad_element",
            "position": [0, 0, 0]
        })

@pytest.mark.asyncio  
async def test_batch_creation_limits():
    server = WorldBuilderServer()
    
    # Test batch size limits
    large_batch = {
        "batch_name": "stress_test",
        "elements": [{"element_type": "cube", "name": f"cube_{i}", 
                     "position": [i, 0, 0]} for i in range(1000)]
    }
    
    result = await server.create_batch(large_batch)
    assert "batch_size_warning" in result or result["success"] == False
```

**WorldViewer Camera Tests:**
```python
@pytest.mark.asyncio
async def test_camera_position_bounds():
    server = WorldViewerServer()
    
    # Test valid camera position
    result = await server.set_camera_position({
        "position": [10, 10, 10],
        "target": [0, 0, 0]
    })
    assert result["success"] == True
    
    # Test extreme camera positions
    extreme_pos = {"position": [10000, 10000, 10000]}
    result = await server.set_camera_position(extreme_pos)
    assert "position_clamped" in result or result["success"] == False

@pytest.mark.asyncio
async def test_smooth_movement_interruption():
    server = WorldViewerServer()
    
    # Start movement
    move_result = await server.smooth_move({
        "start_position": [0, 0, 10],
        "end_position": [20, 20, 10],
        "duration": 10.0
    })
    movement_id = move_result["movement_id"]
    
    # Stop movement mid-execution
    stop_result = await server.stop_movement({"movement_id": movement_id})
    assert stop_result["success"] == True
```

### Authentication & Error Handling Tests

```python
@pytest.mark.asyncio
async def test_auth_retry_mechanism():
    """Test automatic auth retry on 401 responses."""
    client = MCPBaseClient("test_service", "http://localhost:8899")
    
    # Mock 401 response followed by success
    with patch('aiohttp.ClientSession.request') as mock_request:
        mock_request.side_effect = [
            Mock(status=401),  # First call fails
            Mock(status=200, json=lambda: {"success": True})  # Retry succeeds
        ]
        
        result = await client.get("/test")
        assert result["success"] == True
        assert mock_request.call_count == 2

@pytest.mark.asyncio
async def test_connection_resilience():
    """Test MCP server behavior during Isaac Sim restarts."""
    server = WorldBuilderServer()
    
    # Simulate Isaac Sim downtime
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientConnectionError()
        
        result = await server.get_scene_status()
        assert result["success"] == False
        assert "connection_error" in result
```

## Component Testing

### Single MCP Server Integration Tests

**WorldBuilder Component Test:**
```python
@pytest.mark.asyncio
async def test_worldbuilder_scene_lifecycle():
    """Test complete scene creation and cleanup workflow."""
    
    # 1. Verify clean start
    status = await worldbuilder_health_check()
    assert status["scene_object_count"] == 0
    
    # 2. Create scene elements
    elements = [
        {"element_type": "cube", "name": "floor", "position": [0, 0, -1]},
        {"element_type": "sphere", "name": "ball", "position": [0, 0, 2]},
        {"element_type": "cylinder", "name": "pillar", "position": [5, 0, 1]}
    ]
    
    batch_result = await worldbuilder_create_batch({
        "batch_name": "test_scene", 
        "elements": elements
    })
    assert batch_result["success"] == True
    
    # 3. Query created objects
    scene = await worldbuilder_get_scene()
    assert len(scene["elements"]) == 3
    assert all(elem["name"] in ["floor", "ball", "pillar"] for elem in scene["elements"])
    
    # 4. Spatial queries
    nearby = await worldbuilder_query_objects_near_point({
        "point": [0, 0, 0], 
        "radius": 10
    })
    assert len(nearby["objects"]) == 3
    
    # 5. Cleanup
    clear_result = await worldbuilder_clear_scene({"confirm": True})
    assert clear_result["success"] == True
    
    final_status = await worldbuilder_health_check()
    assert final_status["scene_object_count"] == 0
```

**WorldRecorder Capture Test:**
```python
@pytest.mark.asyncio
async def test_worldrecorder_capture_workflow():
    """Test screenshot and video recording capabilities."""
    
    # Setup scene for recording
    await worldbuilder_add_element({
        "element_type": "sphere",
        "name": "record_target",
        "position": [0, 0, 2],
        "color": [0, 1, 0]
    })
    
    await worldviewer_set_camera_position({
        "position": [5, 5, 3],
        "target": [0, 0, 2]
    })
    
    # Test frame capture
    frame_result = await worldrecorder_capture_frame({
        "output_path": "/tmp/test_frame.png",
        "width": 1920,
        "height": 1080
    })
    assert frame_result["success"] == True
    assert os.path.exists("/tmp/test_frame.png")
    
    # Test video recording
    record_start = await worldrecorder_start_recording({
        "output_path": "/tmp/test_video.mp4",
        "duration_sec": 5.0,
        "fps": 30
    })
    assert record_start["success"] == True
    
    # Move camera during recording
    await worldviewer_smooth_move({
        "start_position": [5, 5, 3],
        "end_position": [-5, 5, 3], 
        "duration": 4.0
    })
    
    # Wait for recording completion
    await asyncio.sleep(6)
    
    status = await worldrecorder_get_status()
    assert status["recording_active"] == False
    assert os.path.exists("/tmp/test_video.mp4")
```

### MCP Protocol Compliance Tests

```python
def test_mcp_tool_schema_compliance():
    """Verify all tools follow MCP schema standards."""
    
    for server_name in ["worldbuilder", "worldviewer", "worldrecorder", "worldsurveyor"]:
        server = get_mcp_server(server_name)
        tools = server.list_tools()
        
        for tool in tools:
            # Check required fields
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            
            # Validate JSON schema
            jsonschema.validate(tool["inputSchema"], META_SCHEMA)
            
            # Check naming conventions
            assert tool["name"].startswith(f"{server_name}_")
            assert len(tool["description"]) >= 10
```

## End-to-End Integration Testing

### Multi-Server Workflow Tests

**Complete Scene Documentation Workflow:**
```python
@pytest.mark.asyncio
async def test_complete_documentation_workflow():
    """Test full AI agent workflow across all MCP servers."""
    
    # 1. WorldBuilder: Create documented scene
    building_elements = [
        {"element_type": "cube", "name": "foundation", "position": [0, 0, 0], "scale": [10, 10, 2]},
        {"element_type": "cube", "name": "walls", "position": [0, 0, 3], "scale": [10, 10, 4]},
        {"element_type": "cube", "name": "roof", "position": [0, 0, 6], "scale": [12, 12, 1]}
    ]
    
    await worldbuilder_create_batch({
        "batch_name": "documentation_building",
        "elements": building_elements
    })
    
    # 2. WorldSurveyor: Create inspection waypoints
    waypoint_group = await worldsurveyor_create_group({
        "name": "building_inspection",
        "description": "Documentation waypoints for building"
    })
    
    inspection_points = [
        {"name": "front_view", "position": [15, 0, 3], "type": "camera_position"},
        {"name": "side_view", "position": [0, 15, 3], "type": "camera_position"}, 
        {"name": "aerial_view", "position": [0, 0, 20], "type": "camera_position"},
        {"name": "roof_detail", "position": [0, 0, 8], "type": "point_of_interest"}
    ]
    
    created_waypoints = []
    for point in inspection_points:
        waypoint = await worldsurveyor_create_waypoint({
            "position": point["position"],
            "name": point["name"],
            "waypoint_type": point["type"]
        })
        created_waypoints.append(waypoint["waypoint_id"])
        
        await worldsurveyor_add_waypoint_to_groups({
            "waypoint_id": waypoint["waypoint_id"],
            "group_ids": [waypoint_group["group_id"]]
        })
    
    # 3. WorldViewer + WorldRecorder: Document each viewpoint
    documentation_files = []
    
    for waypoint_id in created_waypoints:
        # Navigate to waypoint
        await worldsurveyor_goto_waypoint({"waypoint_id": waypoint_id})
        
        # Wait for camera movement
        await asyncio.sleep(2)
        
        # Capture documentation
        waypoint_info = await worldsurveyor_list_waypoints()
        waypoint = next(w for w in waypoint_info["waypoints"] if w["id"] == waypoint_id)
        
        output_path = f"/tmp/building_doc_{waypoint['name']}.png"
        await worldrecorder_capture_frame({
            "output_path": output_path,
            "width": 2560,
            "height": 1440
        })
        
        documentation_files.append(output_path)
    
    # 4. Create overview video
    await worldrecorder_start_recording({
        "output_path": "/tmp/building_overview.mp4",
        "duration_sec": 20.0,
        "fps": 60
    })
    
    # Automated camera tour
    for waypoint_id in created_waypoints:
        await worldsurveyor_goto_waypoint({"waypoint_id": waypoint_id})
        await asyncio.sleep(4)  # Pause at each location
    
    await asyncio.sleep(2)  # Wait for recording completion
    
    # 5. Verification
    final_metrics = {
        "worldbuilder": await worldbuilder_get_metrics(),
        "worldviewer": await worldviewer_get_metrics(), 
        "worldrecorder": await worldrecorder_get_metrics(),
        "worldsurveyor": await worldsurveyor_get_metrics()
    }
    
    # Verify all files created
    assert all(os.path.exists(f) for f in documentation_files)
    assert os.path.exists("/tmp/building_overview.mp4")
    
    # Verify metrics show activity
    assert final_metrics["worldbuilder"]["elements_created"] >= 3
    assert final_metrics["worldviewer"]["camera_moves"] >= 4
    assert final_metrics["worldsurveyor"]["waypoint_count"] == 4
    
    # Cleanup
    await worldbuilder_clear_scene({"confirm": True})
    await worldsurveyor_clear_all_waypoints({"confirm": True})
    
    return {
        "documentation_files": documentation_files,
        "video_file": "/tmp/building_overview.mp4",
        "metrics": final_metrics
    }
```

### Cross-MCP Server Data Flow Tests

```python
@pytest.mark.asyncio
async def test_cross_server_data_consistency():
    """Test data consistency across MCP servers."""
    
    # Create object in WorldBuilder
    await worldbuilder_add_element({
        "element_type": "sphere",
        "name": "tracked_object",
        "position": [5, 5, 2],
        "color": [1, 0, 1]
    })
    
    # Get object bounds from WorldBuilder
    scene = await worldbuilder_get_scene()
    tracked_obj = next(e for e in scene["elements"] if e["name"] == "tracked_object")
    object_position = tracked_obj["position"]
    
    # Create waypoint at object location via WorldSurveyor  
    waypoint = await worldsurveyor_create_waypoint({
        "position": object_position,
        "name": "object_marker",
        "waypoint_type": "object_anchor"
    })
    
    # Frame object with WorldViewer
    await worldviewer_frame_object({
        "object_path": "/World/tracked_object",
        "distance": 10
    })
    
    camera_status = await worldviewer_get_camera_status()
    
    # Verify spatial consistency
    assert abs(camera_status["target"][0] - object_position[0]) < 0.1
    assert abs(camera_status["target"][1] - object_position[1]) < 0.1
    assert abs(camera_status["target"][2] - object_position[2]) < 0.1
    
    # Move object in WorldBuilder
    await worldbuilder_transform_asset({
        "prim_path": "/World/tracked_object",
        "position": [10, 10, 5]
    })
    
    # Update waypoint to match
    await worldsurveyor_update_waypoint({
        "waypoint_id": waypoint["waypoint_id"],
        "notes": "Moved to match object position"
    })
    
    # Re-frame with WorldViewer
    await worldviewer_frame_object({
        "object_path": "/World/tracked_object", 
        "distance": 10
    })
    
    updated_camera = await worldviewer_get_camera_status()
    
    # Verify updated consistency
    assert abs(updated_camera["target"][0] - 10.0) < 0.1
    assert abs(updated_camera["target"][1] - 10.0) < 0.1
    assert abs(updated_camera["target"][2] - 5.0) < 0.1
```

## Performance Testing

### Load Testing

```python
@pytest.mark.asyncio
async def test_concurrent_mcp_operations():
    """Test MCP servers under concurrent load."""
    
    async def create_batch_objects(batch_id: int):
        elements = [
            {
                "element_type": "cube",
                "name": f"load_test_cube_{batch_id}_{i}",
                "position": [batch_id * 10, i, 0],
                "scale": [1, 1, 1]
            }
            for i in range(10)
        ]
        
        return await worldbuilder_create_batch({
            "batch_name": f"load_test_batch_{batch_id}",
            "elements": elements
        })
    
    # Run 10 concurrent batch operations
    start_time = time.time()
    tasks = [create_batch_objects(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    # Verify all operations succeeded
    assert all(r["success"] for r in results)
    
    # Performance assertions
    assert elapsed < 30.0  # Should complete within 30 seconds
    assert len(results) == 10
    
    # Check final scene state
    final_scene = await worldbuilder_get_scene()
    assert len(final_scene["elements"]) == 100  # 10 batches × 10 elements
    
    # Performance metrics
    metrics = await worldbuilder_get_metrics()
    assert metrics["batches_created"] >= 10
    assert metrics["elements_created"] >= 100

@pytest.mark.asyncio
async def test_memory_usage_during_long_session():
    """Monitor memory usage during extended MCP operations."""
    import psutil
    import gc
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Perform 100 operations with cleanup
    for i in range(100):
        # Create objects
        await worldbuilder_add_element({
            "element_type": "sphere",
            "name": f"memory_test_{i}",
            "position": [i % 10, (i // 10) % 10, 0]
        })
        
        # Create waypoint
        waypoint = await worldsurveyor_create_waypoint({
            "position": [i % 10, (i // 10) % 10, 0],
            "name": f"waypoint_{i}"
        })
        
        # Move camera
        await worldviewer_set_camera_position({
            "position": [i % 10, (i // 10) % 10, 10],
            "target": [i % 10, (i // 10) % 10, 0]
        })
        
        # Take screenshot
        await worldrecorder_capture_frame({
            "output_path": f"/tmp/memory_test_{i}.png"
        })
        
        # Cleanup every 10 iterations
        if i % 10 == 9:
            await worldbuilder_clear_scene({"confirm": True})
            await worldsurveyor_clear_all_waypoints({"confirm": True})
            gc.collect()
    
    final_memory = process.memory_info().rss
    memory_growth = (final_memory - initial_memory) / 1024 / 1024  # MB
    
    # Memory growth should be reasonable
    assert memory_growth < 500  # Less than 500MB growth
    
    print(f"Memory growth: {memory_growth:.1f} MB")
```

### Latency Testing

```python
@pytest.mark.asyncio
async def test_mcp_response_times():
    """Measure and validate MCP server response times."""
    
    test_operations = [
        ("worldbuilder_scene_status", lambda: worldbuilder_scene_status()),
        ("worldviewer_get_camera_status", lambda: worldviewer_get_camera_status()),
        ("worldrecorder_get_status", lambda: worldrecorder_get_status()),
        ("worldsurveyor_list_waypoints", lambda: worldsurveyor_list_waypoints()),
    ]
    
    latencies = {}
    
    for op_name, operation in test_operations:
        times = []
        
        # Measure 10 operations
        for _ in range(10):
            start = time.time()
            await operation()
            elapsed = time.time() - start
            times.append(elapsed * 1000)  # Convert to ms
        
        latencies[op_name] = {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": sorted(times)[int(0.95 * len(times))],
            "max": max(times)
        }
    
    # Performance requirements
    for op_name, stats in latencies.items():
        assert stats["mean"] < 100.0, f"{op_name} mean latency too high: {stats['mean']:.1f}ms"
        assert stats["p95"] < 200.0, f"{op_name} P95 latency too high: {stats['p95']:.1f}ms"
        assert stats["max"] < 500.0, f"{op_name} max latency too high: {stats['max']:.1f}ms"
    
    print("Latency Results:")
    for op_name, stats in latencies.items():
        print(f"  {op_name}: {stats['mean']:.1f}ms avg, {stats['p95']:.1f}ms P95")
```

## Error Scenario Testing

### Fault Tolerance Tests

```python
@pytest.mark.asyncio
async def test_isaac_sim_connection_loss():
    """Test MCP server behavior when Isaac Sim becomes unavailable."""
    
    # Verify normal operation
    status = await worldbuilder_scene_status()
    assert status["success"] == True
    
    # Simulate Isaac Sim shutdown by stopping the service
    # (This would be done via external script/Docker in real testing)
    
    # Test graceful degradation
    with pytest.raises(ConnectionError):
        await worldbuilder_add_element({
            "element_type": "cube",
            "name": "should_fail",
            "position": [0, 0, 0]
        })
    
    # Verify server recovery after Isaac Sim restart
    # (Isaac Sim would be restarted via external script)
    
    # Test reconnection
    retry_count = 0
    max_retries = 10
    
    while retry_count < max_retries:
        try:
            status = await worldbuilder_scene_status()
            if status["success"]:
                break
        except:
            pass
        
        retry_count += 1
        await asyncio.sleep(2)
    
    assert retry_count < max_retries, "Server failed to reconnect after Isaac Sim restart"

@pytest.mark.asyncio
async def test_invalid_parameter_handling():
    """Test MCP server responses to invalid parameters."""
    
    invalid_test_cases = [
        # WorldBuilder invalid cases
        {
            "server": "worldbuilder",
            "operation": "add_element",
            "params": {"element_type": "nonexistent", "name": "bad", "position": [0, 0, 0]},
            "expected_error": "invalid_element_type"
        },
        {
            "server": "worldbuilder", 
            "operation": "add_element",
            "params": {"element_type": "cube", "name": "", "position": [0, 0, 0]},
            "expected_error": "empty_name"
        },
        {
            "server": "worldviewer",
            "operation": "set_camera_position", 
            "params": {"position": "not_a_list"},
            "expected_error": "invalid_position_format"
        },
        {
            "server": "worldsurveyor",
            "operation": "create_waypoint",
            "params": {"position": [0, 0], "name": "incomplete"},  # Missing Z coordinate
            "expected_error": "incomplete_position"
        }
    ]
    
    for test_case in invalid_test_cases:
        server_func = get_mcp_function(test_case["server"], test_case["operation"])
        
        try:
            result = await server_func(test_case["params"])
            # If no exception, check result contains error
            assert result["success"] == False
            assert test_case["expected_error"] in result.get("error", "").lower()
        except Exception as e:
            # Exception is acceptable for invalid parameters
            assert test_case["expected_error"] in str(e).lower()
```

### Security Testing

```python
@pytest.mark.asyncio
async def test_mcp_security_boundaries():
    """Test security controls in MCP servers."""
    
    # Test path traversal prevention
    malicious_paths = [
        "../../../etc/passwd",
        "/tmp/../../../home/user/.ssh/id_rsa",
        "\\..\\..\\windows\\system32\\config\\sam"
    ]
    
    for malicious_path in malicious_paths:
        result = await worldrecorder_capture_frame({
            "output_path": malicious_path
        })
        
        # Should either reject the path or sanitize it
        assert result["success"] == False or not malicious_path in result.get("output_path", "")
    
    # Test resource limits
    giant_batch = {
        "batch_name": "resource_exhaustion_attempt",
        "elements": [
            {"element_type": "cube", "name": f"cube_{i}", "position": [i, 0, 0]}
            for i in range(10000)  # Try to create 10k objects
        ]
    }
    
    result = await worldbuilder_create_batch(giant_batch)
    # Should be rejected or limited
    assert result["success"] == False or result.get("elements_created", 0) < 10000
    
    # Test authentication bypass attempts
    import aiohttp
    
    # Try to bypass auth with malformed headers
    malicious_headers = {
        "Authorization": "Bearer malicious_token",
        "X-Timestamp": "invalid_timestamp", 
        "X-Signature": "fake_signature"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "http://localhost:8899/scene", 
            headers=malicious_headers
        ) as response:
            # Should reject malicious auth attempts
            assert response.status in [401, 403]
```

## Automated Testing Pipeline

### CI/CD Integration

```yaml
# .github/workflows/mcp-testing.yml
name: MCP End-to-End Testing

on: [push, pull_request]

jobs:
  mcp-tests:
    runs-on: ubuntu-latest
    
    services:
      isaac-sim:
        image: nvcr.io/nvidia/isaac-sim:2024.1.1
        ports:
          - 8899:8899  # WorldBuilder
          - 8900:8900  # WorldViewer
          - 8891:8891  # WorldSurveyor
          - 8892:8892  # WorldRecorder
        options: >-
          --gpus all
          --health-cmd "curl -f http://localhost:8899/health"
          --health-interval 30s
          --health-timeout 10s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          # Install MCP servers
          cd mcp-servers
          for server in worldbuilder worldviewer worldrecorder worldsurveyor desktop-screenshot; do
            cd $server
            python -m venv venv
            source venv/bin/activate
            pip install -e .
            cd ..
          done
      
      - name: Wait for Isaac Sim
        run: |
          timeout 300s bash -c 'until curl -f http://localhost:8899/health; do sleep 5; done'
      
      - name: Run Unit Tests
        run: |
          cd mcp-servers
          python -m pytest tests/unit/ -v --asyncio-mode=auto
      
      - name: Run Component Tests  
        run: |
          cd mcp-servers
          python -m pytest tests/component/ -v --asyncio-mode=auto
      
      - name: Run E2E Tests
        run: |
          cd mcp-servers
          python -m pytest tests/e2e/ -v --asyncio-mode=auto --tb=short
      
      - name: Run Performance Tests
        run: |
          cd mcp-servers
          python -m pytest tests/performance/ -v --asyncio-mode=auto
      
      - name: Generate Test Report
        if: always()
        run: |
          python -m pytest --html=mcp-test-report.html --self-contained-html
      
      - name: Upload Test Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: mcp-test-report
          path: mcp-test-report.html
```

### Local Development Testing

```bash
#!/bin/bash
# scripts/run_mcp_tests.sh

set -e

echo "🧪 Running MCP End-to-End Tests"

# 1. Environment check
echo "📋 Checking environment..."
./scripts/check_isaac_sim_health.sh
./scripts/check_mcp_servers.sh

# 2. Unit tests
echo "🔧 Running unit tests..."
cd mcp-servers
python -m pytest tests/unit/ -v --tb=short

# 3. Component tests
echo "🏗️ Running component tests..."
python -m pytest tests/component/ -v --tb=short

# 4. E2E tests  
echo "🌐 Running E2E tests..."
python -m pytest tests/e2e/ -v --tb=short

# 5. Performance tests
echo "⚡ Running performance tests..."
python -m pytest tests/performance/ -v --tb=short

# 6. Security tests
echo "🔒 Running security tests..."
python -m pytest tests/security/ -v --tb=short

echo "✅ All MCP tests completed successfully!"

# Generate metrics report
python scripts/generate_test_metrics.py > test-metrics.json
echo "📊 Test metrics saved to test-metrics.json"
```

## Monitoring & Observability

### Test Metrics Collection

```python
# scripts/generate_test_metrics.py
import asyncio
import json
from datetime import datetime

async def collect_mcp_metrics():
    """Collect comprehensive metrics from all MCP servers."""
    
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "test_run_id": generate_test_run_id(),
        "servers": {}
    }
    
    # Collect metrics from each server
    for server_name in ["worldbuilder", "worldviewer", "worldrecorder", "worldsurveyor"]:
        server_metrics = await get_mcp_server_metrics(server_name)
        metrics["servers"][server_name] = server_metrics
    
    # Calculate aggregate metrics
    metrics["aggregate"] = {
        "total_requests": sum(s.get("requests_received", 0) for s in metrics["servers"].values()),
        "total_errors": sum(s.get("errors", 0) for s in metrics["servers"].values()),
        "avg_uptime": sum(s.get("uptime_seconds", 0) for s in metrics["servers"].values()) / len(metrics["servers"]),
        "success_rate": calculate_success_rate(metrics["servers"])
    }
    
    return metrics

def generate_dashboard_data():
    """Generate data for MCP testing dashboard."""
    
    return {
        "test_status": get_latest_test_results(),
        "performance_trends": get_performance_trends(),
        "error_patterns": analyze_error_patterns(),
        "coverage_metrics": get_test_coverage_metrics()
    }
```

### Continuous Monitoring

```python
# monitoring/mcp_health_monitor.py
import asyncio
import logging
from datetime import datetime, timedelta

class MCPHealthMonitor:
    """Continuous health monitoring for MCP servers."""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.health_history = []
        self.alert_thresholds = {
            "response_time_ms": 1000,
            "error_rate": 0.05,
            "uptime_hours": 24
        }
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        
        while True:
            try:
                health_check = await self.perform_health_check()
                self.health_history.append(health_check)
                
                # Check for alerts
                await self.check_alerts(health_check)
                
                # Cleanup old history
                cutoff = datetime.utcnow() - timedelta(hours=24)
                self.health_history = [h for h in self.health_history if h["timestamp"] > cutoff]
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def perform_health_check(self):
        """Perform comprehensive health check."""
        
        health_data = {
            "timestamp": datetime.utcnow(),
            "servers": {},
            "overall_health": True
        }
        
        for server_name in ["worldbuilder", "worldviewer", "worldrecorder", "worldsurveyor"]:
            try:
                server_health = await self.check_server_health(server_name)
                health_data["servers"][server_name] = server_health
                
                if not server_health["healthy"]:
                    health_data["overall_health"] = False
                    
            except Exception as e:
                health_data["servers"][server_name] = {
                    "healthy": False,
                    "error": str(e)
                }
                health_data["overall_health"] = False
        
        return health_data
    
    async def check_alerts(self, health_data):
        """Check if any alert conditions are met."""
        
        for server_name, server_health in health_data["servers"].items():
            if not server_health.get("healthy", False):
                await self.send_alert(f"Server {server_name} is unhealthy", server_health)
            
            response_time = server_health.get("response_time_ms", 0)
            if response_time > self.alert_thresholds["response_time_ms"]:
                await self.send_alert(f"High response time for {server_name}: {response_time}ms")
    
    async def send_alert(self, message: str, details=None):
        """Send alert notification."""
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "details": details
        }
        
        logging.error(f"MCP ALERT: {message}")
        
        # In production, send to monitoring system
        # await send_to_monitoring_system(alert)
```

## Test Documentation & Reporting

### Test Result Analysis

```python
def analyze_test_results(test_results_dir: str) -> dict:
    """Analyze test results and generate insights."""
    
    analysis = {
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "success_rate": 0.0
        },
        "performance": {
            "avg_test_duration": 0.0,
            "slowest_tests": [],
            "fastest_tests": []
        },
        "failure_analysis": {
            "common_failures": [],
            "server_specific_issues": {},
            "recommendations": []
        }
    }
    
    # Parse test results from pytest JSON reports
    test_files = glob.glob(f"{test_results_dir}/*.json")
    
    for test_file in test_files:
        with open(test_file) as f:
            results = json.load(f)
            
        # Aggregate statistics
        analysis["summary"]["total_tests"] += len(results["tests"])
        analysis["summary"]["passed"] += len([t for t in results["tests"] if t["outcome"] == "passed"])
        analysis["summary"]["failed"] += len([t for t in results["tests"] if t["outcome"] == "failed"])
        
        # Performance analysis
        durations = [t["duration"] for t in results["tests"]]
        analysis["performance"]["avg_test_duration"] = sum(durations) / len(durations)
        
        # Failure pattern analysis
        failed_tests = [t for t in results["tests"] if t["outcome"] == "failed"]
        for failed_test in failed_tests:
            failure_category = categorize_failure(failed_test["longrepr"])
            analysis["failure_analysis"]["common_failures"].append(failure_category)
    
    # Calculate success rate
    total = analysis["summary"]["total_tests"]
    passed = analysis["summary"]["passed"]
    analysis["summary"]["success_rate"] = (passed / total) * 100 if total > 0 else 0
    
    return analysis

def generate_test_report(analysis: dict) -> str:
    """Generate comprehensive test report."""
    
    report = f"""
# MCP Testing Report - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Executive Summary

- **Total Tests:** {analysis['summary']['total_tests']}
- **Success Rate:** {analysis['summary']['success_rate']:.1f}%
- **Passed:** {analysis['summary']['passed']}
- **Failed:** {analysis['summary']['failed']}
- **Average Duration:** {analysis['performance']['avg_test_duration']:.2f}s

## Performance Analysis

### Response Time Metrics
"""
    
    # Add detailed sections based on analysis
    if analysis['summary']['failed'] > 0:
        report += "\n## Failure Analysis\n\n"
        for failure in analysis['failure_analysis']['common_failures']:
            report += f"- {failure}\n"
    
    report += "\n## Recommendations\n\n"
    recommendations = generate_recommendations(analysis)
    for rec in recommendations:
        report += f"- {rec}\n"
    
    return report
```

## Best Practices & Guidelines

### Test Development Guidelines

1. **Test Isolation**: Each test should be independent and not rely on state from other tests
2. **Cleanup**: Always clean up resources (scenes, waypoints, files) after tests
3. **Async Patterns**: Use proper async/await patterns for MCP operations
4. **Error Validation**: Test both success and failure scenarios
5. **Performance Bounds**: Set reasonable performance expectations and test against them

### Test Organization

```
tests/
├── unit/
│   ├── test_worldbuilder_tools.py
│   ├── test_worldviewer_camera.py
│   ├── test_authentication.py
│   └── test_validation.py
├── component/
│   ├── test_worldbuilder_integration.py
│   ├── test_worldrecorder_capture.py
│   └── test_cross_server_consistency.py
├── e2e/
│   ├── test_documentation_workflow.py
│   ├── test_scene_creation_pipeline.py
│   └── test_multi_agent_scenarios.py
├── performance/
│   ├── test_load_testing.py
│   ├── test_memory_usage.py
│   └── test_response_times.py
├── security/
│   ├── test_auth_boundaries.py
│   ├── test_input_validation.py
│   └── test_resource_limits.py
└── fixtures/
    ├── scene_templates.py
    ├── test_data.py
    └── mock_servers.py
```

### Continuous Improvement

1. **Regular Test Reviews**: Review and update tests as MCP servers evolve
2. **Performance Baselines**: Establish and maintain performance baselines
3. **Test Metrics**: Track test execution metrics and trends
4. **Feedback Loops**: Incorporate user feedback into test scenarios
5. **Documentation**: Keep test documentation current with implementation changes

This comprehensive testing workflow ensures reliable, performant MCP servers that provide consistent AI agent experiences across the Agent World ecosystem.
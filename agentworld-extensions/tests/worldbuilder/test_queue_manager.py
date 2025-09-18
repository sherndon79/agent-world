from collections import deque

import pytest

from omni.agent.worldbuilder.scene.queue_manager import WorldBuilderQueueManager
from omni.agent.worldbuilder.scene.scene_types import (
    PrimitiveType,
    SceneElement,
    AssetPlacement,
)


class DummyConfig:
    max_completed_requests = 20
    max_operations_per_cycle = 2


@pytest.fixture
def queue_manager():
    return WorldBuilderQueueManager(config=DummyConfig())


def _success(**payload):
    return {"success": True, **payload}


def test_process_queues_respects_operation_limit(queue_manager):
    names = ["alpha", "beta", "gamma"]
    for name in names:
        queue_manager.add_element_request(
            SceneElement(name=name, primitive_type=PrimitiveType.CUBE)
        )

    processed = []

    def element_processor(element):
        processed.append(element.name)
        return _success(result=element.name)

    queue_manager.process_queues(
        element_processor,
        lambda *args, **kwargs: _success(),
        lambda *args, **kwargs: _success(),
        lambda *args, **kwargs: _success(),
    )

    assert processed == ["alpha", "beta"], "only two operations should run per cycle"
    assert len(queue_manager._element_queue) == 1
    assert queue_manager._stats["queued_elements"] == 1


def test_process_queues_handles_batch_and_asset_requests(queue_manager):
    queue_manager.add_batch_request("test_batch", [
        {"element_type": "cube"},
    ])
    queue_manager.add_asset_request(
        AssetPlacement(
            name="asset1",
            asset_path="/tmp/asset.usd",
            prim_path="/World/asset1",
        ),
        "asset",
    )

    batches = []
    assets = []

    result = queue_manager.process_queues(
        lambda *_: _success(),
        lambda name, elements, transform: batches.append((name, elements)) or _success(),
        lambda request_type, *args, **kwargs: assets.append(request_type) or _success(),
        lambda *_: _success(),
    )

    assert result['processed_count'] == 2
    assert result['queue_lengths']['batches'] == 0
    assert result['queue_lengths']['assets'] == 0
    assert batches and batches[0][0] == "test_batch"
    assert assets and assets[0] == 'place'


def test_queue_manager_respects_config_fallback():
    # Ensure fallback to global loader when config not provided
    qm = WorldBuilderQueueManager(config=None)

    calls = deque()

    def element_processor(element):
        calls.append(element.name)
        return _success()

    qm.add_element_request(SceneElement(name="solo", primitive_type=PrimitiveType.CUBE))

    qm.process_queues(
        element_processor,
        lambda *_: _success(),
        lambda *_: _success(),
        lambda *_: _success(),
    )

    assert list(calls) == ["solo"]

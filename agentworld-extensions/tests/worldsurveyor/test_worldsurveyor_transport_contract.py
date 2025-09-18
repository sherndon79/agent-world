from __future__ import annotations

import inspect

from omni.agent.worldsurveyor.http.controller import WorldSurveyorController
from omni.agent.worldsurveyor.transport import TOOL_CONTRACTS


def test_contract_operations_exist_on_controller():
    controller_methods = {
        name for name, value in inspect.getmembers(WorldSurveyorController, predicate=inspect.isfunction)
    }
    missing = [contract.operation for contract in TOOL_CONTRACTS if contract.operation not in controller_methods]
    assert not missing, f"Controller missing operations: {missing}"

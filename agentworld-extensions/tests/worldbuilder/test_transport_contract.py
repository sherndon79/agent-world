import inspect

from omni.agent.worldbuilder.http.controller import WorldBuilderController
from omni.agent.worldbuilder.transport.contract import TOOL_CONTRACTS


def test_contract_operations_exist_in_controller():
    controller_methods = {
        name for name, value in inspect.getmembers(WorldBuilderController, predicate=inspect.isfunction)
    }
    missing = [contract.operation for contract in TOOL_CONTRACTS if contract.operation not in controller_methods]
    assert not missing, f"Controller missing operations: {missing}"

import omni.kit.capture.viewport as vcap

# Get the capture instance
inst = vcap.CaptureExtension.get_instance()

# Check available methods
print("Available methods on CaptureExtension instance:")
for attr in dir(inst):
    if not attr.startswith('_'):
        print(f"  {attr}: {type(getattr(inst, attr))}")

# Check if there are different stop/cancel methods
print(f"\nHas 'stop' method: {hasattr(inst, 'stop')}")
print(f"Has 'cancel' method: {hasattr(inst, 'cancel')}")
print(f"Has 'finish' method: {hasattr(inst, 'finish')}")
print(f"Has 'complete' method: {hasattr(inst, 'complete')}")

# Check current state
print(f"\nCurrent state:")
print(f"  done: {getattr(inst, 'done', 'N/A')}")
print(f"  outputs: {inst.get_outputs() if hasattr(inst, 'get_outputs') else 'N/A'}")
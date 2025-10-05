#!/usr/bin/env python3
"""
Prune unwanted sci-fi samples based on user feedback.
"""

import json
import shutil
from pathlib import Path

# Samples to prune
PRUNE_LIST = [
    "sonniss2024/scifi/scifi_0000.wav",  # Tractor engine
    "sonniss2024/scifi/scifi_0001.wav",  # GEODRONE too loud
    "sonniss2024/scifi/scifi_0003.wav",  # GEODRONE loud/high freq
    "sonniss2024/scifi/scifi_0007.wav",  # Painful texture
    "sonniss2024/scifi/scifi_0010.wav",  # Clock tick (SFX not ambient)
    "sonniss2024/scifi/scifi_0025.wav",  # Short beep
    "signature_soundbank/scifi/scifi_0008.wav",  # Quick ding
    "signature_soundbank/scifi/scifi_0009.wav",  # Cello stab
    "signature_soundbank/scifi/scifi_0011.wav",  # Cello stab
    "signature_soundbank/scifi/scifi_0012.wav",  # Cello stab
]

LIBRARY_ROOT = Path('/home/sherndon/agent-world/docker/audio-generator/assets/ambient/library')

def prune_samples():
    """Remove pruned samples and update manifests"""

    for pack in ["sonniss2024", "signature_soundbank"]:
        pack_dir = LIBRARY_ROOT / pack
        manifest_path = pack_dir / 'manifest.json'

        if not manifest_path.exists():
            continue

        # Load manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Filter out pruned entries
        original_count = len(manifest)
        manifest = [entry for entry in manifest if entry['id'] not in PRUNE_LIST]
        pruned_count = original_count - len(manifest)

        # Delete physical files
        for sample_id in PRUNE_LIST:
            if sample_id.startswith(f"{pack}/"):
                file_path = LIBRARY_ROOT / sample_id.replace(f"{pack}/", "")
                if file_path.exists():
                    file_path.unlink()
                    print(f"  ✗ Deleted: {sample_id}")

        # Save updated manifest
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        if pruned_count > 0:
            print(f"\n✅ {pack}: Pruned {pruned_count} samples, {len(manifest)} remain")

if __name__ == "__main__":
    print("🗑️  Pruning unwanted sci-fi samples...\n")
    prune_samples()
    print("\n✅ Pruning complete!")

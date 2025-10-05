#!/usr/bin/env python3
"""
Extract sci-fi samples from Signature Soundbank (nested zips).
"""

import zipfile
import json
import shutil
from pathlib import Path
import soundfile as sf

# Paths
SIGNATURE_ZIP = Path('/mnt/net-shares/samba/Seth-XPS-8960_100425/ambient/Signature Soundbank Update 1.zip')
LIBRARY_ROOT = Path('/home/sherndon/agent-world/docker/audio-generator/assets/ambient/library')
TEMP_DIR = Path('/tmp/signature_extract')

# Target packs that might have sci-fi sounds
TARGET_PACKS = [
    'Experimental Atmospheres 01.zip',
    'SignatureSamples.Co.Uk Ghost Choir Atmospheres.zip',
    'SignatureSamples.Co.Uk Cello Synth Stabs.zip',
    '42596__mielitietty__casio-pt-31-zoom-9030-sounds.zip'
]

def extract_signature_scifi():
    """Extract sci-fi samples from Signature Soundbank"""
    print("\n" + "="*80)
    print("EXTRACTING SCI-FI SAMPLES FROM SIGNATURE SOUNDBANK")
    print("="*80 + "\n")

    # Create signature_soundbank directory
    sig_dir = LIBRARY_ROOT / 'signature_soundbank'
    scifi_dir = sig_dir / 'scifi'
    scifi_dir.mkdir(parents=True, exist_ok=True)

    # Load existing manifest or create new
    manifest_path = sig_dir / 'manifest.json'
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    else:
        manifest = []

    # Track current count
    existing_scifi = [e for e in manifest if e['category'] == 'scifi']
    extracted_count = len(existing_scifi)

    new_entries = []
    TEMP_DIR.mkdir(exist_ok=True)

    try:
        # Open outer zip
        with zipfile.ZipFile(SIGNATURE_ZIP, 'r') as outer_zip:
            print("Opened Signature Soundbank outer zip")

            # Process each target pack
            for pack_name in TARGET_PACKS:
                pack_path = f"Signature Soundbank Update 1/{pack_name}"

                if pack_path not in outer_zip.namelist():
                    print(f"  ⚠ {pack_name} not found in archive")
                    continue

                print(f"\nProcessing {pack_name}...")

                # Extract inner zip to temp
                inner_zip_path = TEMP_DIR / pack_name
                with open(inner_zip_path, 'wb') as f:
                    f.write(outer_zip.read(pack_path))

                # Open inner zip
                try:
                    with zipfile.ZipFile(inner_zip_path, 'r') as inner_zip:
                        file_list = inner_zip.namelist()

                        # Filter for audio files
                        audio_files = [f for f in file_list if f.lower().endswith(('.wav', '.mp3', '.ogg', '.flac'))]

                        print(f"  Found {len(audio_files)} audio files")

                        # Extract up to 5 samples per pack
                        for i, filename in enumerate(audio_files[:5]):
                            try:
                                # Extract to temp
                                inner_zip.extract(filename, TEMP_DIR)
                                extracted_file = TEMP_DIR / filename

                                # Output path
                                output_path = scifi_dir / f"scifi_{extracted_count:04d}.wav"

                                # Convert to WAV if needed
                                if extracted_file.suffix.lower() == '.wav':
                                    shutil.copy(extracted_file, output_path)
                                else:
                                    data, sr = sf.read(str(extracted_file))
                                    sf.write(str(output_path), data, sr, format='WAV')

                                # Get audio info
                                info = sf.info(str(output_path))

                                # Determine tags based on pack name
                                tags = ['scifi']
                                if 'atmosphere' in pack_name.lower():
                                    tags.append('atmosphere')
                                if 'synth' in pack_name.lower():
                                    tags.append('synth')
                                if 'drone' in pack_name.lower() or 'casio' in pack_name.lower():
                                    tags.append('electronic')

                                # Create manifest entry
                                entry = {
                                    "id": f"signature_soundbank/scifi/scifi_{extracted_count:04d}.wav",
                                    "category": "scifi",
                                    "source": f"{pack_name}/{filename}",
                                    "tags": tags,
                                    "duration_seconds": info.duration,
                                    "sample_rate": info.samplerate,
                                    "channels": info.channels
                                }

                                new_entries.append(entry)
                                extracted_count += 1

                                print(f"    ✓ {Path(filename).name} ({info.duration:.1f}s)")

                            except Exception as e:
                                print(f"    ✗ Failed: {Path(filename).name}: {e}")
                                continue

                except Exception as e:
                    print(f"  ✗ Failed to open {pack_name}: {e}")

                # Clean up inner zip
                if inner_zip_path.exists():
                    inner_zip_path.unlink()

    finally:
        # Clean up temp directory
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)

    # Update manifest
    manifest.extend(new_entries)

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✅ Extracted {len(new_entries)} sci-fi samples from Signature Soundbank")
    print(f"✅ Updated manifest with {len(new_entries)} new entries")

    return len(new_entries)


if __name__ == "__main__":
    print("🚀 Signature Soundbank Sci-Fi Extraction")
    count = extract_signature_scifi()
    print(f"\n✅ Total extracted: {count}")

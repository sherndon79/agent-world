#!/usr/bin/env python3
"""
Extract sci-fi samples from zip archives and update manifests.
"""

import zipfile
import json
import shutil
from pathlib import Path
from collections import defaultdict
import soundfile as sf

# Paths
ZIP_DIR = Path('/mnt/net-shares/samba/Seth-XPS-8960_100425/ambient/')
LIBRARY_ROOT = Path('/home/sherndon/agent-world/docker/audio-generator/assets/ambient/library')

# Sci-fi keywords (prioritized)
SCIFI_PRIORITY_KEYWORDS = [
    'spaceship', 'spacecraft', 'alien', 'drone', 'hum',
    'synth', 'sci-fi', 'scifi', 'futuristic'
]

SCIFI_SECONDARY_KEYWORDS = [
    'space', 'engine', 'electronic', 'atmosphere', 'atmos',
    'texture', 'ambient', 'laser', 'beam'
]

def is_scifi_sample(filename: str) -> tuple[bool, list[str]]:
    """Check if filename suggests sci-fi content"""
    filename_lower = filename.lower()

    # Skip non-audio files
    if not filename_lower.endswith(('.wav', '.mp3', '.ogg', '.flac')):
        return False, []

    # Find matching keywords
    matched_keywords = []

    # Priority keywords (high confidence sci-fi)
    for keyword in SCIFI_PRIORITY_KEYWORDS:
        if keyword in filename_lower:
            matched_keywords.append(keyword)

    # Secondary keywords (might be sci-fi)
    for keyword in SCIFI_SECONDARY_KEYWORDS:
        if keyword in filename_lower:
            matched_keywords.append(keyword)

    # Must have at least one keyword match
    if matched_keywords:
        return True, matched_keywords

    return False, []


def extract_scifi_from_sonniss():
    """Extract sci-fi samples from Sonniss GDC bundles"""
    print("\n" + "="*80)
    print("EXTRACTING SCI-FI SAMPLES FROM SONNISS GDC 2024 BUNDLES")
    print("="*80 + "\n")

    sonniss_dir = LIBRARY_ROOT / 'sonniss2024'
    scifi_dir = sonniss_dir / 'scifi'
    scifi_dir.mkdir(exist_ok=True)

    # Load existing manifest
    manifest_path = sonniss_dir / 'manifest.json'
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    # Track extracted files
    extracted_count = 0
    new_entries = []

    # Process each Sonniss bundle
    sonniss_zips = sorted(ZIP_DIR.glob('Sonniss.com-GDC2024-GameAudioBundle*.zip'))

    for zip_path in sonniss_zips:
        print(f"Processing {zip_path.name}...")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                file_list = zf.namelist()

                for filename in file_list:
                    is_scifi, keywords = is_scifi_sample(filename)

                    if is_scifi:
                        # Extract to scifi directory
                        basename = Path(filename).name
                        output_path = scifi_dir / f"scifi_{extracted_count:04d}.wav"

                        # Extract file
                        try:
                            zf.extract(filename, '/tmp/scifi_extract')
                            extracted_file = Path('/tmp/scifi_extract') / filename

                            # Convert to WAV if needed, copy if already WAV
                            if extracted_file.suffix.lower() == '.wav':
                                shutil.copy(extracted_file, output_path)
                            else:
                                # Convert using soundfile
                                data, sr = sf.read(str(extracted_file))
                                sf.write(str(output_path), data, sr, format='WAV')

                            # Get audio info
                            info = sf.info(str(output_path))

                            # Create manifest entry
                            entry = {
                                "id": f"sonniss2024/scifi/scifi_{extracted_count:04d}.wav",
                                "category": "scifi",
                                "source": filename,
                                "tags": ["scifi"] + keywords[:5],  # Limit tags
                                "duration_seconds": info.duration,
                                "sample_rate": info.samplerate,
                                "channels": info.channels
                            }

                            new_entries.append(entry)
                            extracted_count += 1

                            print(f"  ✓ Extracted: {basename} ({info.duration:.1f}s)")

                            # Clean up temp file
                            shutil.rmtree('/tmp/scifi_extract')

                            # Limit to 30 samples to avoid overwhelming
                            if extracted_count >= 30:
                                break

                        except Exception as e:
                            print(f"  ✗ Failed to extract {basename}: {e}")
                            continue

                if extracted_count >= 30:
                    break

        except Exception as e:
            print(f"  ✗ Error reading {zip_path.name}: {e}")

    # Update manifest
    manifest.extend(new_entries)

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✅ Extracted {extracted_count} sci-fi samples to sonniss2024/scifi/")
    print(f"✅ Updated manifest with {len(new_entries)} new entries")

    return extracted_count


def main():
    """Main function"""
    print("🚀 Sci-Fi Sample Extraction Tool")

    # Extract from Sonniss bundles
    sonniss_count = extract_scifi_from_sonniss()

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"\nTotal sci-fi samples extracted: {sonniss_count}")
    print("\nYou can now use these samples in your audio-generator!")
    print('Example: {"sample_id": "sonniss2024/scifi/scifi_0000.wav"}')


if __name__ == "__main__":
    main()

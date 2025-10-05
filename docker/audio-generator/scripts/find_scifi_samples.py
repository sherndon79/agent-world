#!/usr/bin/env python3
"""
Find sci-fi/space-themed audio samples in zip archives.

Searches for keywords in filenames and categorizes them.
"""

import zipfile
import re
from pathlib import Path
from collections import defaultdict

# Sci-fi related keywords to search for
SCIFI_KEYWORDS = [
    'space', 'scifi', 'sci-fi', 'spacecraft', 'spaceship', 'alien',
    'futuristic', 'synth', 'drone', 'engine', 'hum', 'electronic',
    'laser', 'beam', 'warp', 'hyperdrive', 'reactor', 'computer',
    'robot', 'android', 'cyborg', 'mech', 'servo', 'mechanical',
    'station', 'satellite', 'orbit', 'atmosphere', 'airlock',
    'cockpit', 'bridge', 'console', 'ambient', 'pad', 'texture',
    'atmos', 'sfx'
]

def search_zip_for_scifi(zip_path: Path) -> dict:
    """
    Search a zip file for sci-fi samples.

    Returns:
        dict: Categorized results
    """
    results = defaultdict(list)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            file_list = zf.namelist()

            for filename in file_list:
                # Only process audio files
                if not filename.lower().endswith(('.wav', '.mp3', '.ogg', '.flac')):
                    continue

                filename_lower = filename.lower()

                # Check for sci-fi keywords
                matched_keywords = []
                for keyword in SCIFI_KEYWORDS:
                    if keyword in filename_lower:
                        matched_keywords.append(keyword)

                if matched_keywords:
                    # Categorize based on keywords
                    category = 'misc'

                    if any(k in matched_keywords for k in ['space', 'spacecraft', 'spaceship', 'station']):
                        category = 'space'
                    elif any(k in matched_keywords for k in ['engine', 'hum', 'reactor', 'drone']):
                        category = 'mechanical'
                    elif any(k in matched_keywords for k in ['alien', 'creature']):
                        category = 'alien'
                    elif any(k in matched_keywords for k in ['ambient', 'pad', 'texture', 'atmos']):
                        category = 'ambient'
                    elif any(k in matched_keywords for k in ['laser', 'beam', 'weapon']):
                        category = 'weapons'
                    elif any(k in matched_keywords for k in ['computer', 'console', 'interface']):
                        category = 'interface'

                    results[category].append({
                        'filename': filename,
                        'keywords': matched_keywords,
                        'size': zf.getinfo(filename).file_size
                    })

    except Exception as e:
        print(f"Error reading {zip_path.name}: {e}")

    return results


def main():
    """Main function"""
    zip_dir = Path('/mnt/net-shares/samba/Seth-XPS-8960_100425/ambient/')

    # Find all zip files
    zip_files = sorted(zip_dir.glob('*.zip'))

    print(f"Found {len(zip_files)} zip files to search\n")

    all_results = defaultdict(lambda: defaultdict(list))

    for zip_path in zip_files:
        print(f"Searching {zip_path.name}...")
        results = search_zip_for_scifi(zip_path)

        total_matches = sum(len(files) for files in results.values())
        if total_matches > 0:
            print(f"  ✓ Found {total_matches} sci-fi samples")
            for category, files in results.items():
                all_results[zip_path.name][category].extend(files)
        else:
            print(f"  - No matches")

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY BY PACK AND CATEGORY")
    print("="*80 + "\n")

    for pack_name, categories in sorted(all_results.items()):
        print(f"\n📦 {pack_name}")
        print("-" * 80)

        for category, files in sorted(categories.items()):
            print(f"\n  {category.upper()} ({len(files)} files):")

            # Show first 5 examples
            for i, file_info in enumerate(files[:5]):
                size_mb = file_info['size'] / (1024 * 1024)
                keywords = ', '.join(file_info['keywords'][:3])
                filename = Path(file_info['filename']).name
                print(f"    {i+1}. {filename} ({size_mb:.2f} MB) - [{keywords}]")

            if len(files) > 5:
                print(f"    ... and {len(files) - 5} more")

    # Print total summary
    print("\n" + "="*80)
    print("TOTAL SUMMARY")
    print("="*80)

    total_files = 0
    category_totals = defaultdict(int)

    for pack_name, categories in all_results.items():
        for category, files in categories.items():
            category_totals[category] += len(files)
            total_files += len(files)

    print(f"\nTotal sci-fi samples found: {total_files}")
    print("\nBy category:")
    for category, count in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")


if __name__ == "__main__":
    main()

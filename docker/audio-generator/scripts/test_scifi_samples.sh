#!/bin/bash
# Interactive script to test sci-fi ambient samples one by one

echo "🎧 Sci-Fi Ambient Sample Tester"
echo "================================"
echo ""
echo "This will play each sci-fi sample for you to evaluate."
echo "Press ENTER after each sample to continue to the next one."
echo ""

# Get all scifi samples from both packs
samples=(
  # Sonniss samples
  "sonniss2024/scifi/scifi_0000.wav"
  "sonniss2024/scifi/scifi_0001.wav"
  "sonniss2024/scifi/scifi_0002.wav"
  "sonniss2024/scifi/scifi_0003.wav"
  "sonniss2024/scifi/scifi_0004.wav"
  "sonniss2024/scifi/scifi_0005.wav"
  "sonniss2024/scifi/scifi_0006.wav"
  "sonniss2024/scifi/scifi_0007.wav"
  "sonniss2024/scifi/scifi_0008.wav"
  "sonniss2024/scifi/scifi_0009.wav"
  "sonniss2024/scifi/scifi_0010.wav"
  "sonniss2024/scifi/scifi_0011.wav"
  "sonniss2024/scifi/scifi_0012.wav"
  "sonniss2024/scifi/scifi_0013.wav"
  "sonniss2024/scifi/scifi_0014.wav"
  "sonniss2024/scifi/scifi_0015.wav"
  "sonniss2024/scifi/scifi_0016.wav"
  "sonniss2024/scifi/scifi_0017.wav"
  "sonniss2024/scifi/scifi_0018.wav"
  "sonniss2024/scifi/scifi_0019.wav"
  "sonniss2024/scifi/scifi_0020.wav"
  "sonniss2024/scifi/scifi_0021.wav"
  "sonniss2024/scifi/scifi_0022.wav"
  "sonniss2024/scifi/scifi_0023.wav"
  "sonniss2024/scifi/scifi_0024.wav"
  "sonniss2024/scifi/scifi_0025.wav"
  "sonniss2024/scifi/scifi_0026.wav"
  "sonniss2024/scifi/scifi_0027.wav"
  "sonniss2024/scifi/scifi_0028.wav"
  "sonniss2024/scifi/scifi_0029.wav"
  # Signature Soundbank samples
  "signature_soundbank/scifi/scifi_0000.wav"
  "signature_soundbank/scifi/scifi_0001.wav"
  "signature_soundbank/scifi/scifi_0002.wav"
  "signature_soundbank/scifi/scifi_0003.wav"
  "signature_soundbank/scifi/scifi_0004.wav"
  "signature_soundbank/scifi/scifi_0005.wav"
  "signature_soundbank/scifi/scifi_0008.wav"
  "signature_soundbank/scifi/scifi_0009.wav"
  "signature_soundbank/scifi/scifi_0010.wav"
  "signature_soundbank/scifi/scifi_0011.wav"
  "signature_soundbank/scifi/scifi_0012.wav"
  "signature_soundbank/scifi/scifi_0013.wav"
  "signature_soundbank/scifi/scifi_0014.wav"
  "signature_soundbank/scifi/scifi_0015.wav"
  "signature_soundbank/scifi/scifi_0016.wav"
  "signature_soundbank/scifi/scifi_0017.wav"
)

count=1
total=${#samples[@]}

for sample in "${samples[@]}"; do
  echo ""
  echo "[$count/$total] Testing: $sample"

  # Get sample info from manifest
  pack=$(echo $sample | cut -d'/' -f1)

  # Play the sample
  curl -s -X POST http://localhost:8080/api/ambient \
    -H "Content-Type: application/json" \
    -d "{
      \"data\": {
        \"sample_id\": \"$sample\",
        \"fade_out_after\": 10,
        \"fade_duration\": 1.0
      }
    }" | jq -r '.request_id' > /dev/null

  echo "  ▶ Playing... (will fade out after 10s)"
  echo ""
  echo "  Keep? (y/n/skip): "
  read -r response

  if [[ "$response" == "y" ]]; then
    echo "  ✓ Marked as KEEP"
    echo "$sample" >> /tmp/scifi_keep.txt
  elif [[ "$response" == "n" ]]; then
    echo "  ✗ Marked as REMOVE"
    echo "$sample" >> /tmp/scifi_remove.txt
  else
    echo "  - Skipped"
  fi

  count=$((count + 1))
done

echo ""
echo "================================"
echo "Testing complete!"
echo ""
echo "KEEP list: /tmp/scifi_keep.txt"
echo "REMOVE list: /tmp/scifi_remove.txt"

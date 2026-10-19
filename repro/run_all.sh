#!/usr/bin/env bash
# Run a jpylyzer checkout on every repro file; usage: run_all.sh <jpylyzer dir> <files dir> <out dir>
jpylyzer=$1; files=$2; out=$3
mkdir -p "$out"
for f in "$files"/*; do
  name=$(basename "$f"); format=${name##*.}
  start=$(date +%s.%N)
  timeout 20 python3 "$jpylyzer/cli.py" --verbose --packetmarkers --format $format "$f" > "$out/$name.xml" 2> "$out/$name.err"
  rc=$?
  elapsed=$(echo "$(date +%s.%N) - $start" | bc)
  success=$(grep -oP '<success>\K\w+' "$out/$name.xml" | head -1)
  valid=$(grep -oP '<isValid[^>]*>\K\w+' "$out/$name.xml" | head -1)
  printf "%-45s rc=%-3s t=%5.1fs success=%-5s valid=%s\n" "$name" "$rc" "$elapsed" "$success" "$valid"
done

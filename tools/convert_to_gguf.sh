#!/usr/bin/env bash
# ============================================================================
# convert_to_gguf.sh — Convert RavenX-Sec MLX model to GGUF for Ollama/LM Studio
# Run this on the M4 Max (128GB)
# ============================================================================
set -euo pipefail

MODEL_DIR="$HOME/Developer/RavenX-Sec/models/checkpoints/ravenx-sec-fused-v2.0-fp16"
REPO_GGUF="deadbydawn101/RavenX-Sec-8B-GGUF"
WORK_DIR="$HOME/Developer/RavenX-Sec/models/checkpoints"
LLAMA_CPP="$HOME/Developer/llama.cpp"
HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN environment variable first}"

echo "============================================"
echo " RavenX-Sec GGUF Conversion Pipeline"
echo " Source: $MODEL_DIR"
echo " Target: $REPO_GGUF"
echo "============================================"

# ── Step 1: Check prerequisites ──────────────────────────────────────────
echo ""
echo ">>> Step 1: Checking prerequisites..."
F16_GGUF="$WORK_DIR/ravenx-sec-v2.0-f16.gguf"

if [ -f "$F16_GGUF" ]; then
    echo "  F16 GGUF already exists: $(du -h "$F16_GGUF" | cut -f1)"
else
    echo "  Converting to F16 GGUF..."
    python3 "$LLAMA_CPP/convert_hf_to_gguf.py" \
        "$MODEL_DIR" \
        --outfile "$F16_GGUF"
    echo "  F16 GGUF created: $(du -h "$F16_GGUF" | cut -f1)"
fi

# ── Step 2: Build quantizer if needed ────────────────────────────────────
echo ""
echo ">>> Step 2: Checking llama-quantize..."
QUANTIZE="$LLAMA_CPP/build/bin/llama-quantize"

if [ ! -f "$QUANTIZE" ]; then
    echo "  Building llama.cpp..."
    cd "$LLAMA_CPP"
    cmake -B build -DGGML_METAL=ON
    cmake --build build --config Release -j$(sysctl -n hw.ncpu) --target llama-quantize
    cd "$WORK_DIR"
else
    echo "  llama-quantize found"
fi

# ── Step 3: Quantize to multiple formats ──────────────────────────────────
echo ""
echo ">>> Step 3: Quantizing..."

declare -A QUANTS=(
    ["Q4_K_M"]="ravenx-sec-v2.0-Q4_K_M.gguf"
    ["Q5_K_M"]="ravenx-sec-v2.0-Q5_K_M.gguf"
    ["Q8_0"]="ravenx-sec-v2.0-Q8_0.gguf"
)

for QTYPE in "${!QUANTS[@]}"; do
    OUTFILE="$WORK_DIR/${QUANTS[$QTYPE]}"
    if [ ! -f "$OUTFILE" ]; then
        echo "  Quantizing $QTYPE..."
        "$QUANTIZE" "$F16_GGUF" "$OUTFILE" "$QTYPE"
        echo "  Created: $OUTFILE ($(du -h "$OUTFILE" | cut -f1))"
    else
        echo "  $QTYPE already exists: $(du -h "$OUTFILE" | cut -f1)"
    fi
done

# ── Step 4: Create HuggingFace repo and upload ────────────────────────────
echo ""
echo ">>> Step 4: Uploading to HuggingFace..."
echo "  Repo: $REPO_GGUF"

python3 << PYEOF
from huggingface_hub import HfApi
import os, glob

api = HfApi(token="$HF_TOKEN")
repo_id = "$REPO_GGUF"
work_dir = "$WORK_DIR"

# Create repo if it doesn't exist
try:
    api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)
    print(f"Repo {repo_id} ready")
except Exception as e:
    print(f"Repo creation: {e}")

# Find all GGUF files
gguf_files = sorted(glob.glob(f"{work_dir}/ravenx-sec-v2.0-*.gguf"))
print(f"Found {len(gguf_files)} GGUF files to upload:")
for f in gguf_files:
    size_gb = os.path.getsize(f) / (1024**3)
    print(f"  {os.path.basename(f)}: {size_gb:.2f} GB")

for f in sorted(gguf_files):
    fname = os.path.basename(f)
    print(f"\nUploading {fname}...")
    api.upload_file(
        path_or_fileobj=f,
        path_in_repo=fname,
        repo_id=repo_id,
        token="$HF_TOKEN",
        commit_message=f"add {fname}",
    )
    print(f"  Uploaded {fname} successfully!")

print("\nAll GGUF files uploaded!")
PYEOF

# ── Step 5: Summary ───────────────────────────────────────────────────────
echo ""
echo "============================================"
echo " DONE! RavenX-Sec GGUF conversion complete."
echo "============================================"
echo ""
echo "Files created:"
ls -lh "$WORK_DIR"/ravenx-sec-v2.0-*.gguf 2>/dev/null
echo ""
echo "Repo: https://huggingface.co/$REPO_GGUF"
echo ""
echo "Test with:"
echo "  ollama run hf.co/$REPO_GGUF:Q4_K_M"

#!/usr/bin/env python3
"""
extend_context_128k.py — Extend RavenX-Sec context window from 40K to 128K

Based on ghostcc3/mix-context-post-training-128k methodology:
- Mix short (64-8K) and long (8K-128K) packed sequences
- Preserves short-context behavior while extending to 128K
- Uses Qwen3 tokenizer (not Llama 3)
- Mixes in security training data for dual-purpose training

This would be the FIRST Qwen3-specific 128K context extension dataset.

Requirements:
    pip install mlx-lm datasets transformers

Usage:
    # Step 1: Build the context extension dataset
    python training/context/extend_context_128k.py --build-dataset

    # Step 2: Post-train for context extension
    python training/context/extend_context_128k.py --train

    # Step 3: Test long context
    python training/context/extend_context_128k.py --test
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# ── Configuration ──────────────────────────────────────────────────────────
BASE_MODEL = "georgehenney/Qwen3-8B-heretic"
ADAPTER_PATH = str(Path(__file__).resolve().parent.parent.parent / "models" / "checkpoints" / "ravenx-sec-lora-v05")
FUSED_MODEL = str(Path(__file__).resolve().parent.parent.parent / "models" / "checkpoints" / "ravenx-sec-fused-v05")

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "context_extension"
DATASET_FILE = OUTPUT_DIR / "qwen3_128k_extension.jsonl"

# Target distribution (following ghostcc3 methodology)
TARGET_DISTRIBUTION = {
    "short_64_2k": {"min_tokens": 64, "max_tokens": 2048, "pack_to": 8192, "samples": 4000},
    "short_2k_4k": {"min_tokens": 2048, "max_tokens": 4096, "pack_to": 8192, "samples": 4000},
    "short_4k_8k": {"min_tokens": 4096, "max_tokens": 8192, "pack_to": 8192, "samples": 8000},
    "long_8k_32k": {"min_tokens": 8192, "max_tokens": 32768, "pack_to": 32768, "samples": 4000},
    "long_32k_64k": {"min_tokens": 32768, "max_tokens": 65536, "pack_to": 65536, "samples": 4000},
    "long_64k_128k": {"min_tokens": 65536, "max_tokens": 131072, "pack_to": 131072, "samples": 4000},
}
# Total: ~28K samples (scaled down from ghostcc3's 72K for M4 Max feasibility)


def load_tokenizer():
    """Load the Qwen3 tokenizer."""
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
        print(f"Loaded Qwen3 tokenizer: vocab_size={tokenizer.vocab_size}")
        return tokenizer
    except Exception as e:
        print(f"Error loading tokenizer: {e}")
        print("Falling back to mlx_lm tokenizer...")
        from mlx_lm import load
        _, tokenizer = load(FUSED_MODEL)
        return tokenizer


def fetch_short_context_data(tokenizer, num_samples: int = 16000) -> List[Dict]:
    """Fetch short-context data from FineWeb-Edu and tokenize with Qwen3."""
    from datasets import load_dataset

    print(f"Loading FineWeb-Edu for short context data...")
    try:
        ds = load_dataset("HuggingFaceFW/fineweb-edu", "sample-10BT",
                         split="train", streaming=True)
    except Exception:
        print("FineWeb-Edu not available, using C4 as fallback...")
        ds = load_dataset("allenai/c4", "en", split="train", streaming=True)

    samples = []
    seen = 0

    for item in ds:
        text = item.get("text", "")
        if len(text) < 100:
            continue

        tokens = tokenizer.encode(text, add_special_tokens=True)
        token_len = len(tokens)

        samples.append({
            "tokens": tokens,
            "length": token_len,
            "source": "fineweb-edu",
        })

        seen += 1
        if seen % 5000 == 0:
            print(f"  Processed {seen} documents, collected {len(samples)} samples")

        if len(samples) >= num_samples * 2:  # Collect extra for bucketing
            break

    print(f"  Collected {len(samples)} short-context samples")
    return samples


def fetch_long_context_data(tokenizer, num_samples: int = 12000) -> List[Dict]:
    """Fetch long-context data from RedPajama or arXiv and tokenize with Qwen3."""
    from datasets import load_dataset

    print(f"Loading long-context data (arXiv papers, books, etc.)...")

    samples = []

    # Try multiple sources for long documents
    sources = [
        ("togethercomputer/RedPajama-Data-1T-Sample", None, "train"),
        ("scientific_papers", "arxiv", "train"),
    ]

    for ds_name, ds_config, ds_split in sources:
        if len(samples) >= num_samples * 2:
            break

        try:
            print(f"  Trying {ds_name}...")
            ds = load_dataset(ds_name, ds_config, split=ds_split, streaming=True)

            for item in ds:
                text = item.get("text", item.get("article", ""))
                if len(text) < 10000:  # Skip short docs for long-context
                    continue

                tokens = tokenizer.encode(text, add_special_tokens=True)
                token_len = len(tokens)

                if token_len >= 8192:  # Only keep genuinely long docs
                    samples.append({
                        "tokens": tokens,
                        "length": token_len,
                        "source": ds_name,
                    })

                if len(samples) >= num_samples * 2:
                    break

                if len(samples) % 1000 == 0 and len(samples) > 0:
                    print(f"    Collected {len(samples)} long samples")

        except Exception as e:
            print(f"  Could not load {ds_name}: {e}")
            continue

    print(f"  Collected {len(samples)} long-context samples")
    return samples


def fetch_security_context_data(tokenizer) -> List[Dict]:
    """Load our security training data and tokenize for context extension."""
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    samples = []

    # Load all existing security JSONL files
    for jsonl_file in data_dir.rglob("*.jsonl"):
        if jsonl_file.name in ("train.jsonl", "valid.jsonl", "qwen3_128k_extension.jsonl"):
            continue

        try:
            with open(jsonl_file) as f:
                for line in f:
                    item = json.loads(line)
                    messages = item.get("messages", [])
                    if messages:
                        # Convert messages to text
                        text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
                        tokens = tokenizer.encode(text, add_special_tokens=True)
                        samples.append({
                            "tokens": tokens,
                            "length": len(tokens),
                            "source": "ravenx-sec",
                        })
        except Exception:
            continue

    print(f"  Loaded {len(samples)} security context samples")
    return samples


def bucket_samples(samples: List[Dict], min_tokens: int, max_tokens: int) -> List[Dict]:
    """Filter samples into a specific token length bucket."""
    return [s for s in samples if min_tokens <= s["length"] < max_tokens]


def pack_sequences(samples: List[Dict], target_length: int, num_packed: int,
                   bos_id: int, eos_id: int) -> List[Dict]:
    """Pack multiple short sequences into a single long sequence."""
    packed = []
    current_tokens = []
    current_positions = []
    pos = 0

    for sample in samples:
        if len(packed) >= num_packed:
            break

        tokens = sample["tokens"]

        # Add BOS if not already there
        if tokens[0] != bos_id:
            tokens = [bos_id] + tokens
        # Add EOS if not already there
        if tokens[-1] != eos_id:
            tokens = tokens + [eos_id]

        # Check if adding this sample would exceed target
        if len(current_tokens) + len(tokens) > target_length:
            # Save current packed sequence if it's long enough
            if len(current_tokens) >= target_length // 2:
                # Pad to target length
                while len(current_tokens) < target_length:
                    current_tokens.append(eos_id)
                    current_positions.append(pos)
                    pos += 1

                packed.append({
                    "input_ids": current_tokens[:target_length],
                    "position_ids": list(range(target_length)),
                })

            # Reset
            current_tokens = []
            current_positions = []
            pos = 0

        # Add tokens
        for t in tokens:
            current_tokens.append(t)
            current_positions.append(pos)
            pos += 1

    # Don't forget the last sequence
    if len(current_tokens) >= target_length // 2 and len(packed) < num_packed:
        while len(current_tokens) < target_length:
            current_tokens.append(eos_id)
            current_positions.append(pos)
            pos += 1

        packed.append({
            "input_ids": current_tokens[:target_length],
            "position_ids": list(range(target_length)),
        })

    return packed


def build_dataset():
    """Build the complete 128K context extension dataset."""
    print("=" * 60)
    print("Building Qwen3 128K Context Extension Dataset")
    print("FIRST OF ITS KIND — Qwen3-specific context extension")
    print("=" * 60)

    tokenizer = load_tokenizer()

    # Get special token IDs
    bos_id = tokenizer.bos_token_id or 0
    eos_id = tokenizer.eos_token_id or 0
    print(f"BOS ID: {bos_id}, EOS ID: {eos_id}")

    # Fetch data
    print("\n--- Fetching short-context data ---")
    short_samples = fetch_short_context_data(tokenizer, num_samples=20000)

    print("\n--- Fetching long-context data ---")
    long_samples = fetch_long_context_data(tokenizer, num_samples=15000)

    print("\n--- Fetching security context data ---")
    security_samples = fetch_security_context_data(tokenizer)

    # Combine all samples
    all_samples = short_samples + long_samples + security_samples
    print(f"\nTotal samples collected: {len(all_samples)}")

    # Build packed sequences for each bucket
    all_packed = []

    print("\n--- Packing sequences ---")
    for bucket_name, config in TARGET_DISTRIBUTION.items():
        print(f"\n  Bucket: {bucket_name}")
        print(f"    Range: {config['min_tokens']}-{config['max_tokens']} tokens")
        print(f"    Pack to: {config['pack_to']} tokens")
        print(f"    Target: {config['samples']} samples")

        bucket = bucket_samples(all_samples, config["min_tokens"], config["max_tokens"])
        print(f"    Available: {len(bucket)} samples in range")

        if len(bucket) == 0:
            print(f"    SKIP: No samples in this range")
            continue

        packed = pack_sequences(bucket, config["pack_to"], config["samples"],
                              bos_id, eos_id)
        print(f"    Packed: {len(packed)} sequences")
        all_packed.extend(packed)

    # Save dataset
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_FILE, "w") as f:
        for item in all_packed:
            f.write(json.dumps(item) + "\n")

    print(f"\n{'=' * 60}")
    print(f"✅ Dataset saved: {DATASET_FILE}")
    print(f"   Total packed sequences: {len(all_packed)}")
    print(f"   Dataset size: {DATASET_FILE.stat().st_size / (1024**3):.2f} GB")
    print(f"{'=' * 60}")


def train():
    """Post-train RavenX-Sec for 128K context extension."""
    import subprocess

    print("=" * 60)
    print("Post-training RavenX-Sec for 128K Context Extension")
    print("=" * 60)

    # For context extension, we use continued pre-training (not LoRA)
    # with a very low learning rate and the packed sequences
    print("\nNOTE: Context extension requires continued pre-training")
    print("with RoPE scaling. This is a longer training run.")
    print("\nFor MLX, we use LoRA with very long sequences:")

    adapter_dir = Path(__file__).resolve().parent.parent.parent / "models" / "checkpoints" / "ravenx-sec-128k-lora"
    adapter_dir.mkdir(parents=True, exist_ok=True)

    # Write config with extended context
    config_content = """# RavenX-Sec 128K Context Extension LoRA Config
fine_tune_type: lora
num_layers: 8
lora_parameters:
  rank: 16
  alpha: 32
  dropout: 0.05
  scale: 10.0
"""
    config_path = adapter_dir / "lora_config.yaml"
    with open(config_path, "w") as f:
        f.write(config_content)

    cmd = [
        sys.executable, "-m", "mlx_lm", "lora",
        "--model", FUSED_MODEL,
        "--data", str(OUTPUT_DIR),
        "--train",
        "--batch-size", "1",              # Batch size 1 for long sequences
        "--num-layers", "8",
        "--iters", "500",
        "--val-batches", "10",
        "--learning-rate", "5e-6",         # Very low LR for context extension
        "--steps-per-report", "10",
        "--steps-per-eval", "100",
        "--save-every", "100",
        "--max-seq-length", "32768",       # Start with 32K, work up to 128K
        "--adapter-path", str(adapter_dir),
        "-c", str(config_path),
        "--grad-checkpoint",
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)
    print(f"\n✅ Context extension training complete!")


def test():
    """Test long context capabilities."""
    from mlx_lm import load, generate

    print("=" * 60)
    print("Testing RavenX-Sec 128K Context")
    print("=" * 60)

    model, tokenizer = load(FUSED_MODEL)

    # Test with a long prompt (simulating a pentest report)
    long_context = "You are reviewing a penetration test report. " + \
        "Finding 1: " * 100 + \
        "Based on all 100 findings above, provide an executive summary with the top 5 critical issues."

    messages = [
        {"role": "system", "content": "You are RavenX-Sec. Follow RATH protocol."},
        {"role": "user", "content": long_context},
    ]

    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    print(f"Prompt length: {len(tokenizer.encode(prompt))} tokens")

    response = generate(model, tokenizer, prompt=prompt, max_tokens=512)
    print(response)


def main():
    parser = argparse.ArgumentParser(description="RavenX-Sec 128K Context Extension")
    parser.add_argument("--build-dataset", action="store_true", help="Build context extension dataset")
    parser.add_argument("--train", action="store_true", help="Post-train for context extension")
    parser.add_argument("--test", action="store_true", help="Test long context")
    parser.add_argument("--all", action="store_true", help="Run all steps")
    args = parser.parse_args()

    if args.all:
        build_dataset()
        train()
        test()
    elif args.build_dataset:
        build_dataset()
    elif args.train:
        train()
    elif args.test:
        test()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

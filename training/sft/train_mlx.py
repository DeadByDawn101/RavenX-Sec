#!/usr/bin/env python3
"""
train_mlx.py — Fine-tune Qwen3-8B-heretic on Apple Silicon using MLX + LoRA

This script trains the RavenX-Sec security model on the M4 Max (128GB)
using MLX's native LoRA implementation for efficient Apple Silicon training.

Requirements:
    pip install mlx-lm datasets

Usage:
    # Step 1: Download the model
    python training/sft/train_mlx.py --download-only

    # Step 2: Prepare training data
    python training/sft/train_mlx.py --prepare-data

    # Step 3: Train
    python training/sft/train_mlx.py --train

    # Step 4: Fuse LoRA adapters into model
    python training/sft/train_mlx.py --fuse

    # All steps:
    python training/sft/train_mlx.py --all
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────
BASE_MODEL = "georgehenney/Qwen3-8B-heretic"
GGUF_MODEL = "mradermacher/Qwen3-8B-heretic-i1-GGUF"
MYTHOS_DATASET = "WithinUsAI/claude_mythos_distilled_25k"

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TRAIN_FILE = DATA_DIR / "train.jsonl"
VALID_FILE = DATA_DIR / "valid.jsonl"
ADAPTER_DIR = PROJECT_ROOT / "models" / "checkpoints" / "ravenx-sec-lora-v02"
FUSED_DIR = PROJECT_ROOT / "models" / "checkpoints" / "ravenx-sec-fused-v02"

# Training hyperparameters (optimized for M4 Max 128GB)
# v0.2: Conservative settings to prevent output layer destabilization
LORA_CONFIG = {
    "num_layers": 8,           # Fewer layers = more stable (was 16)
    "rank": 16,                # Lower rank = gentler adaptation (was 64)
    "alpha": 32,               # 2x rank for stable training (was 128)
    "dropout": 0.1,            # Higher dropout for regularization (was 0.05)
    "scale": 10.0,             # LoRA scale
}

TRAIN_CONFIG = {
    "learning_rate": 1e-5,     # 20x lower LR prevents corruption (was 2e-4)
    "batch_size": 4,
    "iters": 500,              # Fewer iters with lower LR (was 1000)
    "val_batches": 25,         # Validation batches
    "steps_per_report": 10,    # Report every N steps
    "steps_per_eval": 100,     # Evaluate every N steps
    "save_every": 100,         # Save more frequently (was 200)
    "max_seq_length": 4096,    # Max sequence length
    "grad_checkpoint": True,   # Gradient checkpointing for memory efficiency
}


def download_model():
    """Download the base model for MLX training."""
    print("=" * 60)
    print("Step 1: Downloading Qwen3-8B-heretic for MLX")
    print("=" * 60)

    # Use mlx-lm to convert the model to MLX format
    cmd = [
        sys.executable, "-m", "mlx_lm.convert",
        "--hf-path", BASE_MODEL,
        "-q",  # Quantize to 4-bit for training efficiency
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("✅ Model downloaded and converted to MLX format")


def prepare_data():
    """Prepare training data from the Mythos dataset + security data."""
    print("=" * 60)
    print("Step 2: Preparing training data")
    print("=" * 60)

    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets library...")
        subprocess.run([sys.executable, "-m", "pip", "install", "datasets"], check=True)
        from datasets import load_dataset

    # Load the Mythos distilled dataset
    print(f"Loading {MYTHOS_DATASET}...")
    ds = load_dataset(MYTHOS_DATASET, split="train")
    print(f"Loaded {len(ds)} examples")

    # Filter for security-relevant categories
    security_categories = ["cybersecurity", "advanced_coding", "agentic_planning"]
    all_categories = set()

    all_examples = []
    security_examples = []
    other_examples = []

    for item in ds:
        category = item.get("category", "unknown")
        all_categories.add(category)

        # Convert to MLX chat format
        messages = item.get("messages", [])
        if len(messages) >= 2:
            example = {
                "messages": messages
            }
            all_examples.append(example)

            if category in security_categories:
                security_examples.append(example)
            else:
                other_examples.append(example)

    print(f"Categories found: {all_categories}")
    print(f"Security-relevant examples: {len(security_examples)}")
    print(f"Other examples: {len(other_examples)}")

    # Load any local security training data
    local_data = []
    for jsonl_file in DATA_DIR.rglob("*.jsonl"):
        if jsonl_file.name in ("train.jsonl", "valid.jsonl"):
            continue
        print(f"Loading local data: {jsonl_file}")
        with open(jsonl_file) as f:
            for line in f:
                try:
                    item = json.loads(line)
                    # Convert instruction format to messages format
                    if "instruction" in item:
                        messages = [
                            {"role": "user", "content": item["instruction"] + ("\n" + item["input"] if item.get("input") else "")},
                            {"role": "assistant", "content": item["output"]}
                        ]
                        local_data.append({"messages": messages})
                    elif "messages" in item:
                        local_data.append(item)
                except json.JSONDecodeError:
                    continue

    if local_data:
        print(f"Loaded {len(local_data)} local security examples")

    # Combine: security examples first (upsampled), then other examples
    # Upsample security by 3x to emphasize security training
    combined = security_examples * 3 + local_data * 5 + other_examples

    # Shuffle
    import random
    random.seed(42)
    random.shuffle(combined)

    # Split 90/10
    split_idx = int(len(combined) * 0.9)
    train_data = combined[:split_idx]
    valid_data = combined[split_idx:]

    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(TRAIN_FILE, "w") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")

    with open(VALID_FILE, "w") as f:
        for item in valid_data:
            f.write(json.dumps(item) + "\n")

    print(f"✅ Training data: {len(train_data)} examples → {TRAIN_FILE}")
    print(f"✅ Validation data: {len(valid_data)} examples → {VALID_FILE}")


def train():
    """Run MLX LoRA training on M4 Max."""
    print("=" * 60)
    print("Step 3: Training RavenX-Sec with MLX LoRA")
    print("=" * 60)
    print(f"Base model: {BASE_MODEL}")
    print(f"LoRA rank: {LORA_CONFIG['rank']}")
    print(f"Learning rate: {TRAIN_CONFIG['learning_rate']}")
    print(f"Batch size: {TRAIN_CONFIG['batch_size']}")
    print(f"Iterations: {TRAIN_CONFIG['iters']}")
    print(f"Max seq length: {TRAIN_CONFIG['max_seq_length']}")
    print("=" * 60)

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

    # Write LoRA config YAML for mlx_lm
    lora_config_path = ADAPTER_DIR / "lora_config.yaml"
    config_content = f"""# RavenX-Sec LoRA Configuration
fine_tune_type: lora
num_layers: {LORA_CONFIG["num_layers"]}
lora_parameters:
  rank: {LORA_CONFIG["rank"]}
  alpha: {LORA_CONFIG["alpha"]}
  dropout: {LORA_CONFIG["dropout"]}
  scale: {LORA_CONFIG["scale"]}
"""
    with open(lora_config_path, "w") as f:
        f.write(config_content)

    cmd = [
        sys.executable, "-m", "mlx_lm", "lora",
        "--model", BASE_MODEL,
        "--data", str(DATA_DIR),
        "--train",
        "--batch-size", str(TRAIN_CONFIG["batch_size"]),
        "--num-layers", str(LORA_CONFIG["num_layers"]),
        "--iters", str(TRAIN_CONFIG["iters"]),
        "--val-batches", str(TRAIN_CONFIG["val_batches"]),
        "--learning-rate", str(TRAIN_CONFIG["learning_rate"]),
        "--steps-per-report", str(TRAIN_CONFIG["steps_per_report"]),
        "--steps-per-eval", str(TRAIN_CONFIG["steps_per_eval"]),
        "--save-every", str(TRAIN_CONFIG["save_every"]),
        "--max-seq-length", str(TRAIN_CONFIG["max_seq_length"]),
        "--adapter-path", str(ADAPTER_DIR),
        "-c", str(lora_config_path),
    ]

    if TRAIN_CONFIG["grad_checkpoint"]:
        cmd.append("--grad-checkpoint")

    print(f"\nRunning: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)
    print(f"\n✅ Training complete! Adapters saved to {ADAPTER_DIR}")


def fuse():
    """Fuse LoRA adapters into the base model."""
    print("=" * 60)
    print("Step 4: Fusing LoRA adapters into model")
    print("=" * 60)

    FUSED_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "mlx_lm", "fuse",
        "--model", BASE_MODEL,
        "--adapter-path", str(ADAPTER_DIR),
        "--save-path", str(FUSED_DIR),
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"\n✅ Fused model saved to {FUSED_DIR}")
    print(f"\nTo test: python -m mlx_lm.generate --model {FUSED_DIR} --prompt 'Analyze CVE-2024-1234'")


def test_inference():
    """Quick inference test with the fused model."""
    print("=" * 60)
    print("Testing RavenX-Sec inference")
    print("=" * 60)

    test_prompts = [
        "You found OpenSSH 7.4 on port 22 of a target host. Classify this finding, score it with CVSS, and provide remediation steps.",
        "Perform privilege escalation reconnaissance on a Linux host running Ubuntu 20.04 with kernel 5.4.0-42.",
        "A Nessus scan found CVE-2021-4034 (PwnKit) on 15 production servers. Generate a remediation plan with SLA tracking.",
    ]

    model_path = str(FUSED_DIR) if FUSED_DIR.exists() else BASE_MODEL

    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Test {i+1} ---")
        print(f"Prompt: {prompt[:80]}...")
        cmd = [
            sys.executable, "-m", "mlx_lm.generate",
            "--model", model_path,
            "--prompt", prompt,
            "--max-tokens", "512",
        ]
        subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="RavenX-Sec MLX Training Pipeline")
    parser.add_argument("--download-only", action="store_true", help="Download model only")
    parser.add_argument("--prepare-data", action="store_true", help="Prepare training data")
    parser.add_argument("--train", action="store_true", help="Run training")
    parser.add_argument("--fuse", action="store_true", help="Fuse LoRA adapters")
    parser.add_argument("--test", action="store_true", help="Test inference")
    parser.add_argument("--all", action="store_true", help="Run all steps")
    args = parser.parse_args()

    if args.all:
        download_model()
        prepare_data()
        train()
        fuse()
        test_inference()
    elif args.download_only:
        download_model()
    elif args.prepare_data:
        prepare_data()
    elif args.train:
        train()
    elif args.fuse:
        fuse()
    elif args.test:
        test_inference()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

# Training Guide — RavenX-Sec

## Overview

RavenX-Sec is trained using MLX LoRA on Apple Silicon. The training pipeline
downloads the base model, prepares data from HuggingFace datasets, runs
LoRA fine-tuning, and fuses adapters into a standalone model.

## Prerequisites

```bash
pip install mlx-lm datasets
```

## Quick Start

```bash
# Full pipeline: download → prepare data → train → fuse → test
python training/sft/train_mlx.py --all

# Or step by step:
python training/sft/train_mlx.py --download-only
python training/sft/train_mlx.py --prepare-data
python training/sft/train_mlx.py --train
python training/sft/train_mlx.py --fuse
python training/sft/train_mlx.py --test
```

## Hardware Requirements

| Hardware | Minimum | Recommended |
|----------|---------|-------------|
| Apple Silicon | M1 (16 GB) | M4 Max (128 GB) |
| Peak Memory | ~12 GB | ~21 GB |
| Training Time | ~4 hours | ~2 hours |
| Storage | 30 GB | 50 GB |

## Training Configuration (v1.0)

```yaml
base_model: georgehenney/Qwen3-8B-heretic
method: LoRA
rank: 32
alpha: 64
dropout: 0.1
num_layers: 8
learning_rate: 1e-5
batch_size: 4
iterations: 1000
max_seq_length: 4096
gradient_checkpointing: true
```

## Data Mix (Critical for Quality)

The most important lesson from training: **data balance matters more than data volume.**

| Version | Data | Security Ratio | Result |
|---------|------|---------------|--------|
| v0.3 | 51K (Mythos only) | 94% | ✅ Great |
| v0.4 | 321K (+ 300K AgentAngel) | 13% | ⚠️ Regressed |
| **v0.5** | **125K (Mythos + 50K AgentAngel)** | **58%** | **🏆 Best** |

**Rule: Security examples should be >50% of training data.**

## Lessons Learned

1. **Learning rate 1e-5 is the sweet spot.** 2e-4 destabilized the model (v0.1). 1e-5 preserves base capabilities while learning security specialization.

2. **LoRA rank 32 with 8 layers is optimal.** Rank 16 (v0.2) worked but was limited. Rank 64 (v0.1) was too aggressive. Rank 32 hits the sweet spot.

3. **Cap agentic data to prevent dilution.** AgentAngel is great for reasoning but overwhelms security signal if uncapped. Limit to 50K examples.

4. **Always test with chat template.** Raw prompt generation produces garbage. Must use `tokenizer.apply_chat_template()`.

5. **Save checkpoints frequently.** The best checkpoint might not be the last one.

## Adding New Training Data

### From HuggingFace Datasets
Add to `models/configs/training_config.yaml` and update `prepare_data()` in `train_mlx.py`.

### From Source Repos
Use extraction tools in `tools/`:
```bash
python tools/extract_hackingbuddy.py --db path/to/wintermute.sqlite3
python tools/extract_pentestgpt.py --repo-path path/to/PentestGPT
python tools/extract_shannon.py --repo-path path/to/shannon
python tools/extract_ghidra.py --repo-path path/to/ghidra
python tools/synthesize_chains.py
python tools/quality_filter.py --input data/train.jsonl --output data/train_filtered.jsonl
```

## Evaluation

Test the fused model with security-specific prompts:
```bash
python training/sft/train_mlx.py --test
```

The model should produce structured RATH protocol output:
1. Environment analysis
2. Threat modeling
3. Framework mapping (CVSS + NIST + OWASP)
4. Specific remediation commands
5. Post-fix verification

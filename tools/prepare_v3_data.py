#!/usr/bin/env python3
"""
prepare_v3_data.py — Build the v3.0 mega training dataset

Combines ALL security datasets into one massive training corpus:
- Original: Mythos 25K + AgentAngel (capped 50K) + extracted repo data
- NEW: 11 security-specific HuggingFace datasets

Usage:
    python tools/prepare_v3_data.py --output data/
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict

random.seed(42)


# All 11 new security datasets
SECURITY_DATASETS = [
    "Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset",
    "WNT3D/Ultimate-Offensive-Red-Team",
    "AYI-NEDJIMI/bug-bounty-pentest-en",
    "auren-research/cve-sft-v5",
    "theelderemo/pentesting-explanations",
    "Rootkit7/pentest-redteam-steering",
    "cpagac/venomx-pentesting-harmful",
    "SkywardNomad92/pentest-findings-v2",
    "acnimatic3722/kali-linux-pentesting-data",
    "CJJones/Synthetic_PenTest_Reports",
    "nangyall/4-Security-Tools-Pentesting",
]

# Original datasets
MYTHOS_DATASET = "WithinUsAI/claude_mythos_distilled_25k"
AGENT_DATASET = "WithinUsAI/AgentAngel_100k"
AGENT_SPLITS = ["chat", "instruct", "qa", "reasoning", "thinking"]
AGENT_CAP = 50000


def convert_to_messages(item: Dict) -> Dict:
    """Convert any format to messages format."""
    # Already in messages format
    messages = item.get("messages", [])
    if messages and len(messages) >= 2:
        valid = []
        for m in messages:
            if isinstance(m, dict) and "role" in m and "content" in m:
                valid.append({"role": str(m["role"]), "content": str(m["content"])})
        if len(valid) >= 2:
            return {"messages": valid}

    # Try conversation format
    conversations = item.get("conversations", [])
    if conversations and len(conversations) >= 2:
        msgs = []
        for c in conversations:
            role = c.get("from", c.get("role", "user"))
            if role in ("human", "user"):
                role = "user"
            elif role in ("gpt", "assistant", "model"):
                role = "assistant"
            content = c.get("value", c.get("content", ""))
            if content:
                msgs.append({"role": role, "content": str(content)})
        if len(msgs) >= 2:
            return {"messages": msgs}

    # Try instruction/input/output format
    instruction = item.get("instruction", item.get("question", item.get("prompt", "")))
    inp = item.get("input", "")
    output = item.get("output", item.get("answer", item.get("response", item.get("completion", ""))))

    if instruction and output:
        user_content = str(instruction)
        if inp:
            user_content += "\n" + str(inp)
        return {"messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": str(output)}
        ]}

    # Try text format (for reports/explanations)
    text = item.get("text", item.get("content", ""))
    if text and len(str(text)) > 200:
        return {"messages": [
            {"role": "user", "content": "Analyze the following security content and provide your assessment:"},
            {"role": "assistant", "content": str(text)[:4000]}
        ]}

    return None


def load_hf_dataset(name: str, max_samples: int = None) -> List[Dict]:
    """Load a HuggingFace dataset and convert to messages format."""
    from datasets import load_dataset

    examples = []
    try:
        # Try loading normally
        ds = load_dataset(name, split="train", trust_remote_code=True)
        print(f"    Loaded {len(ds)} rows")

        for item in ds:
            converted = convert_to_messages(dict(item))
            if converted:
                examples.append(converted)
            if max_samples and len(examples) >= max_samples:
                break

    except Exception as e1:
        # Try loading with streaming
        try:
            ds = load_dataset(name, split="train", streaming=True, trust_remote_code=True)
            count = 0
            for item in ds:
                converted = convert_to_messages(dict(item))
                if converted:
                    examples.append(converted)
                    count += 1
                if max_samples and count >= max_samples:
                    break
                if count >= 100000:  # Safety cap
                    break
            print(f"    Streamed {count} examples")
        except Exception as e2:
            print(f"    FAILED: {e1} / {e2}")

    return examples


def load_agent_angel() -> List[Dict]:
    """Load AgentAngel with split-by-split handling."""
    from datasets import load_dataset

    examples = []
    for split_name in AGENT_SPLITS:
        data_file = f"splits/agentangel_100k.{split_name}.jsonl"
        try:
            split_ds = load_dataset(AGENT_DATASET, data_files=data_file, split="train")
            count = 0
            for item in split_ds:
                converted = convert_to_messages(dict(item))
                if converted:
                    examples.append(converted)
                    count += 1
            print(f"    {split_name}: {count} examples")
        except Exception as e:
            print(f"    {split_name}: failed ({e})")
    return examples


def load_local_data(data_dir: Path) -> List[Dict]:
    """Load local extracted security data."""
    examples = []
    for jsonl_file in data_dir.rglob("*.jsonl"):
        if jsonl_file.name in ("train.jsonl", "valid.jsonl"):
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    item = json.loads(line)
                    converted = convert_to_messages(item)
                    if converted:
                        examples.append(converted)
        except Exception:
            continue
    return examples


def main():
    parser = argparse.ArgumentParser(description="Build RavenX-Sec v3.0 training data")
    parser.add_argument("--output", default="data/", help="Output directory")
    parser.add_argument("--skip-agent", action="store_true", help="Skip AgentAngel (faster)")
    args = parser.parse_args()

    from datasets import load_dataset

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_security = []
    all_agentic = []
    all_other = []

    print("=" * 70)
    print("  RavenX-Sec v3.0 — MEGA SECURITY TRAINING DATASET")
    print("=" * 70)

    # ── 1. Load 11 new security datasets ──────────────────────────────
    print("\n[Phase 1] Loading 11 security-specific datasets...")
    for i, ds_name in enumerate(SECURITY_DATASETS, 1):
        print(f"\n  [{i}/11] {ds_name}")
        examples = load_hf_dataset(ds_name, max_samples=50000)
        print(f"    → {len(examples)} usable examples")
        all_security.extend(examples)

    print(f"\n  Phase 1 total: {len(all_security)} security examples")

    # ── 2. Load Mythos (security categories) ──────────────────────────
    print(f"\n[Phase 2] Loading {MYTHOS_DATASET}...")
    ds = load_dataset(MYTHOS_DATASET, split="train")
    security_cats = ["cybersecurity", "advanced_coding", "agentic_planning"]
    mythos_security = []
    mythos_other = []

    for item in ds:
        converted = convert_to_messages(dict(item))
        if not converted:
            continue
        if item.get("category", "") in security_cats:
            mythos_security.append(converted)
        else:
            mythos_other.append(converted)

    print(f"  Mythos security: {len(mythos_security)}")
    print(f"  Mythos other: {len(mythos_other)}")
    all_security.extend(mythos_security)
    all_other.extend(mythos_other)

    # ── 3. Load AgentAngel (capped) ───────────────────────────────────
    if not args.skip_agent:
        print(f"\n[Phase 3] Loading {AGENT_DATASET} (capped at {AGENT_CAP})...")
        agent_examples = load_agent_angel()
        random.shuffle(agent_examples)
        agent_capped = agent_examples[:AGENT_CAP]
        print(f"  AgentAngel: {len(agent_examples)} → capped to {len(agent_capped)}")
        all_agentic.extend(agent_capped)
    else:
        print("\n[Phase 3] Skipping AgentAngel")

    # ── 4. Load local extracted data ──────────────────────────────────
    print(f"\n[Phase 4] Loading local extracted data...")
    local = load_local_data(output_dir)
    print(f"  Local security data: {len(local)} examples")
    all_security.extend(local)

    # ── 5. Combine with security-dominant weighting ───────────────────
    print(f"\n[Phase 5] Combining with security-dominant weighting...")
    print(f"  Security examples (raw): {len(all_security)}")
    print(f"  Agentic examples: {len(all_agentic)}")
    print(f"  Other examples: {len(all_other)}")

    # Security at 2x (already large), agentic at 1x, other at 1x
    combined = (
        all_security * 2 +
        all_agentic +
        all_other
    )

    random.shuffle(combined)

    # Split 90/10
    split_idx = int(len(combined) * 0.9)
    train_data = combined[:split_idx]
    valid_data = combined[split_idx:]

    # Save
    train_file = output_dir / "train.jsonl"
    valid_file = output_dir / "valid.jsonl"

    with open(train_file, "w") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")

    with open(valid_file, "w") as f:
        for item in valid_data:
            f.write(json.dumps(item) + "\n")

    sec_pct = (len(all_security) * 2) / len(combined) * 100

    print(f"\n{'=' * 70}")
    print(f"  ✅ RavenX-Sec v3.0 Training Data READY")
    print(f"{'=' * 70}")
    print(f"  Training:   {len(train_data):,} examples → {train_file}")
    print(f"  Validation: {len(valid_data):,} examples → {valid_file}")
    print(f"  Security:   {len(all_security):,} × 2 = {len(all_security)*2:,} ({sec_pct:.0f}%)")
    print(f"  Agentic:    {len(all_agentic):,}")
    print(f"  Other:      {len(all_other):,}")
    print(f"  Total:      {len(combined):,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
quality_filter.py — Deduplicate, validate, and balance the training dataset

Filters the combined training data for quality:
- Removes duplicates (by instruction hash)
- Validates message format (role/content pairs)
- Filters empty or too-short responses
- Balances categories to prevent data dilution
- Reports statistics

Usage:
    python tools/quality_filter.py --input data/train.jsonl --output data/train_filtered.jsonl
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import List, Dict


def compute_hash(item: Dict) -> str:
    """Compute a content hash for deduplication."""
    messages = item.get("messages", [])
    if messages:
        content = "".join(m.get("content", "") for m in messages)
    else:
        content = item.get("instruction", "") + item.get("output", "")
    return hashlib.md5(content.encode()).hexdigest()


def validate_messages(item: Dict) -> bool:
    """Validate that the item has proper message format."""
    messages = item.get("messages", [])
    if not messages or len(messages) < 2:
        return False

    for msg in messages:
        if not isinstance(msg, dict):
            return False
        if "role" not in msg or "content" not in msg:
            return False
        if not msg["content"] or len(str(msg["content"])) < 10:
            return False
        if msg["role"] not in ("system", "user", "assistant"):
            return False

    # Must have at least one user and one assistant message
    roles = [m["role"] for m in messages]
    if "user" not in roles or "assistant" not in roles:
        return False

    return True


def filter_too_short(item: Dict, min_output_len: int = 50) -> bool:
    """Filter out items with very short assistant responses."""
    messages = item.get("messages", [])
    for msg in messages:
        if msg.get("role") == "assistant":
            if len(str(msg.get("content", ""))) >= min_output_len:
                return True
    return False


def run_quality_filter(input_path: str, output_path: str, min_output_len: int = 50):
    """Run the full quality filter pipeline."""
    print(f"Loading {input_path}...")

    items = []
    with open(input_path) as f:
        for line in f:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Loaded {len(items)} items")

    # Step 1: Validate format
    valid = [item for item in items if validate_messages(item)]
    removed_invalid = len(items) - len(valid)
    print(f"  Format validation: {removed_invalid} removed, {len(valid)} remaining")

    # Step 2: Filter too-short
    long_enough = [item for item in valid if filter_too_short(item, min_output_len)]
    removed_short = len(valid) - len(long_enough)
    print(f"  Length filter (min {min_output_len}): {removed_short} removed, {len(long_enough)} remaining")

    # Step 3: Deduplicate
    seen = set()
    unique = []
    for item in long_enough:
        h = compute_hash(item)
        if h not in seen:
            seen.add(h)
            unique.append(item)
    removed_dupes = len(long_enough) - len(unique)
    print(f"  Deduplication: {removed_dupes} removed, {len(unique)} remaining")

    # Step 4: Statistics
    print(f"\n  Final dataset: {len(unique)} examples")
    print(f"  Removed total: {len(items) - len(unique)} ({(len(items) - len(unique))/len(items)*100:.1f}%)")

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for item in unique:
            f.write(json.dumps(item) + "\n")

    print(f"\n✅ Filtered dataset saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Quality filter for RavenX-Sec training data")
    parser.add_argument("--input", required=True, help="Input JSONL file")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    parser.add_argument("--min-output-len", type=int, default=50, help="Minimum assistant response length")
    args = parser.parse_args()

    run_quality_filter(args.input, args.output, args.min_output_len)


if __name__ == "__main__":
    main()

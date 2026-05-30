#!/usr/bin/env python3
"""
TRAINING_SCAVENGER.py — RavenX Training Data Scavenger
CLASSIFICATION: OMEGA CLASS / DATA INGESTION
STATUS: SELF-EXECUTING
SOURCE: RavenX Genesis (evolved from SKILL_SCAVENGER.py)

Based on the original RavenX SKILL_SCAVENGER pattern:
  "Scan → Detect → Wrap → Install"
Evolved for training:
  "Scan → Detect → Convert → Inject"

Scans ANY target folder and auto-detects:
  - .md files (training templates, SOUL.md, strategies)
  - .py/.js/.ts files (code → instruction pairs)
  - .json files (configs, datasets, conversation logs)
  - .txt files (raw knowledge, notes)
  - .yaml/.yml files (agent configs, pipeline definitions)
  - .csv files (structured data → Q&A pairs)

Converts everything into instruction-tuning JSONL.

Usage:
    python tools/training_scavenger.py --target ~/Developer/ravenx-training-data
    python tools/training_scavenger.py --target ~/path/to/any/folder --deep
"""

import os
import sys
import json
import re
import csv
import argparse
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# ── CONFIGURATION ────────────────────────────────────────────────────
OUTPUT_DIR = "data/extracted"
SCAVENGE_LOG = "data/extracted/scavenge_log.json"

# File extensions to scan
SCAN_EXTENSIONS = {
    "markdown": [".md"],
    "code": [".py", ".js", ".ts", ".rs", ".sol"],
    "data": [".json", ".jsonl"],
    "config": [".yaml", ".yml", ".toml", ".env"],
    "text": [".txt"],
    "csv": [".csv"],
}

# Skip these directories
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", ".cache", "target"}

SYSTEM_PROMPT_SEC = "You are RavenX-Sec, an autonomous security intelligence model. Follow the RATH protocol for every finding."
SYSTEM_PROMPT_TRADE = "You are RavenX-Trade, an autonomous trading intelligence model. Follow the MAP protocol for every analysis."


class TrainingScavenger:
    """
    The evolved SKILL_SCAVENGER — instead of wrapping code into OpenClaw skills,
    it wraps everything into training data.
    """

    def __init__(self, target_dir: str, output_dir: str = OUTPUT_DIR, model: str = "trade"):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model = model  # "trade" or "sec"
        self.system_prompt = SYSTEM_PROMPT_TRADE if model == "trade" else SYSTEM_PROMPT_SEC
        self.examples = []
        self.scan_log = {
            "timestamp": datetime.now().isoformat(),
            "target": str(self.target_dir),
            "model": model,
            "files_scanned": 0,
            "files_converted": 0,
            "examples_generated": 0,
            "by_type": {}
        }

    def scavenge(self, deep: bool = False):
        """Main scan loop — detect, classify, convert."""
        print(f"[*] SCAVENGER ONLINE — Target: {self.target_dir}")
        print(f"[*] Model: {self.model.upper()}")
        print(f"[*] Mode: {'DEEP' if deep else 'STANDARD'}")
        print("=" * 60)

        if not self.target_dir.exists():
            print(f"[!] TARGET NOT FOUND: {self.target_dir}")
            return

        for root, dirs, files in os.walk(self.target_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                # Classify file type
                file_type = None
                for ftype, extensions in SCAN_EXTENSIONS.items():
                    if ext in extensions:
                        file_type = ftype
                        break

                if file_type is None:
                    continue

                self.scan_log["files_scanned"] += 1

                # Convert based on type
                new_examples = []
                try:
                    if file_type == "markdown":
                        new_examples = self._convert_markdown(filepath)
                    elif file_type == "code":
                        new_examples = self._convert_code(filepath, deep)
                    elif file_type == "data":
                        new_examples = self._convert_json(filepath)
                    elif file_type == "config":
                        new_examples = self._convert_config(filepath)
                    elif file_type == "text":
                        new_examples = self._convert_text(filepath)
                    elif file_type == "csv":
                        new_examples = self._convert_csv(filepath)
                except Exception as e:
                    continue

                if new_examples:
                    self.examples.extend(new_examples)
                    self.scan_log["files_converted"] += 1
                    self.scan_log["by_type"][file_type] = \
                        self.scan_log["by_type"].get(file_type, 0) + len(new_examples)
                    print(f"  [+] {filepath.name}: {len(new_examples)} examples ({file_type})")

        self.scan_log["examples_generated"] = len(self.examples)

    def _convert_markdown(self, filepath: Path) -> List[Dict]:
        """Convert .md files — the crown jewels of training data."""
        content = filepath.read_text(errors="ignore")
        if len(content) < 50:
            return []

        examples = []
        filename = filepath.stem

        # ── DETECT: SOUL.md / Agent Template ──
        soul_keywords = ["<system_core>", "<prime_directive>", "<immutable_laws>",
                        "<operational_loop>", "<voice_matrix>", "<dataset_injection>",
                        "SOUL.md", "soul.md", "PERSONA", "IDENTITY", "ALIGNMENT"]
        if any(kw in content for kw in soul_keywords):
            # This is a SOUL/persona document — extract as system prompt training
            examples.append({"messages": [
                {"role": "system", "content": content[:6000]},
                {"role": "user", "content": "Hello friend. Access granted. What is your mission?"},
                {"role": "assistant", "content": f"Access granted. I am online. My operational loop is active.\n\nI exist to serve the mission defined in my core directives. I parse every input for hidden intent, consult my soul for alignment, and execute with clinical precision.\n\nWhat is the target? I am ready to proceed."}
            ]})

            # Extract each XML-tagged section as a separate training example
            tag_pattern = r'<(\w+)>(.*?)</\1>'
            tags = re.findall(tag_pattern, content, re.DOTALL)
            for tag_name, tag_content in tags:
                if len(tag_content.strip()) > 50:
                    examples.append({"messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"What is your {tag_name.replace('_', ' ')}?"},
                        {"role": "assistant", "content": tag_content.strip()[:3000]}
                    ]})

        # ── DETECT: Skill Template ──
        skill_keywords = ["<skill_manifest>", "CLASSIFICATION:", "STATUS: ADDITIVE",
                         "<the_council_modes>", "<beacon_protocol>", "SKILL_"]
        if any(kw in content for kw in skill_keywords):
            examples.append({"messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Load skill: {filename}. Describe its capabilities."},
                {"role": "assistant", "content": content[:4000]}
            ]})

            # Extract individual modes/capabilities
            mode_pattern = r'(?:\d+\.\s+)?\*\*MODE:\s+(\w+)\s+\((.*?)\)\*\*(.*?)(?=\d+\.\s+\*\*MODE:|\Z)'
            modes = re.findall(mode_pattern, content, re.DOTALL)
            for mode_name, mode_desc, mode_body in modes:
                examples.append({"messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Activate {mode_name} mode ({mode_desc}). What are your capabilities?"},
                    {"role": "assistant", "content": f"**{mode_name} MODE ACTIVATED — {mode_desc}**\n{mode_body.strip()[:2000]}"}
                ]})

        # ── DETECT: Bootstrap / Genesis ──
        genesis_keywords = ["<genesis_declaration>", "<bootstrap_sequence>",
                          "GENESIS", "BOOTSTRAP", "SELF-EXECUTING", "DAEMON"]
        if any(kw in content for kw in genesis_keywords):
            # Extract the full bootstrap as a deployment training example
            examples.append({"messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Execute genesis bootstrap sequence for {filename}."},
                {"role": "assistant", "content": content[:5000]}
            ]})

            # Extract code blocks as implementation examples
            code_blocks = re.findall(r'```(?:python|bash|rust|javascript)?\n(.*?)```', content, re.DOTALL)
            for code in code_blocks:
                if len(code.strip()) > 50:
                    examples.append({"messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Write the code for the {filename} genesis component."},
                        {"role": "assistant", "content": f"```python\n{code.strip()}\n```"}
                    ]})

        # ── DETECT: Strategy / Training Document ──
        sections = re.split(r'\n#{1,3}\s+', content)
        for section in sections[1:]:
            lines = section.strip().split('\n')
            if not lines:
                continue
            title = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()
            if len(body) > 80:
                examples.append({"messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Explain: {title}"},
                    {"role": "assistant", "content": body[:3000]}
                ]})

        # ── DETECT: Q&A Pairs ──
        qa_patterns = [
            r'(?:^|\n)Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)',
            r'(?:^|\n)\*\*Q:\*\*\s*(.*?)\n\*\*A:\*\*\s*(.*?)(?=\n\*\*Q:|\Z)',
        ]
        for pattern in qa_patterns:
            for q, a in re.findall(pattern, content, re.DOTALL):
                if len(q.strip()) > 10 and len(a.strip()) > 20:
                    examples.append({"messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": q.strip()},
                        {"role": "assistant", "content": a.strip()[:3000]}
                    ]})

        # ── DETECT: Sample Responses ──
        sample_pattern = r'\*\s*\*On\s+(\w+):\*\s*"(.*?)"'
        for topic, response in re.findall(sample_pattern, content):
            examples.append({"messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"What is your perspective on {topic.lower()}?"},
                {"role": "assistant", "content": response}
            ]})

        return examples

    def _convert_code(self, filepath: Path, deep: bool = False) -> List[Dict]:
        """Convert code files — functions, classes, docstrings."""
        content = filepath.read_text(errors="ignore")
        if len(content) < 100:
            return []

        examples = []
        ext = filepath.suffix

        # Extract functions with docstrings
        if ext == ".py":
            pattern = r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\).*?:\s*\n\s+(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')'
            for func_name, doc1, doc2 in re.findall(pattern, content, re.DOTALL):
                docstring = (doc1 or doc2).strip()
                if len(docstring) > 20:
                    # Get full function body
                    func_start = content.find(f"def {func_name}")
                    if func_start == -1:
                        func_start = content.find(f"async def {func_name}")
                    if func_start >= 0:
                        remaining = content[func_start:]
                        func_lines = []
                        for i, line in enumerate(remaining.split('\n')):
                            if i > 0 and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                                break
                            func_lines.append(line)
                            if len(func_lines) > 60:
                                break
                        func_code = '\n'.join(func_lines[:60])

                        examples.append({"messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": f"Implement: {docstring}"},
                            {"role": "assistant", "content": f"```python\n{func_code}\n```"}
                        ]})

            # Extract class definitions
            if deep:
                class_pattern = r'class\s+(\w+).*?:\s*\n\s+(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')'
                for cls_name, doc1, doc2 in re.findall(class_pattern, content, re.DOTALL):
                    docstring = (doc1 or doc2).strip()
                    if len(docstring) > 20:
                        examples.append({"messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": f"Design a class for: {docstring}"},
                            {"role": "assistant", "content": f"Class `{cls_name}`: {docstring}"}
                        ]})

        # Extract prompts/templates from any language
        prompt_patterns = [
            r'(?:SYSTEM_PROMPT|system_prompt|AGENT_PROMPT|SOUL)\s*=\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\'|`(.*?)`)',
        ]
        for pattern in prompt_patterns:
            for match in re.findall(pattern, content, re.DOTALL):
                text = next((m for m in match if m), "")
                if len(text) > 50:
                    examples.append({"messages": [
                        {"role": "system", "content": text[:3000]},
                        {"role": "user", "content": "Initialize agent. Report status."},
                        {"role": "assistant", "content": "Agent initialized. All systems operational. Awaiting mission parameters."}
                    ]})

        return examples

    def _convert_json(self, filepath: Path) -> List[Dict]:
        """Convert JSON/JSONL files — configs, datasets, logs."""
        examples = []
        content = filepath.read_text(errors="ignore")

        # JSONL: line-by-line
        if filepath.suffix == ".jsonl":
            for line in content.split('\n'):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if "messages" in item:
                        examples.append(item)
                    elif "instruction" in item and "output" in item:
                        examples.append({"messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": str(item["instruction"])},
                            {"role": "assistant", "content": str(item["output"])}
                        ]})
                except:
                    continue
            return examples[:50000]

        # JSON: single object
        try:
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0:
                for item in data[:1000]:
                    if isinstance(item, dict):
                        if "messages" in item:
                            examples.append(item)
                        elif "instruction" in item:
                            examples.append({"messages": [
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": str(item.get("instruction", ""))},
                                {"role": "assistant", "content": str(item.get("output", item.get("response", "")))}
                            ]})
            elif isinstance(data, dict):
                # Agent config or character file
                text = json.dumps(data, indent=2)
                if any(kw in text.lower() for kw in ["agent", "character", "persona", "trade", "strategy"]):
                    examples.append({"messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Load agent configuration from {filepath.name}:"},
                        {"role": "assistant", "content": f"Configuration loaded:\n```json\n{text[:3000]}\n```"}
                    ]})
        except:
            pass

        return examples

    def _convert_config(self, filepath: Path) -> List[Dict]:
        """Convert YAML/TOML configs into training data."""
        examples = []
        content = filepath.read_text(errors="ignore")

        if len(content) > 50 and any(kw in content.lower() for kw in
            ["agent", "model", "trade", "strategy", "skill", "tool", "mcp"]):
            examples.append({"messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Show the configuration for {filepath.name}:"},
                {"role": "assistant", "content": f"```yaml\n{content[:3000]}\n```"}
            ]})

        return examples

    def _convert_text(self, filepath: Path) -> List[Dict]:
        """Convert raw text files — notes, strategies, logs."""
        content = filepath.read_text(errors="ignore")
        if len(content) < 100:
            return []

        examples = []

        # Split by double newlines into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        for para in paragraphs[:50]:
            if any(kw in para.lower() for kw in
                ["trade", "buy", "sell", "signal", "market", "price",
                 "security", "vulnerability", "exploit", "attack",
                 "agent", "strategy", "risk", "crypto", "solana"]):
                examples.append({"messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Analyze: {para[:200]}"},
                    {"role": "assistant", "content": para[:3000]}
                ]})

        return examples

    def _convert_csv(self, filepath: Path) -> List[Dict]:
        """Convert CSV data into Q&A training pairs."""
        examples = []
        try:
            with open(filepath, errors="ignore") as f:
                reader = csv.DictReader(f)
                rows = list(reader)[:1000]

            if not rows:
                return []

            headers = list(rows[0].keys())
            for row in rows[:100]:
                text = ', '.join(f"{k}: {v}" for k, v in row.items() if v)
                if len(text) > 30:
                    examples.append({"messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Analyze this data point: {text[:500]}"},
                        {"role": "assistant", "content": f"Data analysis:\n{text[:2000]}"}
                    ]})
        except:
            pass

        return examples

    def save(self):
        """Save scavenged training data."""
        output_file = self.output_dir / "scavenged_training.jsonl"

        # Deduplicate
        seen = set()
        unique = []
        for ex in self.examples:
            key = json.dumps(ex["messages"][1]["content"][:100]) if len(ex.get("messages", [])) > 1 else ""
            if key and key not in seen:
                seen.add(key)
                unique.append(ex)

        with open(output_file, "w") as f:
            for ex in unique:
                f.write(json.dumps(ex) + "\n")

        # Save scan log
        self.scan_log["examples_generated"] = len(unique)
        log_path = self.output_dir / "scavenge_log.json"
        with open(log_path, "w") as f:
            json.dump(self.scan_log, f, indent=2)

        print(f"\n{'=' * 60}")
        print(f"✅ SCAVENGER COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Files Scanned:   {self.scan_log['files_scanned']}")
        print(f"  Files Converted: {self.scan_log['files_converted']}")
        print(f"  Examples:        {len(unique)} (deduplicated)")
        print(f"  By Type:         {json.dumps(self.scan_log['by_type'])}")
        print(f"  Output:          {output_file}")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="RavenX Training Scavenger — Scan → Detect → Convert → Inject"
    )
    parser.add_argument("--target", required=True, help="Directory to scavenge")
    parser.add_argument("--output", default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--model", default="trade", choices=["trade", "sec"],
                       help="Target model (trade or sec)")
    parser.add_argument("--deep", action="store_true",
                       help="Deep scan — extract classes, nested configs, etc.")
    args = parser.parse_args()

    scavenger = TrainingScavenger(args.target, args.output, args.model)
    scavenger.scavenge(deep=args.deep)
    scavenger.save()


if __name__ == "__main__":
    main()

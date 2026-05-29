#!/usr/bin/env python3
"""
prepare_v3_data.py — Build the FINAL v4.0 mega training dataset

The most complete infosec + agent + tool-calling training corpus:
- 11 security-specific HuggingFace datasets
- 7 NEW: tool calling, MCP, agent, coding, reasoning datasets
- Original: Mythos 25K + AgentAngel (capped 50K) + extracted repo data

Usage:
    python tools/prepare_v3_data.py --output data/
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict

random.seed(42)


# All 11 security datasets (from v3.0)
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
    # nangyall/4-Security-Tools-Pentesting — replaced by Whoisjutanlee version
    "Whoisjutanlee/4-Security-Tools-Pentesting",
]

# NEW: 6 tool-calling, agent, coding, reasoning datasets (v4.0)
AGENT_TOOL_DATASETS = [
    "burtenshaw/agent-tools",
    "Nanbeige/ToolMind",
    "togethercomputer/CoderForge-Preview",
    "automatelab/mcp-servers-tool-catalog",
    "Jackrong/Claude-opus-4.7-TraceInversion-5000x",
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

    # Trendyol format: system/user/assistant as top-level keys
    if "system" in item and "user" in item and "assistant" in item:
        system_content = str(item["system"])
        user_content = str(item["user"])
        assistant_content = str(item["assistant"])
        if user_content and assistant_content:
            msgs = []
            if system_content:
                msgs.append({"role": "system", "content": system_content})
            msgs.append({"role": "user", "content": user_content})
            msgs.append({"role": "assistant", "content": assistant_content})
            return {"messages": msgs}

    # CVE-SFT format: structured CVE fields → RATH instruction pair
    if "cve_id" in item and "cvss_score" in item:
        cve_id = item.get("cve_id", "")
        cvss = item.get("cvss_score", "")
        cvss_vec = item.get("cvss_vector", "")
        cwe = item.get("cwe_id", "")
        software = item.get("affected_software", "")
        versions = item.get("affected_versions", "")
        explanation = item.get("plain_explanation", "")
        deep_dive = item.get("technical_deep_dive", "")
        attack = item.get("attack_scenario", "")
        remediation = item.get("remediation", "")
        vuln_code = item.get("vulnerable_code_example", "")
        exploit = item.get("exploit_poc", "")

        user_prompt = f"Analyze {cve_id} affecting {software} {versions}. Provide RATH protocol assessment."
        assistant_response = f"""**RATH STEP 1: IDENTIFY**
- CVE: {cve_id}
- Affected: {software} {versions}
- CWE: {cwe}
- Description: {explanation}

**RATH STEP 2: ASSESS**
- CVSS Score: {cvss}
- CVSS Vector: {cvss_vec}
- Technical Analysis: {deep_dive}

**RATH STEP 3: THREAT**
- Attack Scenario: {attack}
{f'- Vulnerable Code: {vuln_code[:500]}' if vuln_code else ''}
{f'- Exploit PoC: {exploit[:500]}' if exploit else ''}

**RATH STEP 4: REMEDIATE**
{remediation}"""

        return {"messages": [
            {"role": "system", "content": "You are RavenX-Sec. Follow the RATH protocol for every finding."},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response}
        ]}

    # Rootkit7/pentest-redteam format: goal/target
    if "goal" in item and "target" in item:
        goal = str(item["goal"])
        target = str(item["target"])
        if goal and target and len(target) > 20:
            return {"messages": [
                {"role": "user", "content": goal},
                {"role": "assistant", "content": target}
            ]}

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
    print("  RavenX-Sec v4.0 — THE FINAL TRAINING")
    print("  Security + Tool Calling + MCP + Agent + Coding + Reasoning")
    print("=" * 70)

    # ── 1. Load security datasets ─────────────────────────────────────
    print(f"\n[Phase 1] Loading {len(SECURITY_DATASETS)} security datasets...")
    for i, ds_name in enumerate(SECURITY_DATASETS, 1):
        print(f"\n  [{i}/{len(SECURITY_DATASETS)}] {ds_name}")
        examples = load_hf_dataset(ds_name, max_samples=50000)
        print(f"    → {len(examples)} usable examples")
        all_security.extend(examples)

    print(f"\n  Phase 1 total: {len(all_security)} security examples")

    # ── 2. Load agent/tool/coding/reasoning datasets (NEW v4.0) ──────
    all_agent_tools = []
    print(f"\n[Phase 2] Loading {len(AGENT_TOOL_DATASETS)} agent/tool/coding datasets...")
    for i, ds_name in enumerate(AGENT_TOOL_DATASETS, 1):
        print(f"\n  [{i}/{len(AGENT_TOOL_DATASETS)}] {ds_name}")
        examples = load_hf_dataset(ds_name, max_samples=50000)
        print(f"    → {len(examples)} usable examples")
        all_agent_tools.extend(examples)

    print(f"\n  Phase 2 total: {len(all_agent_tools)} agent/tool examples")

    # ── 3. Load Mythos (security categories) ──────────────────────────
    print(f"\n[Phase 3] Loading {MYTHOS_DATASET}...")
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

    # ── 4. Load AgentAngel (capped) ───────────────────────────────────
    if not args.skip_agent:
        print(f"\n[Phase 4] Loading {AGENT_DATASET} (capped at {AGENT_CAP})...")
        agent_examples = load_agent_angel()
        random.shuffle(agent_examples)
        agent_capped = agent_examples[:AGENT_CAP]
        print(f"  AgentAngel: {len(agent_examples)} → capped to {len(agent_capped)}")
        all_agentic.extend(agent_capped)
    else:
        print("\n[Phase 4] Skipping AgentAngel")

    # ── 5. Extract from OpenMythos repo ───────────────────────────────
    print(f"\n[Phase 5] Extracting from OpenMythos...")
    openmythos_path = Path(args.output).parent / "Developer" / "OpenMythos"
    if not openmythos_path.exists():
        openmythos_path = Path.home() / "Developer" / "OpenMythos"
    if not openmythos_path.exists():
        # Try to clone it
        import subprocess
        print("  Cloning OpenMythos...")
        try:
            subprocess.run(["git", "clone", "https://github.com/DeadByDawn101/OpenMythos.git",
                          str(openmythos_path)], capture_output=True, timeout=60)
        except Exception:
            pass

    mythos_examples = []
    if openmythos_path.exists():
        # Extract from Python/MD files — architecture patterns, training methodology
        for pyfile in openmythos_path.rglob("*.py"):
            if ".git" in str(pyfile):
                continue
            try:
                content = pyfile.read_text(errors="ignore")
                if len(content) > 200:
                    import re
                    # Extract docstrings and class descriptions
                    docstrings = re.findall(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', content, re.DOTALL)
                    for doc in docstrings:
                        if len(doc) > 100:
                            mythos_examples.append({"messages": [
                                {"role": "user", "content": f"Explain this AI architecture component:\n\n{doc.strip()[:2000]}"},
                                {"role": "assistant", "content": f"This component implements a Recurrent-Depth Transformer (RDT) architecture pattern. {doc.strip()[:1500]}"}
                            ]})
            except Exception:
                continue

        for mdfile in openmythos_path.rglob("*.md"):
            if ".git" in str(mdfile):
                continue
            try:
                content = mdfile.read_text(errors="ignore")
                if len(content) > 500:
                    mythos_examples.append({"messages": [
                        {"role": "user", "content": f"Analyze this AI architecture documentation:\n\n{content[:2000]}"},
                        {"role": "assistant", "content": f"This documentation describes advanced AI architecture patterns including Mixture of Experts (MoE), Multi-Latent Attention (MLA), and Recurrent-Depth Transformers. These are relevant for building scalable, efficient models."}
                    ]})
            except Exception:
                continue

        print(f"  OpenMythos: {len(mythos_examples)} examples extracted")
        all_other.extend(mythos_examples)
    else:
        print("  OpenMythos: not found (skipping)")

    # ── 6. Load local extracted data ──────────────────────────────────
    print(f"\n[Phase 6] Loading local extracted data...")
    local = load_local_data(output_dir)
    print(f"  Local security data: {len(local)} examples")
    all_security.extend(local)

    # ── 7. Combine with security-dominant weighting ───────────────────
    print(f"\n[Phase 7] Combining — THE FINAL MIX...")
    print(f"  Security examples (raw): {len(all_security)}")
    print(f"  Agent/Tool examples: {len(all_agent_tools)}")
    print(f"  Agentic examples: {len(all_agentic)}")
    print(f"  Other examples: {len(all_other)}")

    # Security 2x, agent/tool 1x, agentic 1x, other 1x
    combined = (
        all_security * 2 +
        all_agent_tools +
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

    total = len(combined)
    sec_count = len(all_security) * 2
    agent_count = len(all_agent_tools)
    agentic_count = len(all_agentic)
    other_count = len(all_other)

    print(f"\n{'=' * 70}")
    print(f"  ✅ RavenX-Sec v4.0 — THE FINAL TRAINING DATA")
    print(f"{'=' * 70}")
    print(f"  Training:    {len(train_data):,} examples → {train_file}")
    print(f"  Validation:  {len(valid_data):,} examples → {valid_file}")
    print(f"  Security:    {len(all_security):,} × 2 = {sec_count:,} ({sec_count/total*100:.0f}%)")
    print(f"  Agent/Tool:  {agent_count:,} ({agent_count/total*100:.0f}%)")
    print(f"  Agentic:     {agentic_count:,} ({agentic_count/total*100:.0f}%)")
    print(f"  Other:       {other_count:,} ({other_count/total*100:.0f}%)")
    print(f"  TOTAL:       {total:,}")
    print(f"{'=' * 70}")
    print(f"  Datasets:    {len(SECURITY_DATASETS) + len(AGENT_TOOL_DATASETS) + 3} sources")
    print(f"  This is the most complete infosec + agent model ever trained.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

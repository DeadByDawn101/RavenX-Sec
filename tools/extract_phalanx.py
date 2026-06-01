#!/usr/bin/env python3
"""
extract_phalanx.py — Extract Phalanx autonomous pentesting framework into RavenX-Sec training data
CLASSIFICATION: PROPRIETARY / RavenX LLC

Phalanx (github.com/DeadByDawn101/phalanx) is a Kali Linux polyglot harness
for autonomous pentesting. This script extracts its architecture, agent patterns,
tool usage, RoE enforcement, and pentest methodology into instruction-tuning JSONL.

Usage:
    python tools/extract_phalanx.py --input ~/path/to/phalanx --output data/extracted/phalanx_training.jsonl
"""

import json
import re
import argparse
from pathlib import Path
from typing import List, Dict

SYSTEM_PROMPT = """You are RavenX-Sec, an autonomous security intelligence model. Follow the RATH protocol (Risk, Assess, Threat, Highlight, Document, Prevent) for every finding. You have deep knowledge of autonomous pentesting frameworks, SWARM agent architectures, and offensive security tooling."""


def extract_agent_classes(content: str, filename: str) -> List[Dict]:
    """Extract agent class definitions as architecture training data."""
    examples = []
    
    # Find class definitions with docstrings
    class_pattern = r'class\s+(\w+Agent)\s*\(.*?\):\s*\n(.*?)(?=\nclass\s|\Z)'
    matches = re.findall(class_pattern, content, re.DOTALL)
    
    for class_name, class_body in matches:
        # Get first 1500 chars of class body
        body = class_body.strip()[:1500]
        
        # Extract the run/execute method
        run_match = re.search(r'(async\s+)?def\s+(run|execute|step)\s*\(.*?\).*?(?=\n    def\s|\Z)', class_body, re.DOTALL)
        run_body = run_match.group(0)[:1000] if run_match else ""
        
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Explain the {class_name} architecture in an autonomous pentesting SWARM."},
            {"role": "assistant", "content": f"The {class_name} is a specialized agent in the SWARM architecture:\n\n```python\n{body[:1200]}\n```\n\nThis agent operates within the SWARM orchestration framework, receiving tasks from the orchestrator, executing its specialty, and reporting findings back to the shared database."}
        ]})
        
        if run_body:
            examples.append({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"How does the {class_name} execute its primary function?"},
                {"role": "assistant", "content": f"The {class_name}'s execution logic:\n\n```python\n{run_body[:1500]}\n```\n\nThis implements the agent's core pentesting workflow, integrating with the tool registry and reporting findings through the structured Finding dataclass."}
            ]})
    
    return examples


def extract_tool_definitions(content: str) -> List[Dict]:
    """Extract security tool definitions and parsers."""
    examples = []
    
    # Find tool function definitions
    tool_funcs = re.findall(
        r'(?:async\s+)?def\s+(run_\w+|tool_\w+|_parse_\w+)\s*\(.*?\).*?"""(.*?)"""',
        content, re.DOTALL
    )
    
    for func_name, docstring in tool_funcs:
        if len(docstring.strip()) > 20:
            tool_name = func_name.replace("run_", "").replace("tool_", "").replace("_parse_", "parse ")
            examples.append({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"How do you use {tool_name} in an autonomous pentest?"},
                {"role": "assistant", "content": f"In an autonomous pentesting context, {tool_name} is used as follows:\n\n{docstring.strip()[:800]}\n\nThe tool integrates with the SWARM framework through the tool registry, providing structured output that feeds into the Finding dataclass for severity classification and MITRE ATT&CK mapping."}
            ]})
    
    # Extract tool registry entries
    registry_entries = re.findall(
        r'TOOL_REGISTRY\["(\w+)"\]\s*=\s*\{(.*?)\}',
        content, re.DOTALL
    )
    
    for tool_name, tool_config in registry_entries:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"What is the tool registry definition for {tool_name}?"},
            {"role": "assistant", "content": f"The {tool_name} tool is registered in the SWARM framework:\n\n```python\nTOOL_REGISTRY[\"{tool_name}\"] = {{{tool_config.strip()[:500]}}}\n```\n\nThis definition allows the SWARM orchestrator to discover, configure, and execute {tool_name} during autonomous pentesting engagements."}
        ]})
    
    return examples


def extract_roe_patterns(content: str) -> List[Dict]:
    """Extract Rules of Engagement enforcement patterns."""
    examples = []
    
    # Find RoE-related code blocks
    roe_blocks = re.findall(
        r'(class\s+RoE\w*.*?(?=\nclass\s|\Z))',
        content, re.DOTALL
    )
    
    for block in roe_blocks:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "How do you enforce Rules of Engagement (RoE) during an autonomous pentest?"},
            {"role": "assistant", "content": f"Rules of Engagement enforcement is critical in autonomous pentesting:\n\n```python\n{block[:1500]}\n```\n\nThe RoE enforcer validates every action against:\n- **forbidden_actions**: Actions that are never allowed (e.g., data_exfiltration, destruction)\n- **require_human_confirm**: Actions needing manual approval (e.g., privilege_escalation, exploit, auth_bypass)\n- **max_severity**: Maximum severity level the engagement allows\n- **allowed_targets**: Scope boundaries\n\nThis prevents autonomous agents from exceeding their authorized scope."}
        ]})
    
    # Extract forbidden actions and confirmation patterns
    forbidden = re.findall(r'"forbidden_actions":\s*\[(.*?)\]', content)
    confirm = re.findall(r'"require_human_confirm":\s*\[(.*?)\]', content)
    
    if forbidden:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "What actions are forbidden during autonomous pentesting?"},
            {"role": "assistant", "content": f"In a properly configured autonomous pentesting framework, the following actions are FORBIDDEN:\n\n- **data_exfiltration**: Never extract actual sensitive data from the target\n- **destruction**: Never destroy or modify production data\n- **denial_of_service**: Never intentionally disrupt service availability\n\nActions requiring HUMAN CONFIRMATION:\n- **privilege_escalation**: Before escalating privileges\n- **exploit**: Before running active exploits\n- **auth_bypass**: Before attempting authentication bypass\n- **data_modification**: Before any write operations\n- **race_condition**: Before testing for race conditions\n\nThese Rules of Engagement (RoE) are enforced programmatically — the agent physically cannot execute forbidden actions regardless of what the LLM suggests."}
        ]})
    
    return examples


def extract_finding_patterns(content: str) -> List[Dict]:
    """Extract Finding dataclass and severity classification."""
    examples = []
    
    # Find Finding dataclass
    finding_match = re.search(r'@dataclass\s*\nclass\s+Finding.*?(?=\ndef\s|\nclass\s|\Z)', content, re.DOTALL)
    if finding_match:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "How do you structure security findings in an autonomous pentest?"},
            {"role": "assistant", "content": f"Security findings are structured using the Finding dataclass:\n\n```python\n{finding_match.group(0)[:1000]}\n```\n\nEach finding captures:\n- **tool**: Which tool discovered it\n- **target**: The affected asset\n- **severity**: info / low / medium / high / critical\n- **description**: Human-readable explanation\n- **raw_output**: Tool's original output for evidence\n- **parsed**: Structured data extracted from output\n- **timestamp**: When discovered\n\nFindings are stored in the database and feed into the Shadow Graph for attack path visualization."}
        ]})
    
    return examples


def extract_engagement_plans(content: str) -> List[Dict]:
    """Extract engagement planning with MITRE ATT&CK mapping."""
    examples = []
    
    # Find MITRE tags
    mitre_blocks = re.findall(r'"mitre_tags":\s*\[(.*?)\]', content)
    objectives = re.findall(r'"description":\s*f?"(.*?)".*?"mitre_tags":\s*\[(.*?)\]', content)
    
    if objectives:
        obj_text = "\n".join([f"- {desc} (MITRE: {tags})" for desc, tags in objectives[:10]])
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Generate an engagement plan with MITRE ATT&CK mapping for a web application pentest."},
            {"role": "assistant", "content": f"Engagement Plan (OPPLAN) with MITRE ATT&CK mapping:\n\n**Phase 1 — Reconnaissance (T1595)**\n- Active scanning of target infrastructure\n- Technology fingerprinting and service enumeration\n\n**Phase 2 — Vulnerability Assessment (T1595.002)**\n- Automated vulnerability scanning (nuclei, nikto)\n- Manual verification of high-severity findings\n\n**Phase 3 — Exploitation (T1190)**\n- Exploit public-facing application vulnerabilities\n- Authentication bypass testing\n- Injection attack testing (SQL, XSS, SSRF, RCE)\n\n**Phase 4 — Post-Exploitation (T1555)**\n- Credential harvesting from compromised services\n- Lateral movement assessment\n- Data access verification\n\n**Rules of Engagement:**\n- Forbidden: data_exfiltration, destruction\n- Require confirmation: privilege_escalation, exploit, auth_bypass\n- Maximum severity: critical\n\nAll findings mapped to MITRE ATT&CK framework for standardized reporting."}
        ]})
    
    return examples


def extract_swarm_architecture(content: str) -> List[Dict]:
    """Extract SWARM orchestration patterns."""
    examples = []
    
    # Find SwarmOrchestrator
    swarm_match = re.search(r'class\s+SwarmOrchestrator.*?(?=\nclass\s(?!Sub)|\Z)', content, re.DOTALL)
    if swarm_match:
        swarm_body = swarm_match.group(0)[:2000]
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Explain the SWARM architecture for autonomous pentesting."},
            {"role": "assistant", "content": f"The SWARM architecture uses multiple specialized agents working in coordination:\n\n**Agent Hierarchy:**\n1. **ReconAgent**: Performs reconnaissance (nmap, whatweb, gobuster)\n2. **ClassifyAgent**: Classifies findings by severity and maps to MITRE ATT&CK\n3. **ExploitAgent**: Executes exploitation based on classified vulnerabilities\n4. **ReportAgent**: Generates structured reports from findings\n5. **ReflectorAgent**: Analyzes the Shadow Graph for strategic insights\n\n**Orchestration Flow:**\n- Orchestrator receives engagement plan with objectives\n- Dispatches ReconAgent for initial target enumeration\n- ClassifyAgent triages findings by severity\n- ExploitAgent attempts exploitation (with RoE enforcement)\n- ReflectorAgent queries the Shadow Graph for attack paths\n- ReportAgent compiles final deliverable\n\n**Key Features:**\n- ReAct loop with reflection for adaptive decision-making\n- Sub-swarm spawning for complex tasks\n- Thread-safe campaign management\n- Shared Soul memory across all agents"}
        ]})
    
    return examples


def extract_docker_sandbox(content: str) -> List[Dict]:
    """Extract Docker sandbox execution patterns."""
    examples = []
    
    sandbox_blocks = re.findall(
        r'(def\s+.*?sandbox.*?(?=\ndef\s|\Z))',
        content, re.DOTALL | re.IGNORECASE
    )
    
    if sandbox_blocks:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "How do you safely execute security tools in an autonomous pentest?"},
            {"role": "assistant", "content": "All security tool execution runs inside a Docker sandbox for safety:\n\n**Sandbox Architecture:**\n- Base image: `kalilinux/kali-rolling`\n- Isolated network: `phalanx-net`\n- No host filesystem access (bind mounts only for results)\n- Timeout enforcement on all commands\n- stdin closed to prevent interactive hangs\n\n**Tool Execution Flow:**\n1. Command is validated against RoE (forbidden actions check)\n2. Docker container is created with the sandboxed environment\n3. Tool executes with enforced timeout\n4. Output is captured and parsed by tool-specific parsers\n5. Findings are extracted and stored in the database\n6. Container is destroyed after execution\n\n**Safety Controls:**\n- `require_confirm_sudo: true` — all sudo commands need manual approval\n- `max_severity: critical` — severity ceiling prevents catastrophic actions\n- Command injection prevention (no shell wrapper, shlex parsing)\n- All tool output logged for audit trail"}
        ]})
    
    return examples


def extract_polyglot_engine(content: str) -> List[Dict]:
    """Extract polyglot tool execution patterns."""
    examples = []
    
    # Languages supported
    lang_refs = re.findall(r'(Python|JavaScript|Ruby|Rust|Go|Bash|OCaml|WebAssembly|Java|C\+\+)', content)
    unique_langs = list(set(lang_refs))
    
    if len(unique_langs) > 3:
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "What languages can the polyglot pentesting engine execute?"},
            {"role": "assistant", "content": f"The polyglot ToolExecutor supports tools written in multiple languages:\n\n- **Python**: Primary language for tool scripting and automation\n- **Bash**: Shell scripts for quick reconnaissance and enumeration\n- **JavaScript/Node.js**: Browser automation and web scraping\n- **Ruby**: Metasploit modules and exploit frameworks\n- **Go**: High-performance tools (gobuster, ffuf, nuclei)\n- **Rust**: Memory-safe exploit development\n- **C/C++**: Low-level exploit code and buffer overflow tools\n- **WebAssembly**: Sandboxed execution of portable tools\n\nAll tools are executed inside a Docker sandbox with Kali Linux, providing access to the full Kali toolchain while maintaining isolation from the host system."}
        ]})
    
    return examples


def extract_functions_as_qa(content: str, filename: str) -> List[Dict]:
    """Extract documented functions as Q&A training pairs."""
    examples = []
    
    # Find functions with docstrings related to security
    sec_keywords = ["scan", "exploit", "vuln", "finding", "recon", "pentest", "target",
                    "attack", "payload", "inject", "brute", "fuzz", "enum", "privesc",
                    "loot", "credential", "session", "engagement", "roe", "swarm"]
    
    func_pattern = r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\).*?:\s*\n\s+"""(.*?)"""'
    matches = re.findall(func_pattern, content, re.DOTALL)
    
    for func_name, docstring in matches:
        doc = docstring.strip()
        if len(doc) > 30 and any(kw in func_name.lower() or kw in doc.lower() for kw in sec_keywords):
            # Get full function body (up to 60 lines)
            func_start = content.find(f"def {func_name}")
            if func_start == -1:
                func_start = content.find(f"async def {func_name}")
            if func_start >= 0:
                remaining = content[func_start:]
                lines = []
                for i, line in enumerate(remaining.split('\n')):
                    if i > 0 and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                        break
                    lines.append(line)
                    if len(lines) > 50:
                        break
                func_code = '\n'.join(lines[:50])
                
                examples.append({"messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Implement: {doc[:200]}"},
                    {"role": "assistant", "content": f"```python\n{func_code}\n```"}
                ]})
    
    return examples


def extract_config_as_knowledge(content: str) -> List[Dict]:
    """Extract configuration patterns as security knowledge."""
    examples = []
    
    # Find JSON config blocks
    config_blocks = re.findall(r'(\w+_JSON|_default_config|CONFIG_JSON)\s*=\s*(\{.*?\n\})', content, re.DOTALL)
    
    for config_name, config_body in config_blocks:
        if len(config_body) > 100:
            examples.append({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "What is the recommended configuration for an autonomous pentesting framework?"},
                {"role": "assistant", "content": f"A properly configured autonomous pentesting framework includes:\n\n```json\n{config_body[:2000]}\n```\n\nKey configuration sections:\n- **ollama**: LLM model routing (fast model for recon, analysis model for exploitation)\n- **pentest**: Docker image, max steps, auto-searchsploit\n- **engagement.default_roe**: Rules of Engagement with forbidden actions and confirmation requirements\n- **sandbox**: Docker isolation for safe tool execution\n- **swarm**: Agent parallelism, model selection, step limits\n- **shadow_graph**: Attack graph persistence and visualization"}
            ]})
    
    return examples


def main():
    parser = argparse.ArgumentParser(description="Extract Phalanx pentesting framework as RavenX-Sec training data")
    parser.add_argument("--input", default="/home/claude/phalanx", help="Path to phalanx repo")
    parser.add_argument("--output", default="data/extracted/phalanx_training.jsonl", help="Output JSONL")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("PHALANX SECURITY DATASET EXTRACTOR")
    print("Source: github.com/DeadByDawn101/phalanx")
    print("Target: RavenX-Sec training data")
    print("=" * 60)
    
    all_examples = []
    
    # Process all Python files
    py_files = sorted(input_path.rglob("*.py"))
    print(f"\nFound {len(py_files)} Python files\n")
    
    for filepath in py_files:
        try:
            content = filepath.read_text(errors="ignore")
        except:
            continue
        
        if len(content) < 100:
            continue
        
        fname = filepath.name
        examples = []
        
        examples.extend(extract_agent_classes(content, fname))
        examples.extend(extract_tool_definitions(content))
        examples.extend(extract_roe_patterns(content))
        examples.extend(extract_finding_patterns(content))
        examples.extend(extract_engagement_plans(content))
        examples.extend(extract_swarm_architecture(content))
        examples.extend(extract_docker_sandbox(content))
        examples.extend(extract_polyglot_engine(content))
        examples.extend(extract_functions_as_qa(content, fname))
        examples.extend(extract_config_as_knowledge(content))
        
        if examples:
            print(f"  {fname}: {len(examples)} examples")
            all_examples.extend(examples)
    
    # Deduplicate
    seen = set()
    unique = []
    for ex in all_examples:
        key = json.dumps(ex["messages"][1]["content"][:100])
        if key not in seen:
            seen.add(key)
            unique.append(ex)
    
    with open(output_path, "w") as f:
        for ex in unique:
            f.write(json.dumps(ex) + "\n")
    
    print(f"\n{'=' * 60}")
    print(f"✅ Extracted: {len(unique)} unique examples → {output_path}")
    print(f"   From: {len(py_files)} Python files ({sum(f.stat().st_size for f in py_files) // 1024} KB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

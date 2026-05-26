#!/usr/bin/env python3
"""
extract_ghidra.py — Extract RE analysis patterns from Ghidra scripts

Reads Ghidra analysis scripts, plugin code, and decompiler patterns to
generate training data for binary analysis and reverse engineering tasks.

Source: DeadByDawn101/ghidra (Apache-2.0)

Usage:
    python tools/extract_ghidra.py --repo-path /path/to/ghidra --output data/offensive/exploit_pocs/
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Dict


GHIDRA_ANALYSIS_PATTERNS = [
    {
        "instruction": "Analyze a binary for potential buffer overflow vulnerabilities using Ghidra decompiler output.",
        "input": "The decompiled function shows: void vulnerable_func(char *input) { char buf[64]; strcpy(buf, input); }",
        "output": json.dumps({
            "vulnerability": "Stack-based Buffer Overflow",
            "cwe": "CWE-121",
            "cvss": "9.8",
            "analysis": "The function uses strcpy() without bounds checking. The 64-byte stack buffer can be overflowed by any input longer than 63 bytes, potentially overwriting the return address.",
            "indicators": ["strcpy without length check", "fixed-size stack buffer", "user-controlled input"],
            "remediation": "Replace strcpy with strncpy(buf, input, sizeof(buf)-1) or use snprintf. Better: migrate to a memory-safe language.",
        }, indent=2),
    },
    {
        "instruction": "Identify the function calling convention and potential vulnerabilities from this disassembly.",
        "input": "PUSH RBP; MOV RBP,RSP; SUB RSP,0x40; MOV [RBP-0x38],RDI; LEA RAX,[RBP-0x30]; MOV RDI,RAX; CALL gets; LEAVE; RET",
        "output": json.dumps({
            "calling_convention": "System V AMD64 ABI (Linux x86_64)",
            "vulnerability": "gets() is inherently unsafe - no bounds checking",
            "cwe": "CWE-120",
            "stack_frame": "0x40 bytes allocated, buffer at RBP-0x30 (48 bytes to saved RBP)",
            "exploitation": "Input > 48 bytes overwrites saved RBP, > 56 bytes overwrites return address",
            "remediation": "Replace gets() with fgets(buf, sizeof(buf), stdin)",
        }, indent=2),
    },
    {
        "instruction": "Analyze this Ghidra decompiler output for format string vulnerabilities.",
        "input": "void log_input(char *user_data) { printf(user_data); }",
        "output": json.dumps({
            "vulnerability": "Format String Vulnerability",
            "cwe": "CWE-134",
            "cvss": "9.8",
            "analysis": "User-controlled data passed directly as format string to printf. Attacker can use %x to leak stack data, %n to write arbitrary memory.",
            "exploitation": "%08x.%08x.%08x leaks stack; %n writes to arbitrary address",
            "remediation": "Use printf(\"%s\", user_data) instead of printf(user_data)",
        }, indent=2),
    },
    {
        "instruction": "Analyze this binary for use-after-free vulnerabilities from Ghidra output.",
        "input": "obj = malloc(sizeof(struct data)); process(obj); free(obj); /* ... later ... */ obj->callback();",
        "output": json.dumps({
            "vulnerability": "Use-After-Free",
            "cwe": "CWE-416",
            "cvss": "8.8",
            "analysis": "Object is freed then dereferenced. If heap is manipulated between free() and use, attacker controls the callback pointer.",
            "exploitation": "Heap spray to place controlled data at freed address, redirect callback to shellcode",
            "remediation": "Set pointer to NULL after free (obj = NULL). Use smart pointers in C++. Enable MTE/PAC on ARM64.",
        }, indent=2),
    },
    {
        "instruction": "Perform taint analysis on this decompiled function to identify injection points.",
        "input": "void handle_request(int sock) { char query[256]; read(sock, query, 256); char sql[512]; sprintf(sql, \"SELECT * FROM users WHERE name='%s'\", query); db_execute(sql); }",
        "output": json.dumps({
            "vulnerability": "SQL Injection",
            "cwe": "CWE-89",
            "cvss": "9.8",
            "owasp": "A03:2021 - Injection",
            "taint_flow": "socket read → query buffer → sprintf → SQL string → database execution",
            "analysis": "User input from network socket flows directly into SQL query without sanitization or parameterization.",
            "exploitation": "Input: ' OR '1'='1' -- to bypass authentication, or UNION SELECT to extract data",
            "remediation": "Use parameterized queries / prepared statements. Never concatenate user input into SQL.",
        }, indent=2),
    },
]


def extract_ghidra_scripts(repo_path: str) -> List[Dict]:
    """Extract analysis patterns from Ghidra's Java/Python scripts."""
    patterns = []
    script_dirs = [
        Path(repo_path) / "Ghidra" / "Features" / "Base" / "ghidra_scripts",
        Path(repo_path) / "Ghidra" / "Features" / "Python" / "ghidra_scripts",
    ]

    for script_dir in script_dirs:
        if not script_dir.exists():
            continue

        for script_file in script_dir.rglob("*.java"):
            content = script_file.read_text(errors="ignore")
            if any(kw in content.lower() for kw in ["vulnerability", "overflow", "inject", "exploit", "malware"]):
                patterns.append({
                    "instruction": f"Explain what this Ghidra analysis script does and what security issues it detects.",
                    "input": content[:2000],
                    "output": f"This Ghidra script ({script_file.name}) performs automated binary analysis for security vulnerabilities.",
                })

    return patterns


def generate_synthetic_re_data() -> List[Dict]:
    """Generate synthetic RE training data from known patterns."""
    return GHIDRA_ANALYSIS_PATTERNS


def save_output(data: List[Dict], output_dir: str, prefix: str = "ghidra"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sft_file = output_path / f"{prefix}_sft.jsonl"
    with open(sft_file, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    print(f"Saved {len(data)} SFT examples to {sft_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract RE patterns from Ghidra")
    parser.add_argument("--repo-path", default="", help="Path to Ghidra repo (optional)")
    parser.add_argument("--output", default="data/offensive/exploit_pocs/", help="Output directory")
    parser.add_argument("--synthetic-only", action="store_true", help="Generate synthetic data only")
    args = parser.parse_args()

    all_data = []

    if args.repo_path and Path(args.repo_path).exists() and not args.synthetic_only:
        print(f"Extracting from {args.repo_path}...")
        all_data.extend(extract_ghidra_scripts(args.repo_path))

    print("Generating synthetic RE training data...")
    all_data.extend(generate_synthetic_re_data())
    print(f"Total: {len(all_data)} examples")

    save_output(all_data, args.output)


if __name__ == "__main__":
    main()

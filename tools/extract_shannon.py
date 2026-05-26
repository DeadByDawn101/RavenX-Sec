#!/usr/bin/env python3
"""
extract_shannon.py — Extract training data from Shannon white-box AI pentester

Reads Shannon's vulnerability discovery chains, exploit PoCs, and source code
analysis reports, converting them into RavenX-Sec training format.

Source: DeadByDawn101/shannon (96.15% XBOW, AGPL-3.0)

Usage:
    python tools/extract_shannon.py --repo-path /path/to/shannon --output data/offensive/exploit_pocs/
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any


def extract_from_reports(repo_path: str) -> List[Dict[str, Any]]:
    """Extract vulnerability reports from Shannon output."""
    traces = []
    report_dirs = [
        Path(repo_path) / "reports",
        Path(repo_path) / "output",
        Path(repo_path) / "results",
        Path(repo_path) / "findings",
    ]

    for report_dir in report_dirs:
        if not report_dir.exists():
            continue

        for report_file in report_dir.rglob("*.json"):
            try:
                with open(report_file) as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for finding in data:
                        trace = convert_finding(finding)
                        if trace:
                            traces.append(trace)
                elif isinstance(data, dict):
                    trace = convert_finding(data)
                    if trace:
                        traces.append(trace)
            except (json.JSONDecodeError, KeyError):
                continue

    return traces


def extract_from_source_analysis(repo_path: str) -> List[Dict[str, Any]]:
    """Extract source code → vulnerability mappings."""
    traces = []
    analysis_dirs = [
        Path(repo_path) / "analysis",
        Path(repo_path) / "src" / "analysis",
    ]

    for analysis_dir in analysis_dirs:
        if not analysis_dir.exists():
            continue

        for analysis_file in analysis_dir.rglob("*.json"):
            try:
                with open(analysis_file) as f:
                    data = json.load(f)

                trace = {
                    "source": "shannon_source_analysis",
                    "file_analyzed": data.get("file", "unknown"),
                    "language": data.get("language", "unknown"),
                    "vulnerabilities": data.get("vulnerabilities", []),
                    "exploits": data.get("exploits", []),
                }
                if trace["vulnerabilities"]:
                    traces.append(trace)
            except (json.JSONDecodeError, KeyError):
                continue

    return traces


def convert_finding(finding: Dict) -> Dict[str, Any]:
    """Convert a Shannon finding to training format."""
    vuln_type = finding.get("vulnerability_type", finding.get("type", "unknown"))
    if vuln_type == "unknown" and not finding.get("description"):
        return None

    return {
        "source": "shannon",
        "vulnerability_type": vuln_type,
        "severity": finding.get("severity", "unknown"),
        "cvss": finding.get("cvss_score", finding.get("cvss", "")),
        "cwe": finding.get("cwe", finding.get("cwe_id", "")),
        "description": finding.get("description", ""),
        "affected_code": finding.get("affected_code", finding.get("code_snippet", "")),
        "exploit_poc": finding.get("exploit", finding.get("poc", "")),
        "remediation": finding.get("remediation", finding.get("fix", "")),
        "owasp": finding.get("owasp_category", ""),
    }


def convert_to_sft_format(traces: List[Dict]) -> List[Dict[str, str]]:
    """Convert extracted traces to SFT instruction format."""
    sft_data = []

    for trace in traces:
        # Source code vulnerability analysis
        if "affected_code" in trace and trace.get("affected_code"):
            sft_data.append({
                "instruction": (
                    "Analyze this source code for security vulnerabilities. "
                    "Identify the vulnerability type, assign a CVSS score, map to CWE/OWASP, "
                    "and provide a specific code fix."
                ),
                "input": trace["affected_code"][:3000],
                "output": json.dumps({
                    "vulnerability_type": trace["vulnerability_type"],
                    "severity": trace["severity"],
                    "cvss": trace.get("cvss", ""),
                    "cwe": trace.get("cwe", ""),
                    "owasp": trace.get("owasp", ""),
                    "description": trace["description"],
                    "remediation": trace["remediation"],
                }, indent=2),
            })

        # Exploit chain generation
        if trace.get("exploit_poc"):
            sft_data.append({
                "instruction": (
                    f"Given a {trace['vulnerability_type']} vulnerability, "
                    f"describe the exploit chain and provide remediation steps."
                ),
                "input": trace["description"],
                "output": json.dumps({
                    "exploit_poc": trace["exploit_poc"],
                    "severity": trace["severity"],
                    "remediation": trace["remediation"],
                }, indent=2),
            })

        # Find→Classify→Fix chain
        sft_data.append({
            "instruction": (
                "You discovered a security vulnerability during white-box analysis. "
                "Classify it using CVSS, OWASP, and CWE, then provide remediation."
            ),
            "input": f"Vulnerability: {trace['vulnerability_type']}\nDescription: {trace['description']}",
            "output": json.dumps({
                "classification": {
                    "cvss": trace.get("cvss", "N/A"),
                    "cwe": trace.get("cwe", "N/A"),
                    "owasp": trace.get("owasp", "N/A"),
                    "severity": trace["severity"],
                },
                "remediation": trace.get("remediation", "Patch the affected code and validate the fix."),
            }, indent=2),
        })

    return sft_data


def save_output(data: List[Dict], output_dir: str, prefix: str = "shannon"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sft_file = output_path / f"{prefix}_sft.jsonl"
    with open(sft_file, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    print(f"Saved {len(data)} SFT examples to {sft_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract training data from Shannon")
    parser.add_argument("--repo-path", required=True, help="Path to Shannon repo")
    parser.add_argument("--output", default="data/offensive/exploit_pocs/", help="Output directory")
    args = parser.parse_args()

    if not Path(args.repo_path).exists():
        print(f"Error: Repo not found at {args.repo_path}")
        sys.exit(1)

    print(f"Extracting from {args.repo_path}...")
    traces = extract_from_reports(args.repo_path)
    traces.extend(extract_from_source_analysis(args.repo_path))
    print(f"Found {len(traces)} findings")

    sft_data = convert_to_sft_format(traces)
    print(f"Generated {len(sft_data)} SFT examples")

    save_output(sft_data, args.output)


if __name__ == "__main__":
    main()

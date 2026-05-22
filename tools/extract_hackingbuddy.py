#!/usr/bin/env python3
"""
extract_hackingbuddy.py — Extract training data from hackingBuddyGPT logs

Reads hackingBuddyGPT's SQLite logs and round-by-round interaction traces,
converting them into RavenX-Sec training format:
  - Offensive chains (command → result → next command)
  - State trajectories for LeWM world model
  - Find→classify→fix instruction pairs

Usage:
    python tools/extract_hackingbuddy.py --db path/to/wintermute.sqlite3 --output data/offensive/privesc_chains/
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any


def extract_rounds(db_path: str) -> List[Dict[str, Any]]:
    """Extract round-by-round interaction data from hackingBuddyGPT's SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all runs
    cursor.execute("SELECT * FROM runs ORDER BY created_at")
    runs = [dict(row) for row in cursor.fetchall()]

    traces = []
    for run in runs:
        run_id = run.get("id") or run.get("run_id")
        if not run_id:
            continue

        # Get all rounds for this run
        cursor.execute(
            "SELECT * FROM rounds WHERE run_id = ? ORDER BY round_number",
            (run_id,)
        )
        rounds = [dict(row) for row in cursor.fetchall()]

        if not rounds:
            continue

        trace = {
            "source": "hackingBuddyGPT",
            "run_id": str(run_id),
            "target": run.get("target", "unknown"),
            "success": run.get("got_root", False),
            "rounds": [],
            "trajectory": [],  # For LeWM world model
        }

        for r in rounds:
            round_data = {
                "round": r.get("round_number", 0),
                "command": r.get("command", ""),
                "output": r.get("output", "")[:2000],  # Truncate long outputs
                "got_root": r.get("got_root", False),
            }
            trace["rounds"].append(round_data)

            # Build trajectory for LeWM
            trace["trajectory"].append({
                "t": r.get("round_number", 0),
                "action": r.get("command", ""),
                "observation": r.get("output", "")[:500],
                "state_change": "root_obtained" if r.get("got_root") else "in_progress",
            })

        traces.append(trace)

    conn.close()
    return traces


def convert_to_sft_format(traces: List[Dict]) -> List[Dict[str, str]]:
    """Convert extracted traces to SFT instruction format."""
    sft_data = []

    for trace in traces:
        if not trace["rounds"]:
            continue

        # Create offensive chain instruction
        history = ""
        for r in trace["rounds"]:
            history += f"$ {r['command']}\n{r['output'][:200]}\n\n"

        instruction = {
            "instruction": (
                f"You are performing a Linux privilege escalation assessment on target "
                f"'{trace['target']}'. Based on the following command history, determine "
                f"the next best command to escalate privileges to root."
            ),
            "input": history.strip(),
            "output": trace["rounds"][-1]["command"] if trace["rounds"] else "",
        }
        sft_data.append(instruction)

        # If successful, create a full find→fix chain
        if trace["success"]:
            chain = {
                "instruction": (
                    "Analyze this successful privilege escalation chain. Identify the "
                    "vulnerability exploited, classify it using CVSS and OWASP, and "
                    "provide remediation steps."
                ),
                "input": history.strip(),
                "output": json.dumps({
                    "finding": "Privilege escalation via misconfiguration",
                    "attack_chain": [r["command"] for r in trace["rounds"]],
                    "classification": {
                        "severity": "HIGH",
                        "cvss_estimate": "7.8",
                        "owasp": "A01:2021 - Broken Access Control",
                        "cwe": "CWE-269: Improper Privilege Management",
                    },
                    "remediation": {
                        "immediate": "Review and restrict SUID binaries, sudo permissions, and cron job ownership",
                        "long_term": "Implement least-privilege access controls, regular privilege audits",
                    },
                }, indent=2),
            }
            sft_data.append(chain)

    return sft_data


def save_output(data: List[Dict], output_dir: str, prefix: str = "hackingbuddy"):
    """Save extracted data to JSONL files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save SFT data
    sft_file = output_path / f"{prefix}_sft.jsonl"
    with open(sft_file, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    print(f"Saved {len(data)} SFT examples to {sft_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract training data from hackingBuddyGPT")
    parser.add_argument("--db", required=True, help="Path to wintermute.sqlite3")
    parser.add_argument("--output", default="data/offensive/privesc_chains/", help="Output directory")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database not found at {args.db}")
        sys.exit(1)

    print(f"Extracting from {args.db}...")
    traces = extract_rounds(args.db)
    print(f"Found {len(traces)} runs")

    sft_data = convert_to_sft_format(traces)
    print(f"Generated {len(sft_data)} SFT examples")

    save_output(sft_data, args.output)
    print("Done!")


if __name__ == "__main__":
    main()

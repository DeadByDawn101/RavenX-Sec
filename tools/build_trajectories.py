#!/usr/bin/env python3
"""
build_trajectories.py — Build LeWM security world model training trajectories

Combines data from all offensive sources into system state trajectories
for training the LeWM (JEPA) security world model.

Each trajectory is a sequence of (state, action, next_state) transitions
representing how a system evolves during a security engagement.

Usage:
    python tools/build_trajectories.py --data-dir data/ --output data/world_model/
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


def build_trajectory_from_pentest(engagement: Dict) -> Dict[str, Any]:
    """Convert a pentest engagement log into a LeWM trajectory."""
    trajectory = {
        "trajectory_id": engagement.get("id", "unknown"),
        "source": engagement.get("source", "unknown"),
        "environment": engagement.get("target", "unknown"),
        "success": engagement.get("success", False),
        "observations": [],
    }

    for i, step in enumerate(engagement.get("rounds", [])):
        obs = {
            "t": i,
            "state_features": {
                "command_executed": step.get("command", ""),
                "output_summary": step.get("output", "")[:200],
                "privilege_level": "root" if step.get("got_root") else "user",
            },
            "action": categorize_action(step.get("command", "")),
        }
        trajectory["observations"].append(obs)

    return trajectory


def build_trajectory_from_scan_diff(before: Dict, after: Dict, fix_applied: str) -> Dict[str, Any]:
    """Build a remediation trajectory from before/after vulnerability scans."""
    return {
        "trajectory_id": f"remediation-{hash(fix_applied) % 10000:04d}",
        "source": "scan_diff",
        "environment": before.get("host", "unknown"),
        "success": True,
        "observations": [
            {
                "t": 0,
                "state_features": {
                    "vuln_count": before.get("vuln_count", 0),
                    "critical": before.get("critical", 0),
                    "high": before.get("high", 0),
                    "services": before.get("services", []),
                },
                "action": "scan",
            },
            {
                "t": 1,
                "state_features": {
                    "finding_identified": True,
                    "cve": before.get("primary_cve", ""),
                    "severity": before.get("severity", ""),
                },
                "action": "classify",
            },
            {
                "t": 2,
                "state_features": {
                    "fix_applied": fix_applied,
                    "service_restarted": True,
                },
                "action": "remediate",
            },
            {
                "t": 3,
                "state_features": {
                    "vuln_count": after.get("vuln_count", 0),
                    "critical": after.get("critical", 0),
                    "high": after.get("high", 0),
                    "finding_resolved": before.get("vuln_count", 0) > after.get("vuln_count", 0),
                },
                "action": "verify",
            },
        ],
    }


def categorize_action(command: str) -> str:
    """Categorize a shell command into a security action type."""
    cmd = command.lower().strip()

    recon_commands = ["nmap", "netstat", "ss", "lsof", "ps", "id", "whoami", "uname", "cat /etc"]
    enum_commands = ["find / -perm", "sudo -l", "getcap", "cat /etc/passwd", "cat /etc/shadow"]
    exploit_commands = ["exploit", "msfconsole", "python -c", "gcc", "chmod +s", "pkexec"]
    remediation_commands = ["apt update", "apt install", "yum update", "patch", "chmod", "chown"]

    for rc in recon_commands:
        if rc in cmd:
            return "reconnaissance"
    for ec in enum_commands:
        if ec in cmd:
            return "enumeration"
    for xc in exploit_commands:
        if xc in cmd:
            return "exploitation"
    for fc in remediation_commands:
        if fc in cmd:
            return "remediation"

    return "other"


def synthesize_attack_defense_trajectory() -> List[Dict[str, Any]]:
    """Synthesize complete attack → detection → remediation trajectories."""
    templates = [
        {
            "trajectory_id": "synth-ssh-privesc-001",
            "source": "synthetic",
            "environment": "linux-ubuntu",
            "success": True,
            "observations": [
                {"t": 0, "state_features": {"phase": "initial_access", "user": "lowpriv"}, "action": "scan_ports"},
                {"t": 1, "state_features": {"phase": "enumeration", "ssh_version": "7.4"}, "action": "enumerate_vulns"},
                {"t": 2, "state_features": {"phase": "vulnerability_found", "cve": "CVE-2018-15473"}, "action": "exploit"},
                {"t": 3, "state_features": {"phase": "user_enum_success", "valid_users": ["root", "admin"]}, "action": "brute_force"},
                {"t": 4, "state_features": {"phase": "access_gained", "user": "admin"}, "action": "escalate"},
                {"t": 5, "state_features": {"phase": "root_obtained", "user": "root"}, "action": "detect"},
                {"t": 6, "state_features": {"phase": "incident_detected", "alert": "priv_esc"}, "action": "contain"},
                {"t": 7, "state_features": {"phase": "contained", "sessions_killed": True}, "action": "remediate"},
                {"t": 8, "state_features": {"phase": "patched", "ssh_version": "8.9"}, "action": "verify"},
                {"t": 9, "state_features": {"phase": "clean", "vuln_count": 0}, "action": "close"},
            ],
        },
        {
            "trajectory_id": "synth-web-sqli-001",
            "source": "synthetic",
            "environment": "web-app-php",
            "success": True,
            "observations": [
                {"t": 0, "state_features": {"phase": "recon", "target": "login.php"}, "action": "spider"},
                {"t": 1, "state_features": {"phase": "input_found", "param": "username"}, "action": "test_injection"},
                {"t": 2, "state_features": {"phase": "sqli_confirmed", "type": "blind_boolean"}, "action": "extract_data"},
                {"t": 3, "state_features": {"phase": "data_exfiltrated", "tables": ["users", "sessions"]}, "action": "classify"},
                {"t": 4, "state_features": {"phase": "classified", "cvss": 9.8, "cwe": "CWE-89"}, "action": "remediate"},
                {"t": 5, "state_features": {"phase": "fix_applied", "fix": "parameterized_queries"}, "action": "verify"},
                {"t": 6, "state_features": {"phase": "verified_clean", "sqli_test": "blocked"}, "action": "report"},
            ],
        },
    ]
    return templates


def main():
    parser = argparse.ArgumentParser(description="Build LeWM security trajectories")
    parser.add_argument("--data-dir", default="data/", help="Root data directory")
    parser.add_argument("--output", default="data/world_model/", help="Output directory")
    parser.add_argument("--include-synthetic", action="store_true", default=True)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    all_trajectories = []

    # Load offensive data and convert to trajectories
    offensive_dir = Path(args.data_dir) / "offensive"
    for jsonl_file in offensive_dir.rglob("*.jsonl"):
        print(f"Processing {jsonl_file}...")
        with open(jsonl_file) as f:
            for line in f:
                engagement = json.loads(line)
                traj = build_trajectory_from_pentest(engagement)
                if traj["observations"]:
                    all_trajectories.append(traj)

    # Add synthetic trajectories
    if args.include_synthetic:
        synthetic = synthesize_attack_defense_trajectory()
        all_trajectories.extend(synthetic)
        print(f"Added {len(synthetic)} synthetic trajectories")

    # Save trajectories
    output_file = output_path / "security_trajectories.jsonl"
    with open(output_file, "w") as f:
        for traj in all_trajectories:
            f.write(json.dumps(traj) + "\n")

    print(f"\nSaved {len(all_trajectories)} trajectories to {output_file}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
synthesize_chains.py — Generate find→classify→fix training chains

Combines offensive data (from hackingBuddyGPT/PentestGPT/Shannon) with
defensive data (CVSS/OWASP/NIST mappings) to create complete vulnerability
lifecycle training examples.

Usage:
    python tools/synthesize_chains.py --data-dir data/ --output data/synthetic/
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict

# ── Vulnerability Templates ──────────────────────────────────────────────
VULN_TEMPLATES = [
    {
        "finding": "OpenSSH 7.4 on port 22",
        "cve": "CVE-2018-15473",
        "cvss": "5.3",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
        "severity": "MEDIUM",
        "cwe": "CWE-200",
        "owasp": "A07:2021 - Identification and Authentication Failures",
        "nist_csf": "PR.AC - Identity Management and Access Control",
        "description": "OpenSSH user enumeration via timing side-channel",
        "remediation_cmd": ["sudo apt update", "sudo apt install openssh-server", "sudo systemctl restart sshd"],
        "verification": "ssh -V should return OpenSSH >= 7.8",
        "compensating": ["Implement fail2ban", "Restrict SSH to known IPs", "Enable MFA"],
    },
    {
        "finding": "Apache 2.4.49 on port 80",
        "cve": "CVE-2021-41773",
        "cvss": "9.8",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "severity": "CRITICAL",
        "cwe": "CWE-22",
        "owasp": "A01:2021 - Broken Access Control",
        "nist_csf": "PR.AC - Access Control, PR.DS - Data Security",
        "description": "Path traversal allowing RCE via mod_cgi",
        "remediation_cmd": ["sudo apt update", "sudo apt install apache2", "sudo systemctl restart apache2"],
        "verification": "apache2 -v should return >= 2.4.51",
        "compensating": ["Disable mod_cgi if not needed", "WAF rules for path traversal", "File integrity monitoring"],
    },
    {
        "finding": "Log4j 2.14.1 in Java application",
        "cve": "CVE-2021-44228",
        "cvss": "10.0",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        "severity": "CRITICAL",
        "cwe": "CWE-917",
        "owasp": "A03:2021 - Injection",
        "nist_csf": "DE.CM - Security Continuous Monitoring",
        "description": "Remote code execution via JNDI lookup in log messages",
        "remediation_cmd": ["Update log4j-core to >= 2.17.1", "Set -Dlog4j2.formatMsgNoLookups=true", "Remove JndiLookup class"],
        "verification": "Check pom.xml/build.gradle for log4j-core version >= 2.17.1",
        "compensating": ["Block outbound LDAP/RMI at firewall", "Deploy RASP agent", "Monitor for JNDI patterns in logs"],
    },
    {
        "finding": "WordPress 5.7 with xmlrpc.php enabled",
        "cve": "CVE-2021-29447",
        "cvss": "7.5",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
        "severity": "HIGH",
        "cwe": "CWE-611",
        "owasp": "A05:2021 - Security Misconfiguration",
        "nist_csf": "PR.IP - Information Protection Processes",
        "description": "XXE via media upload allowing SSRF and file disclosure",
        "remediation_cmd": ["wp core update", "wp plugin update --all", "Disable xmlrpc: add deny rule in .htaccess"],
        "verification": "wp core version should return >= 5.7.2, xmlrpc.php should return 403",
        "compensating": ["WAF blocking XXE payloads", "Disable file editing in wp-config.php", "Restrict upload types"],
    },
    {
        "finding": "PostgreSQL 12.2 with default credentials",
        "cve": "CVE-2020-25695",
        "cvss": "8.8",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "severity": "HIGH",
        "cwe": "CWE-269",
        "owasp": "A07:2021 - Identification and Authentication Failures",
        "nist_csf": "PR.AC - Identity Management",
        "description": "Privilege escalation via crafted CREATE FUNCTION",
        "remediation_cmd": ["sudo apt update", "sudo apt install postgresql-12", "ALTER USER postgres PASSWORD 'newpass'"],
        "verification": "SELECT version(); should return >= 12.5",
        "compensating": ["Rotate all database credentials", "Restrict network access to DB port", "Enable pg_audit logging"],
    },
]


def generate_find_classify_fix_chains() -> List[Dict]:
    """Generate complete find→classify→fix instruction pairs."""
    chains = []

    for vuln in VULN_TEMPLATES:
        # Full analysis chain
        chains.append({
            "messages": [
                {"role": "system", "content": "You are RavenX-Sec, an autonomous security intelligence model. Analyze findings using CVSS, NIST CSF, and OWASP frameworks."},
                {"role": "user", "content": f"A vulnerability scan found {vuln['finding']}. Classify this finding, provide CVSS scoring, and give specific remediation steps."},
                {"role": "assistant", "content": json.dumps({
                    "finding": vuln["finding"],
                    "cve": vuln["cve"],
                    "classification": {
                        "cvss_score": vuln["cvss"],
                        "cvss_vector": vuln["cvss_vector"],
                        "severity": vuln["severity"],
                        "cwe": vuln["cwe"],
                        "owasp": vuln["owasp"],
                        "nist_csf": vuln["nist_csf"],
                    },
                    "description": vuln["description"],
                    "remediation": {
                        "commands": vuln["remediation_cmd"],
                        "verification": vuln["verification"],
                        "compensating_controls": vuln["compensating"],
                    },
                    "sla": "CRITICAL: 7 days | HIGH: 30 days | MEDIUM: 90 days",
                }, indent=2)},
            ]
        })

        # Triage-only chain
        chains.append({
            "messages": [
                {"role": "user", "content": f"Triage this finding: {vuln['finding']}. What is the severity and SLA?"},
                {"role": "assistant", "content": f"**{vuln['cve']}** — Severity: **{vuln['severity']}** (CVSS {vuln['cvss']})\n\nSLA: {'7-14 days' if vuln['severity'] == 'CRITICAL' else '30 days' if vuln['severity'] == 'HIGH' else '90 days'}\n\nDescription: {vuln['description']}\n\nImmediate action: {vuln['compensating'][0]}"},
            ]
        })

        # Remediation-only chain
        chains.append({
            "messages": [
                {"role": "user", "content": f"How do I fix {vuln['cve']} ({vuln['finding']})?"},
                {"role": "assistant", "content": f"**Remediation for {vuln['cve']}**\n\nCommands:\n```bash\n" + "\n".join(vuln["remediation_cmd"]) + f"\n```\n\nVerification: {vuln['verification']}\n\nCompensating controls:\n- " + "\n- ".join(vuln["compensating"])},
            ]
        })

    return chains


def main():
    parser = argparse.ArgumentParser(description="Synthesize find→classify→fix chains")
    parser.add_argument("--data-dir", default="data/", help="Root data directory")
    parser.add_argument("--output", default="data/synthetic/", help="Output directory")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    chains = generate_find_classify_fix_chains()
    print(f"Generated {len(chains)} synthetic training chains")

    output_file = output_path / "synthetic_chains.jsonl"
    with open(output_file, "w") as f:
        for chain in chains:
            f.write(json.dumps(chain) + "\n")

    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
extract_from_repos.py — Extract security training data from source repos

Works with the ACTUAL repo content (source code, prompts, templates, docs)
rather than runtime logs. Extracts:
- LLM prompt templates (the actual prompts used for security tasks)
- Privilege escalation methodology from code structure
- Web/API testing patterns
- Security agent architectures

Usage:
    python tools/extract_from_repos.py --repos-dir ~/Developer --output data/offensive/
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Dict


def extract_hackingbuddy(repo_path: str) -> List[Dict]:
    """Extract security training data from hackingBuddyGPT source code."""
    data = []
    repo = Path(repo_path)

    # 1. Extract prompt templates
    prompt_dirs = [
        repo / "src" / "hackingBuddyGPT" / "utils" / "prompt_generation" / "prompts",
        repo / "src" / "hackingBuddyGPT" / "usecases" / "privesc" / "templates",
        repo / "src" / "hackingBuddyGPT" / "usecases" / "rag" / "templates",
    ]

    for pdir in prompt_dirs:
        if not pdir.exists():
            continue
        for f in pdir.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".txt", ".md", ".jinja", ".j2", ".yaml", ".yml"):
                content = f.read_text(errors="ignore")
                if len(content) > 50:
                    # Extract string literals that look like prompts
                    prompts = re.findall(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', content, re.DOTALL)
                    for prompt in prompts:
                        if len(prompt) > 100 and any(kw in prompt.lower() for kw in
                            ["privilege", "escalat", "exploit", "vulnerab", "command", "linux", "root",
                             "shell", "attack", "target", "scan", "enumerate", "payload"]):
                            data.append({
                                "messages": [
                                    {"role": "system", "content": "You are a penetration testing assistant performing authorized security assessments."},
                                    {"role": "user", "content": f"Using the following security methodology, explain the approach:\n\n{prompt.strip()[:2000]}"},
                                    {"role": "assistant", "content": f"This methodology describes a structured approach to security testing. The key steps involve: identifying the target, enumerating the attack surface, discovering vulnerabilities, and executing controlled exploitation to validate the findings. Each step should be documented and classified using CVSS scoring."}
                                ]
                            })

    # 2. Extract privesc methodology from Python source
    privesc_files = [
        repo / "src" / "hackingBuddyGPT" / "usecases" / "privesc" / "linux.py",
        repo / "src" / "hackingBuddyGPT" / "usecases" / "privesc" / "windows.py",
        repo / "src" / "hackingBuddyGPT" / "usecases" / "privesc" / "common.py",
    ]

    for pf in privesc_files:
        if not pf.exists():
            continue
        content = pf.read_text(errors="ignore")
        # Extract command patterns from the code
        commands = re.findall(r'["\']([^"\']*(?:sudo|chmod|find|cat\s+/etc|whoami|id\s|uname|netstat|ss\s|ps\s|crontab|suid|getcap)[^"\']*)["\']', content)
        for cmd in commands:
            if len(cmd) > 5 and len(cmd) < 200:
                data.append({
                    "messages": [
                        {"role": "user", "content": f"During a Linux privilege escalation assessment, explain what this command does and what security findings it might reveal:\n\n`{cmd}`"},
                        {"role": "assistant", "content": f"The command `{cmd}` is used during privilege escalation reconnaissance. It helps identify potential misconfigurations, SUID binaries, writable files, or other weaknesses that could be exploited to escalate from a low-privileged user to root. Any findings should be classified using CVSS and mapped to CWE-269 (Improper Privilege Management)."}
                    ]
                })

    # 3. Extract web/API testing patterns
    web_files = list((repo / "src" / "hackingBuddyGPT" / "usecases" / "web_api_testing").rglob("*.py")) if (repo / "src" / "hackingBuddyGPT" / "usecases" / "web_api_testing").exists() else []
    web_files += list((repo / "src" / "hackingBuddyGPT" / "usecases" / "web").rglob("*.py")) if (repo / "src" / "hackingBuddyGPT" / "usecases" / "web").exists() else []

    for wf in web_files:
        content = wf.read_text(errors="ignore")
        # Extract class docstrings and method descriptions
        classes = re.findall(r'class\s+(\w+).*?(?:"""(.*?)""")', content, re.DOTALL)
        for cls_name, docstring in classes:
            if len(docstring) > 50:
                data.append({
                    "messages": [
                        {"role": "user", "content": f"Explain the web security testing approach used by the {cls_name} module:\n\n{docstring.strip()[:1500]}"},
                        {"role": "assistant", "content": f"The {cls_name} module implements automated web application security testing. It follows OWASP testing methodology to identify vulnerabilities in web applications and APIs. Findings should be classified under OWASP Top 10 categories and scored using CVSS."}
                    ]
                })

    # 4. Extract capability definitions (SSH, HTTP, etc.)
    cap_dir = repo / "src" / "hackingBuddyGPT" / "capabilities"
    if cap_dir.exists():
        for cf in cap_dir.glob("*.py"):
            content = cf.read_text(errors="ignore")
            classes = re.findall(r'class\s+(\w+)\(.*?\).*?(?:"""(.*?)""")', content, re.DOTALL)
            for cls_name, docstring in classes:
                if len(docstring) > 30:
                    data.append({
                        "messages": [
                            {"role": "user", "content": f"Describe the security testing capability: {cls_name}"},
                            {"role": "assistant", "content": f"{docstring.strip()[:1500]}\n\nThis capability is part of an automated penetration testing framework. It should be used only during authorized security assessments."}
                        ]
                    })

    return data


def extract_pentestgpt(repo_path: str) -> List[Dict]:
    """Extract security training data from PentestGPT source code."""
    data = []
    repo = Path(repo_path)

    # Find all Python files with security-relevant content
    for pyfile in repo.rglob("*.py"):
        if ".git" in str(pyfile) or "node_modules" in str(pyfile):
            continue
        try:
            content = pyfile.read_text(errors="ignore")
        except:
            continue

        # Extract prompt strings
        prompts = re.findall(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', content, re.DOTALL)
        for prompt in prompts:
            if len(prompt) > 200 and any(kw in prompt.lower() for kw in
                ["pentest", "vulnerab", "exploit", "attack", "target", "reconnaissance",
                 "enumerat", "privilege", "injection", "xss", "csrf", "ssrf", "rce"]):
                data.append({
                    "messages": [
                        {"role": "system", "content": "You are RavenX-Sec, an autonomous security intelligence model."},
                        {"role": "user", "content": f"Analyze this penetration testing methodology and explain each step:\n\n{prompt.strip()[:2000]}"},
                        {"role": "assistant", "content": "This methodology follows a structured penetration testing approach. The key phases are: reconnaissance and information gathering, vulnerability scanning and analysis, exploitation and validation, post-exploitation assessment, and reporting with remediation recommendations. Each discovered vulnerability should be classified using CVSS scoring, mapped to OWASP Top 10 and CWE identifiers, and accompanied by specific remediation steps."}
                    ]
                })

    # Extract from markdown docs
    for mdfile in repo.rglob("*.md"):
        if ".git" in str(mdfile):
            continue
        try:
            content = mdfile.read_text(errors="ignore")
        except:
            continue

        if len(content) > 500 and any(kw in content.lower() for kw in
            ["pentest", "vulnerab", "security", "exploit", "ctf", "challenge"]):
            # Create training pair from doc content
            data.append({
                "messages": [
                    {"role": "user", "content": f"Summarize this security documentation and identify key techniques:\n\n{content[:2000]}"},
                    {"role": "assistant", "content": "This documentation covers penetration testing techniques and methodologies. Key areas include vulnerability identification, exploitation techniques, and security assessment procedures. All findings should be documented with CVSS scores, CWE mappings, and actionable remediation guidance."}
                ]
            })

    return data


def extract_shannon(repo_path: str) -> List[Dict]:
    """Extract security training data from Shannon white-box pentester."""
    data = []
    repo = Path(repo_path)

    # Shannon is a TypeScript project - extract from TS/JS files
    for tsfile in repo.rglob("*.ts"):
        if ".git" in str(tsfile) or "node_modules" in str(tsfile) or "dist" in str(tsfile):
            continue
        try:
            content = tsfile.read_text(errors="ignore")
        except:
            continue

        # Extract string templates and prompts
        templates = re.findall(r'`(.*?)`', content, re.DOTALL)
        for tpl in templates:
            if len(tpl) > 200 and any(kw in tpl.lower() for kw in
                ["vulnerab", "exploit", "security", "attack", "injection", "xss",
                 "code review", "source code", "decompil", "reverse", "malware"]):
                data.append({
                    "messages": [
                        {"role": "system", "content": "You are RavenX-Sec performing white-box security analysis."},
                        {"role": "user", "content": f"Analyze this security assessment approach:\n\n{tpl.strip()[:2000]}"},
                        {"role": "assistant", "content": "This white-box security analysis approach involves examining source code to identify vulnerabilities before they can be exploited. Key techniques include static analysis, code path tracing, input validation checking, and authentication flow review. Findings should be mapped to CWE identifiers and OWASP categories with specific code-level remediation."}
                    ]
                })

    return data


def extract_ghidra_patterns(repo_path: str) -> List[Dict]:
    """Extract RE analysis patterns from Ghidra scripts."""
    data = []
    repo = Path(repo_path)

    # Look for Ghidra analysis scripts
    script_dirs = [
        repo / "Ghidra" / "Features" / "Base" / "ghidra_scripts",
        repo / "Ghidra" / "Features" / "Python" / "ghidra_scripts",
    ]

    for sdir in script_dirs:
        if not sdir.exists():
            continue
        for script in sdir.rglob("*.java"):
            try:
                content = script.read_text(errors="ignore")
            except:
                continue

            if any(kw in content.lower() for kw in
                ["vulnerab", "overflow", "inject", "exploit", "malware",
                 "shellcode", "rop", "gadget", "crypto", "password"]):
                # Extract the class description
                desc_match = re.search(r'/\*\*(.*?)\*/', content, re.DOTALL)
                desc = desc_match.group(1).strip() if desc_match else script.stem

                data.append({
                    "messages": [
                        {"role": "user", "content": f"Explain what this Ghidra RE analysis script does: {script.stem}\n\nDescription: {desc[:500]}"},
                        {"role": "assistant", "content": f"The Ghidra script '{script.stem}' performs binary analysis to identify potential security issues in compiled software. Reverse engineering analysis like this is critical for discovering vulnerabilities in closed-source software, malware analysis, and firmware security review. Findings from RE analysis should be documented with CWE identifiers and CVSS scores."}
                    ]
                })

    return data


def generate_synthetic_security_data() -> List[Dict]:
    """Generate high-quality synthetic security training data."""
    scenarios = [
        {
            "finding": "OpenSSH 7.4 on port 22",
            "cve": "CVE-2018-15473", "cvss": "5.3",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
            "severity": "MEDIUM", "cwe": "CWE-200",
            "owasp": "A07:2021 - Identification and Authentication Failures",
            "description": "OpenSSH user enumeration via timing side-channel",
            "remediation": "Upgrade OpenSSH to 7.8+: sudo apt update && sudo apt install openssh-server",
        },
        {
            "finding": "Apache 2.4.49 with mod_cgi enabled",
            "cve": "CVE-2021-41773", "cvss": "9.8",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-22",
            "owasp": "A01:2021 - Broken Access Control",
            "description": "Path traversal allowing RCE via mod_cgi",
            "remediation": "Upgrade Apache to 2.4.51+: sudo apt update && sudo apt install apache2",
        },
        {
            "finding": "Log4j 2.14.1 in Java application",
            "cve": "CVE-2021-44228", "cvss": "10.0",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-917",
            "owasp": "A03:2021 - Injection",
            "description": "Remote code execution via JNDI lookup in log messages",
            "remediation": "Update log4j-core to 2.17.1+ or set -Dlog4j2.formatMsgNoLookups=true",
        },
        {
            "finding": "PostgreSQL 12.2 with default credentials",
            "cve": "CVE-2020-25695", "cvss": "8.8",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
            "severity": "HIGH", "cwe": "CWE-269",
            "owasp": "A07:2021 - Identification and Authentication Failures",
            "description": "Privilege escalation via crafted CREATE FUNCTION",
            "remediation": "Upgrade PostgreSQL to 12.5+ and rotate all credentials",
        },
        {
            "finding": "Kubernetes API server exposed on port 6443 without authentication",
            "cve": "CVE-2018-1002105", "cvss": "9.8",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-269",
            "owasp": "A01:2021 - Broken Access Control",
            "description": "Unauthenticated API server allows full cluster takeover",
            "remediation": "Enable RBAC, restrict API server network access, enforce TLS client certificates",
        },
        {
            "finding": "Redis 6.0 exposed on port 6379 without AUTH",
            "cve": "CVE-2022-0543", "cvss": "10.0",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-862",
            "owasp": "A01:2021 - Broken Access Control",
            "description": "Unauthenticated Redis allows RCE via Lua sandbox escape",
            "remediation": "Set requirepass in redis.conf, bind to localhost, enable TLS",
        },
        {
            "finding": "Nginx misconfigured with alias traversal",
            "cve": "N/A - Misconfiguration", "cvss": "7.5",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
            "severity": "HIGH", "cwe": "CWE-22",
            "owasp": "A05:2021 - Security Misconfiguration",
            "description": "Nginx alias directive without trailing slash allows path traversal",
            "remediation": "Add trailing slash to alias directives: location /static/ { alias /var/www/static/; }",
        },
        {
            "finding": "Jenkins instance with Script Console enabled",
            "cve": "N/A - Misconfiguration", "cvss": "9.8",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-94",
            "owasp": "A03:2021 - Injection",
            "description": "Groovy Script Console allows arbitrary code execution on Jenkins master",
            "remediation": "Disable Script Console for non-admin users, enable CSRF protection, restrict network access",
        },
        {
            "finding": "MySQL 5.7 with FILE privilege granted to application user",
            "cve": "N/A - Misconfiguration", "cvss": "7.5",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
            "severity": "HIGH", "cwe": "CWE-732",
            "owasp": "A01:2021 - Broken Access Control",
            "description": "FILE privilege allows reading arbitrary files via LOAD_FILE() and writing via INTO OUTFILE",
            "remediation": "REVOKE FILE ON *.* FROM 'appuser'@'%'; Use least-privilege access model",
        },
        {
            "finding": "Docker daemon exposed on TCP 2375 without TLS",
            "cve": "N/A - Misconfiguration", "cvss": "9.8",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "severity": "CRITICAL", "cwe": "CWE-284",
            "owasp": "A01:2021 - Broken Access Control",
            "description": "Unauthenticated Docker API allows container escape and host takeover",
            "remediation": "Disable TCP socket, use Unix socket only, or enable TLS mutual auth on port 2376",
        },
    ]

    data = []
    for s in scenarios:
        # Full RATH analysis
        data.append({
            "messages": [
                {"role": "system", "content": "You are RavenX-Sec, an autonomous security intelligence model. Follow the RATH protocol for every finding."},
                {"role": "user", "content": f"Analyze this finding: {s['finding']}. Classify using CVSS, NIST CSF, and OWASP. Provide specific remediation."},
                {"role": "assistant", "content": f"""**RATH STEP 1: IDENTIFY**
- Finding: {s['finding']}
- CVE: {s['cve']}
- Description: {s['description']}

**RATH STEP 2: ASSESS**
- CVSS Score: {s['cvss']}
- CVSS Vector: {s['cvss_vector']}
- Severity: {s['severity']}
- CWE: {s['cwe']}
- OWASP: {s['owasp']}

**RATH STEP 3: PRIORITIZE**
- SLA: {'7 days (Critical)' if s['severity'] == 'CRITICAL' else '30 days (High)' if s['severity'] == 'HIGH' else '90 days (Medium)'}
- NIST CSF: Detect → Respond → Recover

**RATH STEP 4: REMEDIATE**
- Action: {s['remediation']}
- Compensating controls: Restrict network access, enable monitoring, implement WAF rules

**RATH STEP 5: VERIFY**
- Run rescan to confirm finding is resolved
- Validate no regressions introduced
- Update POA&M tracker"""}
            ]
        })

        # Quick triage format
        data.append({
            "messages": [
                {"role": "user", "content": f"Quick triage: {s['finding']}"},
                {"role": "assistant", "content": f"**{s['cve']}** — {s['severity']} (CVSS {s['cvss']})\nSLA: {'7 days' if s['severity'] == 'CRITICAL' else '30 days' if s['severity'] == 'HIGH' else '90 days'}\n{s['description']}\nFix: {s['remediation']}"}
            ]
        })

        # Remediation only
        data.append({
            "messages": [
                {"role": "user", "content": f"How do I fix {s['cve'] if s['cve'] != 'N/A - Misconfiguration' else s['finding']}?"},
                {"role": "assistant", "content": f"**Remediation:**\n{s['remediation']}\n\n**Verification:** Rescan after patching to confirm the vulnerability is resolved.\n\n**Compensating controls:** If immediate patching is not possible, restrict network access to the affected service and enable anomaly detection."}
            ]
        })

    return data


def main():
    parser = argparse.ArgumentParser(description="Extract security training data from source repos")
    parser.add_argument("--repos-dir", required=True, help="Directory containing cloned repos")
    parser.add_argument("--output", default="data/offensive/", help="Output directory")
    args = parser.parse_args()

    repos_dir = Path(args.repos_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_data = []

    # Extract from each repo
    print("=" * 60)
    print("Extracting security training data from source repos")
    print("=" * 60)

    hb_path = repos_dir / "hackingBuddyGPT"
    if hb_path.exists():
        print(f"\n[1/4] hackingBuddyGPT...")
        hb_data = extract_hackingbuddy(str(hb_path))
        print(f"  Extracted {len(hb_data)} examples")
        all_data.extend(hb_data)

    pg_path = repos_dir / "PentestGPT"
    if pg_path.exists():
        print(f"\n[2/4] PentestGPT...")
        pg_data = extract_pentestgpt(str(pg_path))
        print(f"  Extracted {len(pg_data)} examples")
        all_data.extend(pg_data)

    sh_path = repos_dir / "shannon"
    if sh_path.exists():
        print(f"\n[3/4] Shannon...")
        sh_data = extract_shannon(str(sh_path))
        print(f"  Extracted {len(sh_data)} examples")
        all_data.extend(sh_data)

    gh_path = repos_dir / "ghidra"
    if gh_path.exists():
        print(f"\n[4/4] Ghidra...")
        gh_data = extract_ghidra_patterns(str(gh_path))
        print(f"  Extracted {len(gh_data)} examples")
        all_data.extend(gh_data)

    # Add synthetic data
    print(f"\n[+] Generating synthetic RATH training data...")
    synthetic = generate_synthetic_security_data()
    print(f"  Generated {len(synthetic)} synthetic examples")
    all_data.extend(synthetic)

    # Save
    output_file = output_dir / "extracted_security_data.jsonl"
    with open(output_file, "w") as f:
        for item in all_data:
            f.write(json.dumps(item) + "\n")

    print(f"\n{'=' * 60}")
    print(f"✅ Total: {len(all_data)} training examples → {output_file}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

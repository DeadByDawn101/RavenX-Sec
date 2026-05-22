# RavenX-Sec — Autonomous Security Intelligence Model

<p align="center">
<strong>Find → Classify → Fix → Verify → Report</strong><br>
<em>The first security model that completes the full vulnerability lifecycle.</em>
</p>

**Built by @DeadByDawn101 (RavenX LLC)**  
**Status:** Training data curation phase  
**License:** MIT — Security knowledge should be open.

---

## What This Is

RavenX-Sec is a fine-tuned LLM specialized in offensive security, vulnerability discovery, and **real-time remediation**. Unlike existing security LLMs that only find vulnerabilities, RavenX-Sec completes the full lifecycle.

Trained on the combined intelligence of five security toolchains, a world model for attack dynamics, and industry-standard compliance frameworks — this model understands both the attacker's perspective and the defender's playbook.

## Why This Exists

Every pentest report ends with a list of findings. Those findings sit in a Jira queue. A security TPM tracks them against SLAs. Developers scramble to remediate. Weeks pass. Some findings expire unpatched.

**What if the model that found the vulnerability also generated the fix?**

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      RavenX-Sec Model                             │
│                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │  Offensive  │  │ Analytical │  │ Defensive  │  │ Reporting  │  │
│  │            │  │            │  │            │  │            │  │
│  │ Priv-esc   │  │ CVSS score │  │ Code fixes │  │ POA&M      │  │
│  │ Web pentest│  │ OWASP map  │  │ Config     │  │ Compliance │  │
│  │ API testing│  │ NIST CSF   │  │ hardening  │  │ SLA track  │  │
│  │ RE/binary  │  │ Kill chain │  │ Patch gen  │  │ Executive  │  │
│  │ Exploit    │  │ ATT&CK     │  │ Validation │  │ summary    │  │
│  │ chains     │  │ mapping    │  │ Regression │  │            │  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              LeWM Security World Model                        │ │
│  │  Encodes system state → Predicts attack dynamics →            │ │
│  │  Models remediation impact → Detects anomalies                │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## The Model Stack

| Layer | Component | Purpose |
|-------|-----------|---------|
| **World Model** | LeWM (JEPA) | Learns security system dynamics — predicts attack progression, models remediation impact, detects anomalous states |
| **Compression** | TriAttention | 10.7x KV cache compression for efficient long-context security reasoning |
| **Training** | MOOSE-Star | Tractable training for complex multi-step security reasoning chains |
| **Fine-tuning** | Jackrong Pipeline | QLoRA (4-bit) via Unsloth on security-specific instruction data |
| **Base Model** | Qwen3-8B | Foundation language understanding and code generation |
| **Evaluation** | GLM-5.1 | Judge model for quality validation of generated findings and fixes |

## The LeWM Security World Model

Traditional security models classify vulnerabilities from static text. RavenX-Sec understands **dynamics** — how systems evolve under attack and remediation.

Based on [LeWorldModel](https://arxiv.org/abs/2603.19312) (Maes et al., 2026), a Joint Embedding Predictive Architecture that learns world models from raw observations:

**Security Applications:**

| Capability | How It Works |
|------------|-------------|
| **Attack chain prediction** | Encode current system state (ports, services, configs) → predict next state if vulnerability is exploited |
| **Remediation impact modeling** | Apply "fix action" to state → predict new state → verify vulnerability resolved with no regressions |
| **Anomaly detection** | Learn "normal" system dynamics → flag deviations that indicate compromise, lateral movement, or exfiltration |
| **Offline learning** | Train on historical pentest data, vulnerability scans, and incident logs without explicit reward signals |

**Trajectory Training Format:**

```json
{
  "trajectory": [
    {"state": "port 22 open, SSH 7.4", "action": "scan", "t": 0},
    {"state": "CVE-2018-15473 found", "action": "enumerate", "t": 1},
    {"state": "valid user confirmed", "action": "exploit", "t": 2},
    {"state": "shell obtained", "action": "remediate", "t": 3},
    {"state": "SSH 8.9, hardened", "action": "verify", "t": 4},
    {"state": "clean scan", "action": "done", "t": 5}
  ]
}
```

The world model learns: given any (state, action) pair → predict the next state. This enables **planning** — simulating attack chains and remediation outcomes before they happen.

## Training Data Sources

### Offensive Intelligence (How to Find)

| Source Repo | What We Extract |
|-------------|----------------|
| [hackingBuddyGPT](https://github.com/DeadByDawn101/hackingBuddyGPT) | Linux priv-esc sequences, web pentest patterns, API testing, agent round logs |
| [PentestGPT](https://github.com/DeadByDawn101/PentestGPT) | CTF solutions, autonomous pentest sessions, XBOW benchmark (86.5%) |
| [Shannon](https://github.com/DeadByDawn101/shannon) | White-box vuln discovery, exploit PoCs, source code → vulnerability mappings |
| [Ghidra](https://github.com/DeadByDawn101/ghidra) | RE methodology, binary analysis heuristics, malware indicators |

### Defensive Intelligence (How to Fix)

| Source | What We Extract |
|--------|----------------|
| NIST NVD | CVE descriptions, CVSS vectors, CWE mappings (~250K CVEs) |
| OWASP Top 10 | Prevention checklists, remediation code examples |
| CIS Benchmarks | Hardening configs for Linux, Windows, cloud, containers |
| MITRE ATT&CK | Technique → mitigation mappings, detection rules |
| GitHub fix commits | Security fix diffs → remediation pattern extraction |

### Framework Intelligence (How to Classify & Report)

CVSS v3.1/v4.0 • NIST CSF 2.0 • ISO 27001 • PCI DSS v4.0 • HIPAA • SOX

### World Model Intelligence (How Systems Evolve)

| Source | What We Extract |
|--------|----------------|
| Pentest engagement logs | Attack state trajectories with timestamps |
| Vulnerability scan histories | System state evolution over time |
| Incident response timelines | Compromise → detection → containment → recovery chains |
| Remediation tracking (POA&M) | Fix applied → verification → closure trajectories |

## Training Pipeline

### Phase 1: Data Curation & Synthesis

Extract interaction traces from source repos → normalize to instruction format → synthesize find→classify→fix chains → quality filter → ~500K examples

### Phase 2: LeWM World Model Pre-training

Train the security world model on system state trajectories:
- 15M parameters, single GPU (RTX 3090)
- Two-loss training: prediction loss + SIGReg anti-collapse
- Input: system state observations + security actions
- Output: predicted next system state in latent space

### Phase 3: Supervised Fine-Tuning (SFT)

```python
{
    "base_model": "Qwen3-8B",
    "method": "QLoRA (4-bit)",
    "framework": "Unsloth + HuggingFace TRL",
    "rank": 64,
    "alpha": 128,
    "learning_rate": 2e-4,
    "max_seq_len": 8192,
    "hardware": "RTX 3090 (24 GB VRAM + 64 GB UVM)"
}
```

### Phase 4: MOOSE-Star Enhancement

Apply MOOSE-Star training methodology for complex multi-step security reasoning.

### Phase 5: Reinforcement Learning (Future)

GRPO for rewarding successful find→fix cycles and penalizing false positives.

## Deployment

### On Star Platinum Cluster

- **Mac nodes** (312 GB): Host full model via oMLX
- **Linux rig** (RTX 3090): Accelerate compute-heavy layers
- **TurboQuant bridge**: Compressed KV for cross-backend transfer

### As an Agent

- OpenClaw / Hermes: Security-specialized agent persona
- Claude Code: MCP tool server for real-time analysis
- CI/CD: Pre-commit security review hook
- Jira / ServiceNow: Automatic finding creation with remediation

## Repo Structure

```
RavenX-Sec/
├── data/
│   ├── offensive/           # From hackingBuddyGPT, PentestGPT, Shannon
│   ├── defensive/           # CVE fixes, CIS benchmarks, hardening
│   ├── analytical/          # CVSS, OWASP, NIST, ATT&CK mappings
│   ├── synthetic/           # Synthesized find→classify→fix chains
│   └── world_model/         # System state trajectories for LeWM
├── training/
│   ├── sft/                 # Supervised fine-tuning (Jackrong method)
│   ├── lewm/                # LeWM world model training
│   ├── moose/               # MOOSE-Star enhancement
│   ├── rl/                  # Future GRPO reinforcement learning
│   └── eval/                # Evaluation benchmarks
├── models/
│   ├── configs/             # Model and LoRA configurations
│   └── checkpoints/         # Training checkpoints
├── deploy/
│   ├── star-platinum/       # Cluster deployment configs
│   ├── agent/               # Agent persona definitions
│   └── api/                 # OpenAI-compatible API server
├── tools/
│   ├── extract_hackingbuddy.py
│   ├── extract_pentestgpt.py
│   ├── extract_shannon.py
│   ├── extract_ghidra.py
│   ├── synthesize_chains.py
│   ├── build_trajectories.py  # Build LeWM training trajectories
│   └── quality_filter.py
└── docs/
    ├── ARCHITECTURE.md
    ├── TRAINING.md
    ├── DATA_PIPELINE.md
    └── LEWM_SECURITY.md       # LeWM world model for security
```

## Source Repos

| Repo | Purpose | License |
|------|---------|---------|
| [DeadByDawn101/hackingBuddyGPT](https://github.com/DeadByDawn101/hackingBuddyGPT) | Offensive security agent framework | MIT |
| [DeadByDawn101/PentestGPT](https://github.com/DeadByDawn101/PentestGPT) | Autonomous penetration testing (USENIX Security 2024) | MIT |
| [DeadByDawn101/shannon](https://github.com/DeadByDawn101/shannon) | White-box AI pentester (96.15% XBOW) | AGPL-3.0 |
| [DeadByDawn101/ghidra](https://github.com/DeadByDawn101/ghidra) | Reverse engineering framework | Apache-2.0 |
| [DeadByDawn101/OpenMythos](https://github.com/DeadByDawn101/OpenMythos) | RDT architecture reference | MIT |
| [Jackrong LLM fine-tuning guide](https://github.com/DeadByDawn101/Jackrong-llm-finetuning-guide) | SFT pipeline | — |
| [MOOSE-Star](https://github.com/ZonglinY/MOOSE-Star) | ICML 2026 training methodology | — |
| [LeWorldModel](https://arxiv.org/abs/2603.19312) | JEPA world model from pixels | — |

## References

- [LeWorldModel (arXiv:2603.19312)](https://arxiv.org/abs/2603.19312) — Stable end-to-end JEPA from pixels
- [TriAttention (arXiv:2604.04921)](https://arxiv.org/abs/2604.04921) — 10.7x KV compression
- [MOOSE-Star (ICML 2026)](https://github.com/ZonglinY/MOOSE-Star) — Tractable training for scientific discovery
- [PentestGPT (USENIX Security 2024)](https://www.usenix.org/conference/usenixsecurity24/presentation/deng)
- [hackingBuddyGPT (FSE'23)](https://dl.acm.org/doi/10.1145/3611643.3613083)
- [CVSS v4.0](https://www.first.org/cvss/v4-0/)
- [NIST CSF 2.0](https://www.nist.gov/cyberframework)
- [MITRE ATT&CK](https://attack.mitre.org/)

---

*"We don't give up. We do what others don't and build what isn't possible."*  
*— RavenX LLC*

# Data Pipeline — RavenX-Sec

## Pipeline Overview

```
Source Repos          HuggingFace Datasets     Synthetic Generation
     │                       │                        │
     ▼                       ▼                        ▼
  extract_*.py          load_dataset()         synthesize_chains.py
     │                       │                        │
     └───────────┬───────────┘────────────────────────┘
                 ▼
          quality_filter.py
                 │
                 ▼
           train.jsonl + valid.jsonl
                 │
                 ▼
            train_mlx.py (MLX LoRA)
```

## Data Sources

### Tier 1: Security-Specific (Highest Priority)

| Source | Tool | Expected Volume |
|--------|------|----------------|
| hackingBuddyGPT SQLite logs | `extract_hackingbuddy.py` | ~50K traces |
| PentestGPT benchmark results | `extract_pentestgpt.py` | ~100K steps |
| Shannon vuln reports | `extract_shannon.py` | ~50K pairs |
| Ghidra RE patterns | `extract_ghidra.py` | ~20K patterns |
| Synthetic CVE chains | `synthesize_chains.py` | ~1K templates |

### Tier 2: HuggingFace Datasets

| Dataset | Type | Volume |
|---------|------|--------|
| WithinUsAI/claude_mythos_distilled_25k | Distilled reasoning | 25K |
| WithinUsAI/AgentAngel_100k | Agentic coding | 500K (cap at 50K) |
| ByteDance/PatchEval | CVE patches | 1K gold-standard |
| JetBrains-Research/commit-chronicle | Git security commits | Millions |
| bigcode/commitpack | Code changes | Billions of tokens |
| bigcode/vuln-eval | Vulnerability eval | TBD |
| Fraser/cwe-benchmark | CWE code examples | TBD |
| isek/cybersecurity-instructions | Security instructions | TBD |

### Tier 3: Public Security Data

| Source | What | Format |
|--------|------|--------|
| NIST NVD | CVE descriptions + CVSS | JSON API |
| MITRE ATT&CK | Technique → mitigation | STIX/JSON |
| CIS Benchmarks | Hardening configs | PDF/text |

## Data Format

All training data is normalized to the chat messages format:

```json
{
  "messages": [
    {"role": "system", "content": "You are RavenX-Sec..."},
    {"role": "user", "content": "Analyze this finding..."},
    {"role": "assistant", "content": "**Step 1: Environment Analysis**..."}
  ]
}
```

## Weighting Strategy

```python
combined = (
    security_examples * 5 +     # 5x weight — dominant signal
    agent_examples[:50000] +     # Capped — prevents dilution
    local_data * 5 +             # 5x weight — our own extraction
    other_examples               # 1x weight — general reasoning
)
```

**Critical rule: Security data must be >50% of final training mix.**

## Quality Filtering

```bash
python tools/quality_filter.py --input data/train.jsonl --output data/train_filtered.jsonl
```

Filters applied:
1. Format validation (proper role/content message pairs)
2. Length filter (min 50 char assistant response)
3. Deduplication (MD5 hash of content)

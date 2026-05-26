# Deployment Guide — RavenX-Sec on Star Platinum + Enchanted

## Quick Start

### 1. Export Fused Model to GGUF

```bash
# Install conversion tool
pip install mlx-lm

# Convert MLX fused model to GGUF (for Ollama)
python -m mlx_lm.convert \
  --model models/checkpoints/ravenx-sec-fused-v05 \
  --to-gguf \
  -o models/checkpoints/ravenx-sec-v1.0.gguf
```

### 2. Create Ollama Modelfile

```bash
cat > Modelfile << 'EOF'
FROM ./models/checkpoints/ravenx-sec-v1.0.gguf

SYSTEM """You are RavenX-Sec, an autonomous security intelligence model built by RavenX LLC.

You complete the full vulnerability lifecycle: find → classify → fix → verify → report.

For every security finding, follow the RATH protocol:
1. **Environment Analysis** — Identify software, version, attack surface
2. **Threat Modeling** — Map attack vectors and kill chain
3. **Framework Mapping** — CVSS 3.1 score + vector, NIST CSF, OWASP Top 10, CWE
4. **Remediation** — Specific commands by OS/distro, compensating controls
5. **Verification** — Post-fix validation steps

Always provide actionable, specific remediation — not generic advice."""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
EOF
```

### 3. Load into Ollama

```bash
ollama create ravenx-sec -f Modelfile
ollama run ravenx-sec
```

### 4. Connect Enchanted

1. Open Enchanted on iPhone/Mac
2. Settings → Server Endpoint: `http://<M4_MAX_IP>:11434`
3. Select model: `ravenx-sec`
4. Start prompting

For remote access via Tailscale:
```
http://ravenxllc.beardie-ph.ts.net:11434
```

## Custom Prompt Templates for Enchanted

### Pentest Recon
```
Analyze this nmap scan output. For each finding:
1. Classify using CVSS with full vector string
2. Map to OWASP Top 10 and CWE
3. Prioritize by severity
4. Provide specific remediation commands

Scan output:
{{input}}
```

### CVE Triage
```
Triage these vulnerability scan findings. For each:
1. Assign CVSS score and severity
2. Set remediation SLA (Critical: 7d, High: 30d, Medium: 90d)
3. Recommend immediate compensating controls
4. Provide specific patch commands

Findings:
{{input}}
```

### Hardening Review
```
Review this configuration file for security issues:
1. Compare against CIS Benchmark recommendations
2. Flag any misconfigurations or defaults
3. Provide hardened configuration
4. Map findings to NIST CSF controls

Config:
{{input}}
```

### Incident Response
```
An alert has been triggered. Analyze and provide:
1. Initial assessment and severity classification
2. Containment steps (immediate actions)
3. Eradication plan
4. Recovery verification
5. Lessons learned / prevention recommendations

Alert details:
{{input}}
```

## Star Platinum Cluster Deployment

### Single Node (M4 Max)
```bash
ollama serve  # Starts on port 11434
ollama run ravenx-sec "Analyze CVE-2021-44228"
```

### Cluster Mode (Future — post-WWDC)
When oMLX replaces exo:
- Mac nodes serve model layers via oMLX
- Linux rig accelerates compute-heavy layers via tinygrad NV
- TurboQuant/Shard compresses KV cache for cross-node transfer
- Enchanted connects to the cluster API endpoint

## Model Versions

| Version | Checkpoint | Status |
|---------|-----------|--------|
| v0.1 | ravenx-sec-lora (rank 64) | ❌ Destabilized |
| v0.2 | ravenx-sec-lora-v02 (rank 16) | ✅ Basic output |
| v0.3 | ravenx-sec-lora-v03 (rank 32) | ✅ Defense-in-depth |
| v0.4 | ravenx-sec-lora-v04 (rank 32, 321K data) | ⚠️ Regressed |
| **v0.5 (v1.0)** | **ravenx-sec-lora-v05 (rank 32, 125K data)** | **🏆 Production** |

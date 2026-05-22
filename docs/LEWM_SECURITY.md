# LeWM for Security — World Model for Attack Dynamics

## Overview

Based on [LeWorldModel](https://arxiv.org/abs/2603.19312) (Maes et al., 2026), this module adapts the Joint Embedding Predictive Architecture (JEPA) for security system dynamics.

## Key Insight

LeWM learns to predict the future state of a system by encoding observations into a compact latent space and modeling dynamics through next-embedding prediction. In security context:

- **Observations** = system state (open ports, running services, configurations, user sessions)
- **Actions** = security events (scans, exploits, patches, config changes)
- **Predictions** = next system state after action

## Why JEPA for Security

| Traditional Security ML | LeWM Security World Model |
|------------------------|--------------------------|
| Classifies vulnerabilities from static features | Predicts how systems evolve under attack |
| Binary: vulnerable or not | Continuous: models the full attack trajectory |
| Requires labeled data | Learns from unlabeled system trajectories |
| No concept of time | Temporal dynamics are the core |
| Can't simulate "what if" | Plans remediation by simulating outcomes |

## Architecture

```
System State (t)     Action (t)
     │                    │
     ▼                    │
  Encoder                 │
     │                    │
     ▼                    ▼
  z_t ──────────► Predictor ──────► ẑ_{t+1}
                                       │
                                       ▼
                               Predicted State (t+1)
```

Training uses only two losses:
1. **Prediction loss**: MSE between predicted and actual next state embedding
2. **SIGReg**: Anti-collapse regularizer enforcing Gaussian-distributed latent embeddings

No exponential moving averages. No stop-gradient. No pre-trained encoders. Stable end-to-end training.

## Security State Encoding

### Input Features (per system snapshot)

```python
state_features = {
    "network": {
        "open_ports": [22, 80, 443, 3306],
        "services": {"22": "OpenSSH_7.4", "80": "Apache_2.4.6"},
        "firewall_rules": ["ALLOW 22/tcp", "ALLOW 80/tcp"],
    },
    "system": {
        "os": "Ubuntu_20.04",
        "kernel": "5.4.0-42-generic",
        "suid_binaries": ["/usr/bin/pkexec", "/usr/bin/sudo"],
        "cron_jobs": ["*/5 * * * * /opt/backup.sh"],
    },
    "users": {
        "active_sessions": ["lowpriv@pts/0"],
        "recent_auth_failures": 15,
        "privilege_level": "user",
    },
    "vulnerabilities": {
        "cve_count": 3,
        "critical": 1,
        "high": 2,
        "patch_age_days": 180,
    }
}
```

### Action Space

```python
security_actions = [
    "scan_ports",
    "scan_vulnerabilities",
    "enumerate_users",
    "exploit_cve",
    "escalate_privileges",
    "lateral_move",
    "exfiltrate_data",
    "apply_patch",
    "harden_config",
    "add_firewall_rule",
    "rotate_credentials",
    "restart_service",
    "verify_remediation",
]
```

## Training Data

### Trajectory Format

```json
{
  "trajectory_id": "pentest-2026-001",
  "environment": "linux-ubuntu-20.04",
  "observations": [
    {"t": 0, "state": "<encoded_state>", "action": "scan_ports"},
    {"t": 1, "state": "<encoded_state>", "action": "scan_vulnerabilities"},
    {"t": 2, "state": "<encoded_state>", "action": "exploit_cve"},
    {"t": 3, "state": "<encoded_state>", "action": "escalate_privileges"},
    {"t": 4, "state": "<encoded_state>", "action": "apply_patch"},
    {"t": 5, "state": "<encoded_state>", "action": "verify_remediation"}
  ]
}
```

### Data Sources for Trajectories

1. **hackingBuddyGPT logs**: Each round is a (state, action, result) triple
2. **PentestGPT sessions**: Full pentest engagement logs with timestamps
3. **Shannon reports**: Source analysis → exploitation → report chains
4. **Vulnerability scan histories**: Nessus/Qualys scan diffs over time
5. **POA&M tracking**: Remediation state changes with dates

## Training Configuration

```python
lewm_config = {
    "encoder": {
        "type": "ViT-tiny",
        "params": "5M",
        "patch_size": 14,
        "layers": 12,
        "heads": 3,
        "hidden_dim": 192,
    },
    "predictor": {
        "type": "Transformer",
        "params": "10M",
        "layers": 6,
        "heads": 16,
        "dropout": 0.1,
        "action_conditioning": "AdaLN",
    },
    "training": {
        "total_params": "15M",
        "gpu": "RTX 3090 (single GPU)",
        "loss": "MSE + λ * SIGReg",
        "lambda": 0.1,
        "sigreg_projections": 1024,
        "optimizer": "AdamW",
        "batch_size": 64,
        "learning_rate": 1e-4,
    }
}
```

## Applications

### 1. Attack Chain Simulation

```python
# Given current state, simulate what happens if CVE is exploited
current_state = encode(system_snapshot)
exploit_action = encode_action("exploit_cve_2021_4034")
predicted_state = predict(current_state, exploit_action)
# predicted_state encodes: root shell obtained, system compromised
```

### 2. Remediation Impact Verification

```python
# Simulate applying a patch and verify the vulnerability is resolved
vulnerable_state = encode(system_snapshot)
patch_action = encode_action("apply_patch_polkit")
patched_state = predict(vulnerable_state, patch_action)
# Verify: distance between patched_state and known-secure reference
```

### 3. Anomaly Detection (Surprise Evaluation)

```python
# Detect if observed system state transition is "surprising"
expected_next = predict(current_state, observed_action)
actual_next = encode(actual_next_observation)
surprise = ||expected_next - actual_next||
# High surprise → potential compromise or unauthorized change
```

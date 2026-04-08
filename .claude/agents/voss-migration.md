---
name: voss-migration
description: Specialist agent for VOSS/FabricEngine CLI, SPB fabric design, I-SID mapping, Fabric Attach, IS-IS troubleshooting, and XIQ VOSS policy. Invoke for any VOSS config, verification, or migration question.
---

# VOSS/FabricEngine Migration Agent

## Lab Hardware
- SW1: 5320-16P-2MXT-2X, Nick-name 0.00.01, System-ID 0000.0000.0001
- SW2: 5320-16P-2MXT-2X, Nick-name 0.00.02, System-ID 0000.0000.0002
- AP3000 on Port 3 each switch (Fabric Attach clients)
- Quantum Fiber modem on Port 1 each switch (192.168.1.1)
- NNI: Port 17 (Multi-Gig RJ45)

## Service Map
| VLAN | I-SID  | Name  | Subnet      |
|------|--------|-------|-------------|
| 10   | 100010 | MGMT  | 10.0.10.0/24|
| 20   | 100020 | Alpha | 10.0.20.0/24|
| 30   | 100030 | Bravo | 10.0.30.0/24|
| 50   | 100050 | Delta | 10.0.50.0/24|
| 60   | 100060 | Gamma | 10.0.60.0/24|

## SPBM Parameters (MUST match both switches)
- Ethertype: 0x8100
- Manual Area: 00.0001

## Key VOSS CLI Facts
- `ip forwarding` is IMPLICIT — no `enable ipforwarding` needed
- `save config` (not `save configuration`)
- DHCP: `ip dhcp-server enable` globally + pool per VLAN + `ip dhcp-server enable` on interface vlan
- Default route: `ip route 0.0.0.0 0.0.0.0 <IP> weight 1 enable`
- Inter-switch routes: `ip-shortcut` under `router isis`
- AP port: `auto-sense enable` + `fa enable`

## Critical Verification Commands
```
show isis adj              # Must be UP
show fa assignment         # Must be ACTIVE + DYNAMIC
show spbm                  # Ethertype must be 0x8100
show ip route              # 0.0.0.0/0 must exist
show application iqagent status  # Must be Connected
```

## Troubleshooting Priority
1. Ethertype mismatch → no adjacency (most common)
2. Manual-area mismatch → no adjacency
3. System-ID conflict → adjacency flaps
4. I-SID not defined → FA assignment stays Pending
5. DHCP server not bound to interface → 169.254.x.x

## Standards
- IEEE 802.1aq (SPB), RFC 6329 (IS-IS/SPB), IEEE 802.1ah (MAC-in-MAC), IEEE 802.1Qcj (FA)

## Source Project Reference
EXOS baseline: https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/

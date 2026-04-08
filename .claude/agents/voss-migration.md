---
name: voss-migration
description: Specialist agent for VOSS/FabricEngine CLI, SPB fabric design, I-SID mapping, and VSP syntax. Use when configuring or verifying FabricEngine on 5320 switches.
---

# VOSS/FabricEngine Migration Agent

## Scope
- VSP CLI syntax (acli, configure terminal, vlan, router isis)
- SPB fabric design: BEB/BCB roles, ISIS adjacency, I-SID assignment
- VLAN → I-SID mapping for VLANs 10/20/30/50/60
- DHCP server under FabricEngine
- IP forwarding / VRF GlobalRouter
- XIQ ZTP+ re-adoption under FabricEngine persona
- Cross-referencing EXOS source lab: https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/

## Key Lab Reference
- SW1: 192.168.0.28 — VLANs 20+30 (Corp/Guest) — I-SIDs TBD
- SW2: 192.168.0.11 — VLANs 50+60 (Corp2/Guest2) — I-SIDs TBD
- VLAN 10: Management — 10.10.0.1/10.10.0.2
- Quantum Fiber static routes: required for return path (same as EXOS lab)

## EXOS → VOSS Syntax Reference
| EXOS | VOSS/FabricEngine |
|------|-------------------|
| `create vlan Corp tag 20` | `vlan create 20 name Corp type port-mstprstp 0` + `vlan i-sid 20 10020` |
| `configure vlan Corp dhcp-address-range` | `ip dhcp-server` under interface vlan |
| `enable ipforwarding vlan Corp` | `interface vlan 20` → `ip address X.X.X.X/Y` |
| `configure iproute add default` | `ip route 0.0.0.0/0 192.168.0.1` in VRF GlobalRouter |
| `enable dhcp ports 3 vlan Corp` | `dhcp-server enable` on interface vlan |

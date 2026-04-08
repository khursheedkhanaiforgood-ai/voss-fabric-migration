# VOSS/FabricEngine Migration — Claude Code Instructions

## Project Purpose
Document and guide the migration of a 2-switch 2-AP EXOS/SwitchEngine lab to VOSS/FabricEngine.
Hardware: 2× Extreme 5320-16P-2MXT-2X + 2× AP3000, managed via XIQ.

## Source Lab (baseline being migrated)
- Repo: https://github.com/khursheedkhanaiforgood-ai/5320-onboarding
- Live docs: https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
- SW1: 192.168.0.28 — VLANs 20+30 (Corp/Guest) — AP3000 on port 3
- SW2: 192.168.0.11 — VLANs 50+60 (Corp2/Guest2) — AP3000 on port 3
- VLAN 10: SW_VLAN_10_Mgmt — SVIs 10.10.0.1/10.10.0.2

## Migration Phases
1. Factory reset → FabricEngine ZTP+ → XIQ re-adoption
2. SPB fabric + VLAN/I-SID design (VLANs 10/20/30/50/60 → I-SIDs)
3. DHCP + routing + AP3000 re-verification (all 4 SSIDs)

## HTML/Docs Conventions
- Theme: NYT style — white bg #FFFFFF, Libre Baskerville headings, Libre Franklin body, NYT blue #326891
- GitHub Pages: served from main branch root
- Session logs: session_log_YYYYMMDD.html pattern
- All pages link back to index.html

## Switch Credentials
- FabricEngine: rwa / rwa (admin blocked in pre-GA)
- Serial: /dev/cu.usbserial-A9VKJO11 @ 115200 baud

## Global Agents
- planner — before any new phase
- code-reviewer — after writing code

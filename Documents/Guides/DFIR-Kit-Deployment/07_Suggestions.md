---
layout: default
title: "07 Suggestions"
---

## Purpose

Operational recommendations that extend the baseline deployment guides. These are **not** a substitute for your organization’s security policy or change management.

## Scale and resilience

- **Cluster multiple ESXi nodes** (or move to a supported VMware cluster design) when you need more RAM, CPU, storage performance, or **more concurrent FLARE** workstations than a **single 128 GB** host can sustain. See **[02 Limitations](./02_Limitations)**.

## Evidence and laptops

- **Keep forensic artifacts off unmanaged analyst laptops.** Interactive work with images, KAPE bundles, and large exports should happen on **FLARE VMs** with shares mounted per **[04 NAS deployment](./04_NAS-Deployment)**.
- **Vault on laptops** is for **Obsidian / notes / runbooks** only — not for disk images, malware samples, or case exports.

## Virtual machine hygiene

- Take **frequent snapshots** of **all** infrastructure VMs (NAS, ELK, FLARE templates) at **known-good milestones** — after patching windows, after major config changes, and before risky upgrades.
- Remember: snapshots are **rollback convenience**, not a **backup strategy** for evidence. Evidence lifecycle belongs on **NAS** design and organizational retention policy.

---

## DFIR kit guides

- [Overview](./index)
- [01 Introduction](./01_Introduction)
- [02 Limitations](./02_Limitations)
- [03 ESXi deployment](./03_ESXi-Deployment)
- [04 NAS deployment](./04_NAS-Deployment)
- [05 ELK deployment](./05_ELK-Deployment)
- [06 Flare VM build](./06_Flare-VM-Build)
- [07 Suggestions](./07_Suggestions)

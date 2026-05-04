---
layout: default
title: "02 Limitations"
---

## Purpose

This document captures **capacity and topology limits** of the reference DFIR kit as deployed on a **single ESXi node**, so teams know when the design is appropriate and when to plan a larger platform.

## Single-node constraints

The reference lab assumes **one physical ESXi host** with **128 GB of RAM** and a **finite CPU budget** shared by the hypervisor, NAS, ELK, FLARE, and any utility VMs.

### FLARE analyst capacity

On this baseline host we sized **three FLARE VMs** at **24 GB RAM each**, with **conservative vCPU** allocations so the hypervisor remains stable during heavy tool use (memory forensics, large timelines, multiple GUIs).

That choice **severely caps** how many analysts can work concurrently at full performance, and it **bottlenecks** scenarios that need:

- Multiple large memory images open at once
- Parallel KAPE / Hayabusa / heavy Zimmerman workloads across many VMs
- Extra headroom for ad-hoc helper VMs

This is acceptable for a **small kit** or proof-of-concept lab; it is **not** a substitute for a multi-analyst enterprise forensic farm.

## When to scale out

For **longer-term production** use, **more analysts**, or **higher case throughput**, plan a deployment on **clustered ESXi nodes** (or an equivalent supported VMware stack) so you can:

- Spread FLARE and ELK workloads across hosts
- Isolate storage and indexing I/O from analyst desktops
- Grow RAM and CPU independently per role
- Apply HA, DRS, and shared storage where your organization allows

The numbered deployment guides in this folder remain a **logical sequence**; only the **hardware footprint and cluster configuration** change at scale.

## Related reading

- [03 ESXi deployment](./03_ESXi-Deployment) — host and port-group baseline  
- [07 Suggestions](./07_Suggestions) — snapshots, data placement, and collaboration hygiene  

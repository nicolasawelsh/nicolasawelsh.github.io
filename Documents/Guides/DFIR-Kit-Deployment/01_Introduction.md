---
layout: default
title: "01 Introduction"
---

## Purpose

This guide set defines a repeatable build process for a small **DFIR kit** hosted on a standalone **VMware ESXi** host. The kit supports host image staging, artifact extraction, CSV-based timeline ingestion, analyst collaboration, and **Kibana**-based review **without requiring vCenter**.

The design assumes a **segmented lab network** where the **NAS** stores evidence and staging data, the **FLARE VM** performs Windows-based triage and tool execution, and the **ELK VM** indexes curated artifact CSVs for hunting and correlation. These documents are written as a **deployment and validation playbook**, not a theory overview.

## Target architecture

```text
Standalone ESXi host
├── Management network (vmnic0 / Host Client access)
└── Segmented DFIR port group — lab subnet 172.16.0.0/24
    ├── NAS VM     172.16.0.10   Samba: ingest, evidence, vault
    ├── ELK VM     172.16.0.20   Elasticsearch, Logstash, Kibana
    ├── FLARE VM   172.16.0.x    Windows analysis workstation(s)
    └── Analyst systems as required (see NAS guide for mount policy)
```

## Operational principles

- Keep original evidence **read-only** whenever practical.
- **Separate** evidence storage from working ingest copies.
- Use the NAS as **controlled storage** and the ELK VM **local disk** for Logstash processing (see ELK deployment guide).
- Use **snapshots or templates** for infrastructure rollback; do **not** treat snapshots as evidence backups.
- Document credentials in an **approved vault**, not in these public-facing pages.
- **Validate** each service before moving to the next deployment phase.

## IP addressing baseline

| Item | Standard / value |
|------|------------------|
| Lab CIDR | 172.16.0.0/24 |
| Default gateway | 172.16.0.1 |
| NAS VM | 172.16.0.10 |
| ELK VM | 172.16.0.20 |
| FLARE VM | Static or DHCP reservation inside 172.16.0.0/24 |

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

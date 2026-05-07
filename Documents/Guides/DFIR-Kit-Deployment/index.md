---
layout: default
title: DFIR-Kit-Deployment
---

# DFIR-Kit-Deployment

This guide set walks through building a practical DFIR lab on a **standalone ESXi** host: **network and hypervisor** setup, **NAS** storage, **FLARE** Windows analysis VMs, **artifact carving** (EvtxECmd, Hayabusa, MFTECmd, Plaso JSONL—or **KAPE** for orchestration), and a **single-node ELK** stack so analysts can hunt timelines in **Kibana**.

Read **01 Introduction** for architecture and principles, then follow the numbered guides through **06**. Use **07** when exporting artifacts for ingest (including **Plaso** JSONL via Docker), **08** for operational habits (snapshots, scale, laptops).

---

## Guides in this set

| Guide | Contents |
|-------|----------|
| [01 Introduction](./01_Introduction) | Purpose, lab topology, IP baseline |
| [02 Limitations](./02_Limitations) | Host RAM/VM counts and constraints |
| [03 ESXi deployment](./03_ESXi-Deployment) | Standalone ESXi and DFIR port group |
| [04 NAS deployment](./04_NAS-Deployment) | Ubuntu NAS, Samba shares, mount policy |
| [05 ELK deployment](./05_ELK-Deployment) | Elasticsearch, Logstash, Kibana, ingest |
| [06 Flare VM build](./06_Flare-VM-Build) | Windows FLARE workstation and NAS use |
| [07 Artifact carving](./07_Artifact-Carving) | EvtxECmd, Hayabusa, MFTECmd, **Plaso JSONL** (Docker), ELK filenames (`DESKTOP-EXAMPLE_*`) |
| [08 Suggestions](./08_Suggestions) | Snapshots, scale, evidence handling |

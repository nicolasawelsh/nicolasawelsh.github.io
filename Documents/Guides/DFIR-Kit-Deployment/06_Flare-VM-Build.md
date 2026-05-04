---
layout: default
title: "06 Flare VM Build"
---

## Purpose

This guide describes how to **build and harden** a Windows **FLARE VM** as the primary **interactive forensic workstation** in the DFIR kit. FLARE VM is maintained by **Mandiant**; follow the **official project** for installation mechanics. This page records **lab-specific** choices, **additional tools**, **NAS integration**, and how the VM fits the **[04 NAS deployment](./04_NAS-Deployment)** mount policy.

Official repository and documentation: [github.com/mandiant/flare-vm](https://github.com/mandiant/flare-vm)

The upstream project states that FLARE VM is a collection of installation scripts for **Windows VMs** (not physical PCs), with requirements such as Windows 10 or newer, PowerShell 5+, sufficient disk and RAM, **internet access during install**, and temporary changes to updates / Defender per their README. Read their current guidance before you build.

## Table of Contents

- [Where to get FLARE VM](#where-to-get-flare-vm)
- [Build environment](#build-environment)
- [Recommended baseline (DFIR kit)](#recommended-baseline-dfir-kit)
- [Build sequence](#build-sequence)
- [Additional tools installed (this kit)](#additional-tools-installed-this-kit)
- [Licensing](#licensing)
- [NAS shares from FLARE](#nas-shares-from-flare)
- [Validation checklist](#validation-checklist)

---

<a id="where-to-get-flare-vm"></a>
## Where to get FLARE VM

Clone or download the **Mandiant FLARE-VM** repository from **[github.com/mandiant/flare-vm](https://github.com/mandiant/flare-vm)** and run the installer **exactly** as described in the project’s `README` (elevated PowerShell, profile selection, reboots, etc.). Do not use unofficial bundles for production lab use.

---

<a id="build-environment"></a>
## Build environment

- **Internet required during build:** FLARE-VM pulls packages and dependencies from the network. Build on a **NATed lab build network** or temporary internet segment, then move the finished VM to **`PG-DFIR-LAB`** per **[03 ESXi deployment](./03_ESXi-Deployment)**.
- **VMware Tools:** Install on the guest before or as part of your standard so consoles and copy/paste behave predictably.
- **Snapshots:** Take a **clean Windows + Tools** snapshot **before** running the FLARE installer, and a **post-install validated** snapshot before promoting the VM to a template or production clone.

---

<a id="recommended-baseline-dfir-kit"></a>
## Recommended baseline (DFIR kit)

Aligns with the SOP and **[02 Limitations](./02_Limitations)** when running **multiple FLARE clones** on a **128 GB** single-node host:

- **OS:** Windows 10 or 11 (approved media and **valid licenses**).
- **vCPU:** 4+ per VM where the host can sustain it; reduce count if you run **three** heavy FLAREs concurrently.
- **RAM:** **24 GB per FLARE** in the reference three-VM layout (adjust if your host budget differs).
- **Disk:** **120 GB** minimum; increase if you keep large local scratch on the VM (prefer storing big images on **NAS `evidence`** per mount policy).

---

<a id="build-sequence"></a>
## Build sequence

1. Create the Windows VM on ESXi and install the OS (internet-connected if policy allows).
2. Apply required **Windows Updates** before FLARE install if your timeline allows.
3. Create a **local administrator** account whose username avoids spaces/special characters (per FLARE guidance).
4. Follow Mandiant’s steps to **pause Windows Update** and **Defender / Tamper Protection** only for the install window, then restore per org policy after tooling is stable.
5. Run the **official FLARE-VM** install script and complete all reboots.
6. Install **[additional tools](#additional-tools-installed-this-kit)** that your team licenses and approves.
7. Validate tooling, then take **snapshots** / **template** per **[07 Suggestions](./07_Suggestions)**.
8. Attach the VM to **`PG-DFIR-LAB`** and verify **NAS** and **Kibana** reachability.

---

<a id="additional-tools-installed-this-kit"></a>
## Additional tools installed (this kit)

Beyond the FLARE-VM bundle, this deployment adds common DFIR utilities (install only what your organization **approves** and **licenses**):

| Tool | Role |
|------|------|
| **Autopsy** | Disk image review and triage |
| **Eric Zimmerman tools** | Windows artifact parsing |
| **Hayabusa** | EVTX sigma-style hunting |
| **KAPE** | Targeted collection and module output |
| **MemProcFS** | Live memory / image filesystem views |
| **NetworkMiner** | PCAP carving and session overviews |
| **Volatility** | Memory analysis framework |
| **Arsenal Image Mounter** | Mount forensic images |
| **FTK Imager** | Image acquisition and mount |
| **Magnet** (Magnet-branded suite components as used by your team) | Additional triage / review per license |

Exact installers and versions change often; record build versions in your **internal build sheet**, not in public credentials.

---

<a id="licensing"></a>
## Licensing

**All commercial software must be properly licensed.** FLARE-VM includes many open-source tools, but products such as **FTK Imager**, **Magnet** offerings, some **Autopsy** deployment models, and certain **commercial** plugins require **organization-owned entitlements**. Keep license keys and installers in an **approved vault**, not in this repository.

---

<a id="nas-shares-from-flare"></a>
## NAS shares from FLARE

Per **[04 NAS deployment](./04_NAS-Deployment)**:

- **`evidence`** — Mount on **FLARE** and work with forensic images **directly from the NAS** when your procedure allows (read-only or controlled writes per NAS ACLs). **Do not** copy full case images to unmanaged laptops.
- **`ingest`** — Mount on **FLARE** for **CSV staging**, **KAPE** and other tool outputs destined for ELK, scratch collaboration, and intermediate files that belong in the **lab-controlled** path before operators sync to the ELK workflow described in **[05 ELK deployment](./05_ELK-Deployment)**.
- **`vault`** — FLARE **may** use `vault` if your team places shared notes there; **laptops** may mount **`vault` only** for lightweight notes (see NAS guide). Keep **forensic artifacts off laptops**.

Expected SMB paths (example NAS `172.16.0.10`):

```text
\\172.16.0.10\evidence
\\172.16.0.10\ingest
\\172.16.0.10\vault
```

Kibana (example ELK host):

```text
http://172.16.0.20:5601
```

---

<a id="validation-checklist"></a>
## Validation checklist

```text
[ ] Windows activated/licensed per policy
[ ] VMware Tools installed
[ ] Official FLARE-VM installation completed without errors
[ ] Additional licensed tools installed and smoke-tested
[ ] Snapshots/templates captured at known-good points
[ ] VM attached to PG-DFIR-LAB
[ ] SMB access to ingest and evidence per NAS ACLs
[ ] Kibana reachable from FLARE browser
[ ] No sensitive case data stored in the golden template VM
```

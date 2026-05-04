---
layout: default
title: "03 ESXi Deployment"
---

## Purpose

This chapter covers a **standalone ESXi** deployment for the DFIR kit. It intentionally **avoids vCenter** and keeps the host manageable through the **ESXi Host Client**. The goal is a stable hypervisor baseline that can host the **NAS**, **FLARE**, and **ELK** VMs on a **segmented lab network** while preserving **management access**.

## Table of Contents

- [Recommended host baseline](#recommended-host-baseline)
- [Pre-installation checklist](#pre-installation-checklist)
- [Install ESXi](#install-esxi)
- [Configure ESXi management network](#configure-esxi-management-network)
- [Initial Host Client login](#initial-host-client-login)
- [Create or validate datastore](#create-or-validate-datastore)
- [Networking model](#networking-model)
- [Create a segmented DFIR port group](#create-a-segmented-dfir-port-group)
- [VM resource standards](#vm-resource-standards)
- [Upload installation ISOs](#upload-installation-isos)
- [Create the NAS VM](#create-the-nas-vm)
- [Create the FLARE VM](#create-the-flare-vm)
- [Create the ELK VM](#create-the-elk-vm)
- [Standalone ESXi operational guardrails](#standalone-esxi-operational-guardrails)
- [ESXi validation checklist](#esxi-validation-checklist)

---

<a id="recommended-host-baseline"></a>
## Recommended host baseline

- **CPU:** Modern x86_64 CPU with virtualization support enabled in BIOS/UEFI.
- **RAM:** 64 GB minimum; **128 GB preferred** if running ELK and multiple analyst VMs.
- **Storage:** SSD/NVMe datastore strongly preferred for ELK; large-capacity datastore for NAS / evidence staging.
- **NICs:** At least **two physical adapters** preferred: one for management/uplink, one or more for segmented lab switching.
- **Management access:** Dedicated management IP reachable only from a **trusted admin** workstation or network.
- **Time:** Configure reliable **NTP** before production use so forensic timestamps stay consistent.

---

<a id="pre-installation-checklist"></a>
## Pre-installation checklist

- Download the **approved ESXi installer ISO** for the hardware platform.
- Confirm storage devices are visible in BIOS/UEFI and not reserved for another controller mode.
- Enable **Intel VT-x / VT-d** or **AMD-V / IOMMU** if available.
- Label physical NICs or document switch-port mappings before installation.
- Decide which NIC remains **dedicated to management** so remote access is not lost during lab network configuration.
- Prepare **static IP** details for the ESXi management interface.
- Prepare **ISO files** for Ubuntu Server and Windows installation media.

---

<a id="install-esxi"></a>
## Install ESXi

1. Boot the server from the ESXi installer ISO or USB installer.
2. Accept the license agreement and select the boot/install disk.
3. Set the **root** password and complete installation.
4. Reboot and remove installation media.
5. At the **Direct Console User Interface (DCUI)**, configure the management network.

---

<a id="configure-esxi-management-network"></a>
## Configure ESXi management network

From the **DCUI**, configure the management NIC and static IP. Keep this network simple and reachable **before** creating any segmented lab networks.

Example management values (replace placeholders):

```text
Management IP:  <ESXI-MGMT-IP>
Subnet mask:    <SUBNET-MASK>
Gateway:        <DEFAULT-GATEWAY>
DNS:            <DNS-SERVER>
Hostname:       <ESXI-HOSTNAME>
```

---

<a id="initial-host-client-login"></a>
## Initial Host Client login

1. Browse to `https://<ESXI-MGMT-IP>/ui` from an admin workstation.
2. Log in as **root** using the password configured during installation.
3. Verify the host summary, CPU, RAM, storage adapters, physical NICs, and datastore visibility.
4. Confirm the management vmkernel interface is on the intended network **before** changing virtual switching.

---

<a id="create-or-validate-datastore"></a>
## Create or validate datastore

Use the ESXi Host Client to create the datastore that will hold the VMs. If multiple datastore types exist, place the **ELK VM** on the **fastest** datastore available (Elasticsearch indexing and search).

1. Navigate to **Storage → Datastores**.
2. Create a new **VMFS** datastore if one does not already exist.
3. Name the datastore clearly, for example `datastore-dfir-fast` or `datastore-dfir-capacity`.
4. Confirm free space is sufficient before deploying the NAS and ELK VMs.

---

<a id="networking-model"></a>
## Networking model

For a basic standalone build, keep **vSwitch0** for **management** and create **one additional** standard vSwitch or port group for the **segmented DFIR lab**. Do **not** remove the active management uplink while remotely connected.

Recommended simple layout:

```text
vSwitch0
  Port group: Management Network
  Uplink:     vmnic0
  Purpose:    ESXi management access

vSwitch-DFIR-LAB
  Port group: PG-DFIR-LAB
  Uplink:     optional dedicated lab NIC, or no uplink for isolated-only lab
  Purpose:    NAS, FLARE VM, ELK VM, analyst lab VMs
```

---

<a id="create-a-segmented-dfir-port-group"></a>
## Create a segmented DFIR port group

1. In the ESXi Host Client, navigate to **Networking → Virtual switches**.
2. Create a **new standard switch** for the lab, or add a new port group to an existing lab switch.
3. Name the port group **`PG-DFIR-LAB`** (or equivalent documented name).
4. If the lab must be physically reachable, assign the intended **lab uplink**. If the lab should be **fully isolated**, leave the switch **without** an uplink.
5. Attach **NAS**, **FLARE**, and **ELK** VM virtual NICs to **PG-DFIR-LAB**.

---

<a id="vm-resource-standards"></a>
## VM resource standards

- **NAS VM:** Ubuntu Server 22.04/24.04, 2–4 vCPU, 4–8 GB RAM, large disk (for example **5 TB**) depending on evidence needs.
- **ELK VM:** Ubuntu Server 22.04/24.04, **4+ vCPU**, **16 GB RAM minimum**, **32 GB preferred**, **~1 TB** disk recommended for indexing headroom.
- **FLARE VM:** Windows 10/11, **4+ vCPU**, **8–16 GB RAM** baseline (see [02 Limitations](./02_Limitations) and [06 Flare VM build](./06_Flare-VM-Build) for multi-VM sizing), **120+ GB** disk preferred for tools and working data.
- **Snapshots:** Take snapshots only at **clean configuration** points; do not rely on snapshots for long-term rollback or backups.
- **Templates:** Use clean templates for FLARE (and optionally Ubuntu base VMs) to accelerate future deployments.

---

<a id="upload-installation-isos"></a>
## Upload installation ISOs

1. Navigate to **Storage → Datastore browser**.
2. Create an **ISO** folder if one does not already exist.
3. Upload **Ubuntu Server** and **Windows** ISO files.
4. Attach ISOs to VM CD/DVD drives during VM creation.

---

<a id="create-the-nas-vm"></a>
## Create the NAS VM

1. Create a new virtual machine named **`DFIR-NAS`** (or similar).
2. Attach the VM network adapter to **PG-DFIR-LAB**.
3. Install **Ubuntu Server**.
4. Complete the NAS build in **[04 NAS deployment](./04_NAS-Deployment)**.

---

<a id="create-the-flare-vm"></a>
## Create the FLARE VM

1. Create a new Windows VM named **`FLARE-TEMPLATE`** or **`DFIR-FLARE`**.
2. Install Windows **while internet-connected** if possible so FLARE-VM and tooling can be installed before moving to the segmented network.
3. Install **VMware Tools**.
4. Complete the FLARE build in **[06 Flare VM build](./06_Flare-VM-Build)**.

---

<a id="create-the-elk-vm"></a>
## Create the ELK VM

1. Create a new virtual machine named **`DFIR-ELK`** (or similar).
2. Attach the VM network adapter to **PG-DFIR-LAB**.
3. Install **Ubuntu Server**.
4. Complete the ELK deployment in **[05 ELK deployment](./05_ELK-Deployment)**.

---

<a id="standalone-esxi-operational-guardrails"></a>
## Standalone ESXi operational guardrails

- Do **not** expose the ESXi management interface to **untrusted** networks.
- Use **strong root** credentials and store them in an approved vault.
- Keep **one known-good management uplink** active while testing virtual switching.
- Use clear **VM names** and datastore folders so analysts can identify system purpose quickly.
- **Document** which port group each VM uses and which physical NICs back those port groups.
- Avoid mixing **evidence staging** traffic with **management** traffic when a dedicated lab NIC is available.

---

<a id="esxi-validation-checklist"></a>
## ESXi validation checklist

```text
[ ] ESXi host is reachable through the Host Client
[ ] Management network is stable and documented
[ ] Datastore is created and has sufficient capacity
[ ] PG-DFIR-LAB (or equivalent segmented lab port group) exists
[ ] NAS VM is attached to the lab port group
[ ] FLARE VM is attached to the lab port group after build/template preparation
[ ] ELK VM is attached to the lab port group
[ ] VM resource allocations match the SOP baseline (adjusted for your kit size)
[ ] Root credentials and host details are stored in the approved credential vault
[ ] Clean snapshots/templates exist only where operationally appropriate
```

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

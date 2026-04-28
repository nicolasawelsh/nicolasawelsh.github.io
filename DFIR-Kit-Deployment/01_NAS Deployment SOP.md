---
layout: default
title: "01 NAS Deployment SOP"
---

## Purpose

This SOP documents a repeatable deployment for a DFIR NAS on Ubuntu Server using Samba. The NAS provides controlled file shares for ingestion staging, read-only evidence access, and analyst notes storage for the lab environment.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Section 1 — Prepare Ubuntu Server](#section-1-prepare-ubuntu-server)
- [Section 2 — Online Package Install](#section-2-online-package-install)
- [Section 3 — Post ESXi Migration Configuration](#section-3-post-esxi-migration-configuration)
- [Section 4 — Create Groups and Users](#section-4-create-groups-and-users)
- [Section 5 — Create NAS Directory Structure](#section-5-create-nas-directory-structure)
- [Section 6 — Configure Linux Permissions and ACLs](#section-6-configure-linux-permissions-and-acls)
- [Section 7 — Configure Samba Shares](#section-7-configure-samba-shares)
- [Section 8 — Validate Samba Configuration](#section-8-validate-samba-configuration)
- [Section 9 — Verify Share Access](#section-9-verify-share-access)
- [Section 10 — Mount NAS Share from ELK VM](#section-10-mount-nas-share-from-elk-vm)
- [Section 11 — Operational Guardrails](#section-11-operational-guardrails)
- [Section 12 — Testing and Troubleshooting Notes](#section-12-testing-and-troubleshooting-notes)
- [Section 13 — Configure Firewall (UFW)](#section-13-configure-firewall-ufw)
- [Section 14 — Final Validation Checklist](#section-14-final-validation-checklist)
- [Appendix A — Recommended Share Mapping](#appendix-a-recommended-share-mapping)
- [Appendix B — Credential Tracking Worksheet](#appendix-b-credential-tracking-worksheet)

---

<a id="architecture-overview"></a>
## Architecture Overview

```text
NAS IP: 172.16.0.10
ELK VM (example): 172.16.0.20
Default Gateway: 172.16.0.1
Lab CIDR: 172.16.0.0/24
Protocol: Samba (SMB/CIFS)

Shares:
  ingest  -> CSV staging for ELK ingest
  evidence   -> read-only to analysts, write access for admins
  vault      -> analyst/admin collaboration (notes, runbooks)
```

---

<a id="section-1-prepare-ubuntu-server"></a>
## Section 1 — Prepare Ubuntu Server

### Recommended VM Resources

```text
OS:       Ubuntu Server 22.04 LTS or 24.04 LTS
CPU:      2-4 vCPU
RAM:      4-8 GB
Disk:     5 TB recommended
Network:  Lab VLAN/Subnet (172.16.0.0/24)
```

---

<a id="section-2-online-package-install"></a>
## Section 2 — Online Package Install

These steps require internet access. Complete them before moving the VM into an offline/isolated ESXi environment.

Build sequence for this SOP:

1. Build the VM while internet-connected.
2. Complete package and repository installation in this section.
3. Move the VM to ESXi/lab network and complete post-move network/storage steps in `Section 3`.

If you must build offline, use an approved internal mirror/repository for Ubuntu packages.

### Update the System and Install Baseline Prerequisites

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y samba acl cifs-utils ufw
```

---

<a id="section-3-post-esxi-migration-configuration"></a>
## Section 3 — Post ESXi Migration Configuration

### Configure a Static IP with Netplan After Migrating to ESXi

1. Identify the network interface name:

```bash
ip link
ip addr
```

2. Edit the Netplan config (file name may vary under `/etc/netplan/`):

```bash
ls /etc/netplan
sudo nano /etc/netplan/00-installer-config.yaml
```

3. Example static IP configuration (update `ens160`, IP, gateway, and DNS):

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    ens160:
      dhcp4: no
      addresses:
        - 172.16.0.10/24
      routes:
        - to: default
          via: 172.16.0.1
      nameservers:
        addresses:
          - 172.16.0.1
          - 1.1.1.1
```

4. Validate and apply:

```bash
sudo netplan try
sudo netplan apply
```

5. Verify:

```bash
ip addr
ip route
```

### Resize Disk After ESXi Expansion (If Applicable)

If the VM disk was expanded in ESXi, grow the Ubuntu LVM-backed root filesystem.

#### Verify Disk Size

```bash
lsblk
```

Confirm the main disk (often `/dev/sda` on ESXi, but sometimes `/dev/nvme0n1`) reflects the new size.

#### Identify the Correct LVM Partition (It May Not Be `sda3`)

You need to run `growpart` and `pvresize` against the **partition that is the LVM physical volume** (it will typically show as `LVM2_member`).

Run:

```bash
lsblk -f
sudo pvs
```

Look for:

- In `lsblk -f`: a partition with `FSTYPE` = `LVM2_member` (example: `/dev/sda3`)
- In `pvs`: a `PV` path like `/dev/sda3` (this is the exact device to use)

If your PV is not `/dev/sda3`, substitute your actual PV device in the commands below.

#### Grow the PV Partition

Example mappings:

- If `pvs` shows `/dev/sda2`, then use `sudo growpart /dev/sda 2` and `sudo pvresize /dev/sda2`
- If `pvs` shows `/dev/nvme0n1p3`, then use `sudo growpart /dev/nvme0n1 3` and `sudo pvresize /dev/nvme0n1p3`

```bash
sudo growpart /dev/sda 3
```

#### Resize the LVM Physical Volume

```bash
sudo pvresize /dev/sda3
```

#### Extend the Root Logical Volume

```bash
sudo lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
```

#### Resize the Filesystem

```bash
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
```

#### Verify

```bash
df -h
```

Expected result: root filesystem `/` should show close to the expanded disk size.

---

<a id="section-4-create-groups-and-users"></a>
## Section 4 — Create Groups and Users

Create groups:

```bash
sudo groupadd analysts
sudo groupadd admins
```

Create example users:

```bash
sudo useradd -m -G analysts analyst1
sudo passwd analyst1

sudo useradd -m -G admins admin1
sudo passwd admin1
```

Add Linux users to Samba:

```bash
sudo smbpasswd -a analyst1
sudo smbpasswd -a admin1
```

---

<a id="section-5-create-nas-directory-structure"></a>
## Section 5 — Create NAS Directory Structure

```bash
sudo mkdir -p /data/ingest
sudo mkdir -p /data/evidence
sudo mkdir -p /data/vault
```

---

<a id="section-6-configure-linux-permissions-and-acls"></a>
## Section 6 — Configure Linux Permissions and ACLs

Set base ownership:

```bash
sudo chown -R root:admins /data
```

Set primary groups per share:

```bash
sudo chgrp -R analysts /data/ingest
sudo chgrp -R admins /data/evidence
sudo chgrp -R analysts /data/vault
```

Set directory permissions:

```bash
sudo chmod -R 2770 /data/ingest
sudo chmod -R 2770 /data/vault
sudo chmod -R 2770 /data/evidence
```

Grant analysts read/execute on evidence; admins full control:

```bash
sudo setfacl -R -m g:analysts:rx /data/evidence
sudo setfacl -R -m g:admins:rwx /data/evidence
sudo setfacl -R -d -m g:analysts:rx /data/evidence
sudo setfacl -R -d -m g:admins:rwx /data/evidence
```

---

<a id="section-7-configure-samba-shares"></a>
## Section 7 — Configure Samba Shares

Back up existing config:

```bash
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
sudo nano /etc/samba/smb.conf
```

Use/append this share configuration:

```ini
[ingest]
   path = /data/ingest
   browseable = yes
   read only = no
   valid users = @analysts @admins
   write list = @analysts @admins
   force group = analysts
   create mask = 0660
   directory mask = 2770

[evidence]
   path = /data/evidence
   browseable = yes
   read only = yes
   valid users = @analysts @admins
   write list = @admins
   force group = admins
   create mask = 0660
   directory mask = 2770

[vault]
   path = /data/vault
   browseable = yes
   read only = no
   valid users = @analysts @admins
   write list = @analysts @admins
   force group = analysts
   create mask = 0660
   directory mask = 2770
```

Restart Samba:

```bash
sudo systemctl restart smbd
sudo systemctl enable smbd
```

---

<a id="section-8-validate-samba-configuration"></a>
## Section 8 — Validate Samba Configuration

```bash
testparm
sudo systemctl status smbd
sudo smbstatus
```

Expected result: no syntax errors from `testparm`, and `smbd` active/running.

---

<a id="section-9-verify-share-access"></a>
## Section 9 — Verify Share Access

From Windows or FLARE VM:

```text
\\172.16.0.10\ingest
\\172.16.0.10\evidence
\\172.16.0.10\vault
```

Validation:

```text
analyst user can write to ingest and vault
analyst user cannot write to evidence
admin user can write to all three shares
```

---

<a id="section-10-mount-nas-share-from-elk-vm"></a>
## Section 10 — Mount NAS Share from ELK VM

Create mount point and credentials file:

```bash
sudo mkdir -p /ingest
sudo nano /root/.smbcred
```

Credentials file example:

```text
username=analyst1
password=YOUR_PASSWORD
```

Secure credentials and configure fstab:

```bash
sudo chmod 600 /root/.smbcred
sudo nano /etc/fstab
```

```text
//172.16.0.10/ingest /ingest cifs credentials=/root/.smbcred,vers=3.0,ro,uid=logstash,gid=logstash,file_mode=0444,dir_mode=0555,nofail 0 0
```

Mount and validate:

```bash
sudo mount -a
ls -l /ingest
```

---

<a id="section-11-operational-guardrails"></a>
## Section 11 — Operational Guardrails

- Treat `evidence` as controlled source storage.
- Keep ELK ingest workflow against local copy (`/ingest_local`) instead of direct SMB reads.
- Use least privilege for all analyst accounts.
- Rotate Samba credentials on a defined schedule.
- Snapshot/backup NAS data before major permission changes.

---

<a id="section-12-testing-and-troubleshooting-notes"></a>
## Section 12 — Testing and Troubleshooting Notes

### Test 1 — Share Access Denied

Check user/group membership and Samba user mapping:

```bash
id analyst1
sudo pdbedit -L
```

### Test 2 — Can Read but Cannot Write

Check share ACLs and Samba share block:

```bash
getfacl /data/ingest
getfacl /data/evidence
```

### Test 3 — Samba Config Fails to Start

```bash
testparm
sudo journalctl -u smbd -n 100
```

### Test 4 — ELK Cannot See NAS Files

```bash
mount | grep ingest
ls -l /ingest
```

---

<a id="section-13-configure-firewall-ufw"></a>
## Section 13 — Configure Firewall (UFW)

Restrict inbound access so SMB and SSH are reachable from `172.16.0.0/24` only.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 172.16.0.0/24 to any port 22 proto tcp
sudo ufw allow from 172.16.0.0/24 to any port 445 proto tcp
sudo ufw allow from 172.16.0.0/24 to any port 139 proto tcp
sudo ufw enable
sudo ufw status verbose
```

---

<a id="section-14-final-validation-checklist"></a>
## Section 14 — Final Validation Checklist

```text
[ ] NAS static IP is set to 172.16.0.10
[ ] UFW only allows SSH/SMB from 172.16.0.0/24
[ ] Samba service is active and enabled
[ ] testparm returns no Samba syntax errors
[ ] ingest share is writable by analysts/admins
[ ] evidence share is read-only for analysts
[ ] evidence share is writable for admins
[ ] vault share is writable by analysts/admins
[ ] ELK VM can mount NAS ingest share
[ ] Credentials are documented in approved vault
```

---

<a id="appendix-a-recommended-share-mapping"></a>
## Appendix A — Recommended Share Mapping

```text
Analyst workstation:
  \\172.16.0.10\vault

FLARE VM:
  \\172.16.0.10\ingest
  \\172.16.0.10\evidence

ELK VM:
  //172.16.0.10/ingest mounted at /ingest (read-only)
```

---

<a id="appendix-b-credential-tracking-worksheet"></a>
## Appendix B — Credential Tracking Worksheet

```text
Credential Name: NAS admin account
Username: <admin username>
Password Location: <vault reference>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
```

```text
Credential Name: Analyst SMB account(s)
Username(s): <analyst account list>
Password Location: <vault reference>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
```

```text
Credential Name: ELK NAS mount credential
Used By: /root/.smbcred on ELK VM
Username: <service account>
Password Location: <vault reference>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
```
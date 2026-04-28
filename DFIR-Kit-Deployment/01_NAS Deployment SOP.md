---
layout: default
title: "01 NAS Deployment SOP"
---

## Purpose

This SOP documents a repeatable deployment for a DFIR NAS on Ubuntu Server using Samba. The NAS provides controlled file shares for ingestion staging, read-only evidence access, and analyst notes storage for the lab environment.

## Table of Contents

- [[#Architecture Overview]]
- [[#Section 1 — Prepare Ubuntu Server]]
- [[#Section 2 — Online Package Install]]
- [[#Section 3 — Post ESXi Migration Configuration]]
- [[#Section 4 — Create Groups and Users]]
- [[#Section 5 — Create NAS Directory Structure]]
- [[#Section 6 — Configure Linux Permissions and ACLs]]
- [[#Section 7 — Configure Samba Shares]]
- [[#Section 8 — Validate Samba Configuration]]
- [[#Section 9 — Verify Share Access]]
- [[#Section 10 — Mount NAS Share from ELK VM]]
- [[#Section 11 — Operational Guardrails]]
- [[#Section 12 — Testing and Troubleshooting Notes]]
- [[#Section 13 — Configure Firewall (UFW)]]
- [[#Section 14 — Final Validation Checklist]]
- [[#Appendix A — Recommended Share Mapping]]
- [[#Appendix B — Credential Tracking Worksheet]]

---

## Architecture Overview

```text
NAS IP: 172.16.0.10
ELK VM (example): 172.16.0.20
Default Gateway: 172.16.0.1
Lab CIDR: 172.16.0.0/24
Protocol: Samba (SMB/CIFS)

Shares:
  ingest_rw  -> CSV staging for ELK ingest
  evidence   -> read-only to analysts, write access for admins
  vault      -> analyst/admin collaboration (notes, runbooks)
```

---

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

## Section 5 — Create NAS Directory Structure

```bash
sudo mkdir -p /data/ingest_rw
sudo mkdir -p /data/evidence
sudo mkdir -p /data/vault
```

---

## Section 6 — Configure Linux Permissions and ACLs

Set base ownership:

```bash
sudo chown -R root:admins /data
```

Set primary groups per share:

```bash
sudo chgrp -R analysts /data/ingest_rw
sudo chgrp -R admins /data/evidence
sudo chgrp -R analysts /data/vault
```

Set directory permissions:

```bash
sudo chmod -R 2770 /data/ingest_rw
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

## Section 7 — Configure Samba Shares

Back up existing config:

```bash
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
sudo nano /etc/samba/smb.conf
```

Use/append this share configuration:

```ini
[ingest_rw]
   path = /data/ingest_rw
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

## Section 8 — Validate Samba Configuration

```bash
testparm
sudo systemctl status smbd
sudo smbstatus
```

Expected result: no syntax errors from `testparm`, and `smbd` active/running.

---

## Section 9 — Verify Share Access

From Windows or FLARE VM:

```text
\\172.16.0.10\ingest_rw
\\172.16.0.10\evidence
\\172.16.0.10\vault
```

Validation:

```text
analyst user can write to ingest_rw and vault
analyst user cannot write to evidence
admin user can write to all three shares
```

---

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
//172.16.0.10/ingest_rw /ingest cifs credentials=/root/.smbcred,vers=3.0,ro,uid=logstash,gid=logstash,file_mode=0444,dir_mode=0555,nofail 0 0
```

Mount and validate:

```bash
sudo mount -a
ls -l /ingest
```

---

## Section 11 — Operational Guardrails

- Treat `evidence` as controlled source storage.
- Keep ELK ingest workflow against local copy (`/ingest_local`) instead of direct SMB reads.
- Use least privilege for all analyst accounts.
- Rotate Samba credentials on a defined schedule.
- Snapshot/backup NAS data before major permission changes.

---

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
getfacl /data/ingest_rw
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

## Section 14 — Final Validation Checklist

```text
[ ] NAS static IP is set to 172.16.0.10
[ ] UFW only allows SSH/SMB from 172.16.0.0/24
[ ] Samba service is active and enabled
[ ] testparm returns no Samba syntax errors
[ ] ingest_rw share is writable by analysts/admins
[ ] evidence share is read-only for analysts
[ ] evidence share is writable for admins
[ ] vault share is writable by analysts/admins
[ ] ELK VM can mount NAS ingest share
[ ] Credentials are documented in approved vault
```

---

## Appendix A — Recommended Share Mapping

```text
Analyst workstation:
  \\172.16.0.10\vault

FLARE VM:
  \\172.16.0.10\ingest_rw
  \\172.16.0.10\evidence

ELK VM:
  //172.16.0.10/ingest_rw mounted at /ingest (read-only)
```

---

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

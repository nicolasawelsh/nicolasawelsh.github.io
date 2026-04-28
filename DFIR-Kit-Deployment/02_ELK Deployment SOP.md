---
layout: default
title: "02 ELK Deployment SOP"
---

## Purpose

This SOP documents the full deployment process for a single-node ELK stack used to ingest DFIR artifact CSVs generated from tools such as EvtxECmd, Hayabusa, MFTECmd `$MFT`, and MFTECmd `$J`. The goal is to create a repeatable DFIR kit deployment that supports timeline hunting, event review, dashboarding, and multi-host artifact correlation in Kibana.

This guide is based on the working architecture validated during deployment and troubleshooting:

- Elasticsearch stores and indexes DFIR records.
- Logstash reads curated CSVs from a local ingest folder.
- Kibana provides Discover, dashboards, and analyst access.
- A NAS acts as the ingest share.
- Files are copied from the NAS into a local ingestion folder before Logstash processes them.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Supported Input Files](#supported-input-files)
- [Section 1 — Prepare Ubuntu Server](#section-1-prepare-ubuntu-server)
- [Section 2 — Online Package Install](#section-2-online-package-install)
- [Section 3 — Post ESXi Migration Configuration](#section-3-post-esxi-migration-configuration)
- [Section 4 — Configure Elasticsearch](#section-4-configure-elasticsearch)
- [Section 5 — Create Logstash Ingest User](#section-5-create-logstash-ingest-user)
- [Section 6 — Configure Kibana](#section-6-configure-kibana)
- [Section 7 — Configure NAS Mount](#section-7-configure-nas-mount)
- [Section 8 — Prepare Local Ingest Folder](#section-8-prepare-local-ingest-folder)
- [Section 9 — Configure Logstash Global Settings](#section-9-configure-logstash-global-settings)
- [Section 10 — Logstash Pipeline Configuration](#section-10-logstash-pipeline-configuration)
- [Section 11 — Validate Logstash Configuration](#section-11-validate-logstash-configuration)
- [Section 12 — Start Logstash and Ingest](#section-12-start-logstash-and-ingest)
- [Section 13 — Verify Elasticsearch Indices](#section-13-verify-elasticsearch-indices)
- [Section 14 — Rebuild Indices After Ingestion Issues](#section-14-rebuild-indices-after-ingestion-issues)
- [Section 15 — Create Kibana Data View](#section-15-create-kibana-data-view)
- [Section 16 — Create Kibana Users and Roles](#section-16-create-kibana-users-and-roles)
- [Section 17 — Testing and Troubleshooting Notes](#section-17-testing-and-troubleshooting-notes)
- [Section 18 — Standard Reingest Procedure](#section-18-standard-reingest-procedure)
- [Section 19 — Operational Workflow](#section-19-operational-workflow)
- [Section 20 — Suggested Initial Dashboards](#section-20-suggested-initial-dashboards)
- [Section 21 — Configure Firewall (UFW)](#section-21-configure-firewall-ufw)
- [Section 22 — Final Validation Checklist](#section-22-final-validation-checklist)
- [Appendix A — Timestamp Mapping](#appendix-a-timestamp-mapping)
- [Appendix B — Safe Delete and Reingest Commands](#appendix-b-safe-delete-and-reingest-commands)
- [Appendix C — Quick Health Commands](#appendix-c-quick-health-commands)
- [Appendix D — Credential Tracking Worksheet](#appendix-d-credential-tracking-worksheet)

---

<a id="architecture-overview"></a>
## Architecture Overview

```text
NAS Ingest Share
        ↓
Mounted read-only at /ingest
        ↓
Local processing copy at /ingest_local
        ↓
Logstash CSV pipeline
        ↓
Elasticsearch indices
        ↓
Kibana data views, Discover, dashboards
```

### Environment Baseline

```text
Lab CIDR: 172.16.0.0/24
NAS IP: 172.16.0.10
ELK VM (example): 172.16.0.20
Default Gateway: 172.16.0.1
```

### Key Design Decisions

1. **Do not ingest directly from the NAS.**
   Logstash file watching can behave inconsistently against SMB/CIFS mounts. The NAS should be treated as artifact storage only.

2. **Mount the NAS read-only.**
   This prevents accidental modification or deletion of source artifact files.

3. **Copy working files to `/ingest_local`.**
   Logstash reads from a local filesystem to avoid SMB file-watcher issues.

4. **Use explicit CSV column definitions.**
   Do not use global `autodetect_column_names` when ingesting multiple CSV schemas. It can cause headers from one artifact type to be applied to another, especially when it applies to Zimmerman Tool outputs.

5. **Use `event.dataset` for dataset separation.**
   The pipeline routes records to separate indices using:

```text
dfir-evtx
dfir-hayabusa
dfir-mft
dfir-usnjrnl
```

---

<a id="supported-input-files"></a>
## Supported Input Files

The SOP assumes the following filename format:

```text
<HOSTNAME>_<ARTIFACT>_Output.csv
```

Example validated files:

```text
EXAMPLE-DC_EvtxECmd_Output.csv
EXAMPLE-DC_Hayabusa_Output.csv
EXAMPLE-DC_MFTECmd_J_Output.csv
EXAMPLE-DC_MFTECmd_MFT_Output.csv
```

The hostname portion can vary, for example:

```text
DESKTOP-01
DESKTOP-02
EXAMPLE-DC
```

The artifact name must include one of the following:

```text
EvtxECmd
Hayabusa
MFTECmd_J
MFTECmd_MFT
```

---

<a id="section-1-prepare-ubuntu-server"></a>
## Section 1 — Prepare Ubuntu Server

### Recommended VM Resources

For a DFIR kit that may ingest large CSVs:

```text
CPU:      4+ vCPU
RAM:      16 GB minimum, 32 GB preferred
Disk:     1 TB recommended
OS:       Ubuntu Server 22.04 LTS or 24.04 LTS
Network:  Static IP recommended
```

---

<a id="section-2-online-package-install"></a>
## Section 2 — Online Package Install

These steps require internet access. Complete them before moving the VM into an offline/isolated ESXi environment.

Build sequence for this SOP:

1. Build the VM while internet-connected.
2. Complete package and repository installation in this section.
3. Move the VM to ESXi/lab network and complete post-move network/storage steps in `Section 3`.

If you must build offline, use an approved internal mirror/repository for Ubuntu and Elastic packages.

### Update the System and Install Baseline Prerequisites

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y apt-transport-https curl gnupg cifs-utils jq cloud-guest-utils ufw
```

### Add Elastic Repository

```bash
curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | \
  sudo gpg --dearmor -o /usr/share/keyrings/elastic.gpg

echo "deb [signed-by=/usr/share/keyrings/elastic.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | \
  sudo tee /etc/apt/sources.list.d/elastic-8.x.list

sudo apt update
```

### Install ELK

```bash
sudo apt install -y elasticsearch logstash kibana
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
        - 172.16.0.20/24
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

<a id="section-4-configure-elasticsearch"></a>
## Section 4 — Configure Elasticsearch

Edit Elasticsearch configuration:

```bash
sudo nano /etc/elasticsearch/elasticsearch.yml
```

Use this baseline single-node configuration:

```yaml
cluster.name: dfir-cluster
node.name: elk-node-1

network.host: 0.0.0.0
http.port: 9200

discovery.type: single-node
xpack.security.enabled: true
```

Start Elasticsearch:

```bash
sudo systemctl enable elasticsearch
sudo systemctl start elasticsearch
```

### Set the Elastic Password

```bash
sudo /usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic -i --url https://127.0.0.1:9200
```

### Test Elasticsearch

```bash
curl -k -u elastic https://127.0.0.1:9200
```

Expected result: JSON cluster information.

---

<a id="section-5-create-logstash-ingest-user"></a>
## Section 5 — Create Logstash Ingest User

Use a dedicated ingest user instead of the `elastic` superuser.

### Create the Role

```bash
curl -k -u elastic -X POST https://127.0.0.1:9200/_security/role/logstash_writer \
-H "Content-Type: application/json" \
-d '{
  "cluster": ["monitor"],
  "indices": [
    {
      "names": ["dfir-*"],
      "privileges": ["create_index", "write", "create", "index"]
    }
  ]
}'
```

### Create the User

Replace `YOUR_LOGSTASH_PASSWORD` with a strong password.

```bash
curl -k -u elastic -X POST https://127.0.0.1:9200/_security/user/logstash_ingest \
-H "Content-Type: application/json" \
-d '{
  "password": "YOUR_LOGSTASH_PASSWORD",
  "roles": ["logstash_writer"]
}'
```

### Test the User

```bash
curl -k -u logstash_ingest https://127.0.0.1:9200/_security/_authenticate
```

Expected result: username `logstash_ingest` with role `logstash_writer`.

---

<a id="section-6-configure-kibana"></a>
## Section 6 — Configure Kibana

Edit Kibana configuration:

```bash
sudo nano /etc/kibana/kibana.yml
```

Basic lab configuration:

```yaml
server.host: "0.0.0.0"
server.port: 5601
elasticsearch.hosts: ["https://127.0.0.1:9200"]
elasticsearch.ssl.verificationMode: none
```

Start Kibana:

```bash
sudo systemctl enable kibana
sudo systemctl start kibana
```

Access Kibana:

```text
http://<ELK-SERVER-IP>:5601
```

Log in as:

```text
Username: elastic
Password: <elastic password>
```

---

<a id="section-7-configure-nas-mount"></a>
## Section 7 — Configure NAS Mount

The NAS should be mounted read-only at `/ingest`.

### Create Mount Point

```bash
sudo mkdir -p /ingest
```

### Create SMB Credentials File

```bash
sudo nano /root/.smbcred
```

Example:

```text
username=analyst
password=YOUR_NAS_PASSWORD
```

Secure it:

```bash
sudo chmod 600 /root/.smbcred
```

### Mount the NAS Read-Only

Replace IP and share name as needed:

```bash
sudo mount -t cifs //172.16.0.10/ingest /ingest \
-o credentials=/root/.smbcred,vers=3.0,ro,uid=logstash,gid=logstash,file_mode=0444,dir_mode=0555
```

### Verify

```bash
ls -l /ingest
```

Files should appear as read-only.

### Persist Mount in `/etc/fstab`

```bash
sudo nano /etc/fstab
```

Add:

```text
//172.16.0.10/ingest /ingest cifs credentials=/root/.smbcred,vers=3.0,ro,uid=logstash,gid=logstash,file_mode=0444,dir_mode=0555 0 0
```

Test:

```bash
sudo mount -a
ls -l /ingest
```

---

<a id="section-8-prepare-local-ingest-folder"></a>
## Section 8 — Prepare Local Ingest Folder

Create a local folder that Logstash will actually read from:

```bash
sudo mkdir -p /ingest_local
sudo chown logstash:logstash /ingest_local
sudo chmod 755 /ingest_local
```

Copy CSV files from the NAS into local ingest:

```bash
sudo cp /ingest/*.csv /ingest_local/
sudo chown logstash:logstash /ingest_local/*.csv
sudo chmod 444 /ingest_local/*.csv
```

### Why Copy Instead of Reading Directly from NAS?

Logstash file input is more reliable against local filesystems. SMB/CIFS mounts can cause file discovery and sincedb tracking issues.

---

<a id="section-9-configure-logstash-global-settings"></a>
## Section 9 — Configure Logstash Global Settings

Edit:

```bash
sudo nano /etc/logstash/logstash.yml
```

Recommended settings:

```yaml
pipeline.workers: 1
pipeline.ordered: true
path.config: /etc/logstash/conf.d
http.host: 0.0.0.0
http.port: 9600
```

### Notes

- `pipeline.workers: 1` is required when `pipeline.ordered: true` is enabled.
- Ordered processing is helpful for deterministic forensic ingestion.

---

<a id="section-10-logstash-pipeline-configuration"></a>
## Section 10 — Logstash Pipeline Configuration

### Input Filename Convention (Used by This Example)

This pipeline’s dataset routing is based on the **artifact name embedded in the CSV filename**. Use the same naming convention described earlier:

```text
<HOSTNAME>_<ARTIFACT>_Output.csv
```

Examples:

```text
EXAMPLE-DC_EvtxECmd_Output.csv
EXAMPLE-DC_Hayabusa_Output.csv
EXAMPLE-DC_MFTECmd_J_Output.csv
EXAMPLE-DC_MFTECmd_MFT_Output.csv
```

If filenames don’t include those artifact strings, the regex checks won’t match and events will fall into `dfir-unknown`.

### CSV Columns (Zimmerman Tools)

In this deployment, it’s best practice to **manually define the `csv { columns => [...] }` list per artifact type** (as shown below) to match the Zimmerman tool output schemas.

Do not use a single global CSV filter with header autodetection across mixed artifact types; it can cause one artifact’s headers to be applied to another and will break field mappings and dataset separation.

Create the pipeline:

```bash
sudo nano /etc/logstash/conf.d/10-dfir.conf
```

Paste the following, replacing `YOUR_LOGSTASH_PASSWORD` with the real password for `logstash_ingest`.

```conf
input {
  file {
    path => "/ingest_local/*.csv"
    start_position => "beginning"
    sincedb_path => "/var/lib/logstash/sincedb-dfir"
    mode => "read"

    file_completed_action => "log"
    file_completed_log_path => "/var/log/logstash/ingested_files.log"
  }
}

filter {
  mutate {
    add_field => { "[source_file]" => "%{[log][file][path]}" }
  }

  ############################
  # EVTXECMD
  ############################
  if [source_file] =~ /(?i)evtxecmd/ {
    mutate { add_field => { "[event][dataset]" => "evtx" } }

    csv {
      skip_header => true
      separator => ","
      ecs_compatibility => "disabled"
      columns => [
        "RecordNumber", "EventRecordId", "TimeCreated", "EventId", "Level", "Provider",
        "Channel", "ProcessId", "ThreadId", "Computer", "ChunkNumber", "UserId",
        "MapDescription", "UserName", "RemoteHost", "PayloadData1", "PayloadData2",
        "PayloadData3", "PayloadData4", "PayloadData5", "PayloadData6",
        "ExecutableInfo", "HiddenRecord", "SourceFile", "Keywords",
        "ExtraDataOffset", "Payload"
      ]
    }

    date {
      match => ["TimeCreated", "yyyy-MM-dd HH:mm:ss.SSSSSSS", "ISO8601"]
      target => "@timestamp"
    }
  }

  ############################
  # HAYABUSA
  ############################
  else if [source_file] =~ /(?i)hayabusa/ {
    mutate { add_field => { "[event][dataset]" => "hayabusa" } }

    csv {
      skip_header => true
      separator => ","
      ecs_compatibility => "disabled"
      columns => [
        "Timestamp", "RuleTitle", "Level", "Computer", "Channel", "EventID",
        "RecordID", "Details", "ExtraFieldInfo", "RuleID"
      ]
    }

    date {
      match => ["Timestamp", "yyyy-MM-dd HH:mm:ss.SSS ZZZ", "ISO8601"]
      target => "@timestamp"
    }
  }

  ############################
  # USN JOURNAL
  ############################
  else if [source_file] =~ /(?i)mftecmd_j/ {
    mutate { add_field => { "[event][dataset]" => "usnjrnl" } }

    csv {
      skip_header => true
      separator => ","
      ecs_compatibility => "disabled"
      columns => [
        "Name", "Extension", "EntryNumber", "SequenceNumber", "ParentEntryNumber",
        "ParentSequenceNumber", "ParentPath", "UpdateSequenceNumber",
        "UpdateTimestamp", "UpdateReasons", "FileAttributes", "OffsetToData",
        "SourceFile"
      ]
    }

    date {
      match => ["UpdateTimestamp", "yyyy-MM-dd HH:mm:ss.SSSSSSS", "ISO8601"]
      target => "@timestamp"
    }
  }

  ############################
  # MFT
  ############################
  else if [source_file] =~ /(?i)mftecmd_mft/ {
    mutate { add_field => { "[event][dataset]" => "mft" } }

    csv {
      skip_header => true
      separator => ","
      ecs_compatibility => "disabled"
      columns => [
        "EntryNumber", "SequenceNumber", "InUse", "ParentEntryNumber",
        "ParentSequenceNumber", "ParentPath", "FileName", "Extension", "FileSize",
        "ReferenceCount", "ReparseTarget", "IsDirectory", "HasAds", "IsAds",
        "SI_LT_FN", "uSecZeros", "Copied", "SiFlags", "NameType",
        "Created0x10", "Created0x30", "LastModified0x10", "LastModified0x30",
        "LastRecordChange0x10", "LastRecordChange0x30", "LastAccess0x10",
        "LastAccess0x30", "UpdateSequenceNumber", "LogfileSequenceNumber",
        "SecurityId", "ObjectIdFileDroid", "LoggedUtilStream", "ZoneIdContents"
      ]
    }

    date {
      match => ["Created0x10", "yyyy-MM-dd HH:mm:ss.SSSSSSS", "ISO8601"]
      target => "@timestamp"
    }
  }

  ############################
  # FALLBACK
  ############################
  else {
    mutate {
      add_field => { "[event][dataset]" => "unknown" }
      add_tag => ["unknown_dataset"]
    }
  }

  mutate {
    remove_field => ["message"]
  }
}

output {
  elasticsearch {
    hosts => ["https://127.0.0.1:9200"]
    index => "dfir-%{[event][dataset]}"
    user => "logstash_ingest"
    password => "YOUR_LOGSTASH_PASSWORD"
    ssl_enabled => true
    ssl_verification_mode => "none"
  }

  stdout { codec => rubydebug }
}
```

---

<a id="section-11-validate-logstash-configuration"></a>
## Section 11 — Validate Logstash Configuration

Before starting or restarting Logstash, test the config:

```bash
sudo -u logstash /usr/share/logstash/bin/logstash --path.settings /etc/logstash -t
```

Expected result:

```text
Configuration OK
```

If the test fails, do not restart the service until the syntax issue is fixed.

---

<a id="section-12-start-logstash-and-ingest"></a>
## Section 12 — Start Logstash and Ingest

Prepare the completed files log:

```bash
sudo touch /var/log/logstash/ingested_files.log
sudo chown logstash:logstash /var/log/logstash/ingested_files.log
```

Clear sincedb before a fresh reingest:

```bash
sudo rm -f /var/lib/logstash/sincedb-dfir*
```

Restart Logstash:

```bash
sudo systemctl restart logstash
sudo journalctl -u logstash -f
```

### Expected Journal Output

Look for:

```text
Pipeline started
Pipelines running
```

If `stdout { codec => rubydebug }` is enabled, you should see parsed events. Confirm:

```text
source_file => /ingest_local/<filename>.csv
event.dataset => evtx | hayabusa | mft | usnjrnl
```

---

<a id="section-13-verify-elasticsearch-indices"></a>
## Section 13 — Verify Elasticsearch Indices

Check indices:

```bash
curl -k -u elastic "https://127.0.0.1:9200/_cat/indices?v"
```

Expected indices:

```text
dfir-evtx
dfir-hayabusa
dfir-mft
dfir-usnjrnl
```

Check sample document:

```bash
curl -k -u elastic "https://127.0.0.1:9200/dfir-*/_search?size=1&pretty"
```

Confirm:

```text
@timestamp exists
event.dataset is populated
source_file is populated
fields match the correct artifact type
```

---

<a id="section-14-rebuild-indices-after-ingestion-issues"></a>
## Section 14 — Rebuild Indices After Ingestion Issues

Use this procedure when parsing errors, bad mappings, or incorrect field extraction require a clean rebuild.

### When to Use This

```text
Incorrect field mappings from a previous bad ingest
Most events landing in dfir-unknown due to temporary pipeline errors
Need to reprocess the same CSV set from scratch
```

### Rebuild Procedure

```bash
sudo systemctl stop logstash
curl -k -u elastic -X DELETE "https://127.0.0.1:9200/dfir-*"
sudo rm -f /var/lib/logstash/sincedb-dfir*
sudo systemctl start logstash
sudo journalctl -u logstash -f
```

### Validate Rebuild

```bash
curl -k -u elastic "https://127.0.0.1:9200/_cat/indices?v"
curl -k -u elastic "https://127.0.0.1:9200/dfir-*/_search?size=1&pretty"
```

Expected result:

```text
dfir-evtx, dfir-hayabusa, dfir-mft, and dfir-usnjrnl are recreated
@timestamp, event.dataset, and source_file are present in sample documents
```

---

<a id="section-15-create-kibana-data-view"></a>
## Section 15 — Create Kibana Data View

In Kibana:

```text
Stack Management → Data Views → Create data view
```

Use:

```text
dfir-*
```

Timestamp field:

```text
@timestamp
```

In Discover, set time range to:

```text
Last 5 years
```

### Important Field Note

Use this field for filtering, terms, dashboards, and distinct counts:

```text
event.dataset.keyword
```

This is normal. The `.keyword` field is the exact-match version of the field and is best for aggregations and filtering.

---

<a id="section-16-create-kibana-users-and-roles"></a>
## Section 16 — Create Kibana Users and Roles

### Create DFIR Analyst Role

In Kibana:

```text
Stack Management → Roles → Create role
```

Role name:

```text
dfir_analyst
```

Index privileges:

```text
Index: dfir-*
Privileges: read, view_index_metadata
```

Kibana privileges:

```text
Discover: All
Dashboard: All
Visualize/Lens: All
Stack Management: None
Dev Tools: None
```

### Create Analyst User

```text
Stack Management → Users → Create user
```

Assign role:

```text
dfir_analyst
```

### Recommended Role Model

```text
dfir_viewer   = read-only dashboards/discover
dfir_analyst  = discover + dashboards + visualizations
dfir_admin    = management of data views, spaces, dashboards
```

---

<a id="section-17-testing-and-troubleshooting-notes"></a>
## Section 17 — Testing and Troubleshooting Notes

### Test 1 — Logstash Will Not Start

Check:

```bash
sudo journalctl -u logstash -n 100
```

Common causes:

```text
Syntax error in 10-dfir.conf
pipeline.ordered true but pipeline.workers not set to 1
misspelled plugin option such as separator
missing file_completed_log_path when file_completed_action is log
```

### Test 2 — No `dfir-*` Indices Appear

Check Logstash events for:

```text
event.dataset
source_file
```

If index error says:

```text
Badly formatted index, after interpolation still contains placeholder
```

Then `event.dataset` is missing.

Fix dataset detection or use fallback to `unknown`.

### Test 3 — Everything Goes to `dfir-unknown`

Check:

```text
source_file
```

It should show the real path:

```text
/ingest_local/EXAMPLE-DC_EvtxECmd_Output.csv
```

If it shows:

```text
%{[path]}
```

Then the config is using the wrong field. Use:

```conf
add_field => { "[source_file]" => "%{[log][file][path]}" }
```

### Test 4 — MFT Fields Look Like EVTX Fields

This means CSV headers were applied incorrectly.

Cause:

```text
A global csv filter with autodetect_column_names was used across mixed CSV schemas.
```

Fix:

```text
Use artifact-specific csv filters with explicit columns.
```

### Test 5 — Files Disappear from `/ingest`

Cause:

```text
Logstash file input in read mode can delete files if file_completed_action defaults to delete.
```

Fix:

```conf
file_completed_action => "log"
file_completed_log_path => "/var/log/logstash/ingested_files.log"
```

Also mount NAS read-only.

### Test 6 — Disk Fills Quickly

Elasticsearch expands CSV data significantly due to indexing.

If storage needs to be increased, follow [Section 3 — Post ESXi Migration Configuration](#section-3-post-esxi-migration-configuration), specifically **Resize Disk After ESXi Expansion (If Applicable)**.

Recommended:

```text
1 TB disk for DFIR kit
Delete failed test indices before reingestion
Monitor disk usage with df -h
```

Commands:

```bash
df -h
sudo du -h /var/lib/elasticsearch | sort -h | tail -n 20
```

Delete bad test indices:

```bash
curl -k -u elastic -X DELETE "https://127.0.0.1:9200/dfir-*"
```

---

<a id="section-18-standard-reingest-procedure"></a>
## Section 18 — Standard Reingest Procedure

Use this when changing Logstash mappings or CSV parsing logic.
For full troubleshooting context and validation guidance, see [Section 14 — Rebuild Indices After Ingestion Issues](#section-14-rebuild-indices-after-ingestion-issues).

```bash
sudo systemctl stop logstash
curl -k -u elastic -X DELETE "https://127.0.0.1:9200/dfir-*"
sudo rm -f /var/lib/logstash/sincedb-dfir*
sudo systemctl start logstash
sudo journalctl -u logstash -f
```

Then verify:

```bash
curl -k -u elastic "https://127.0.0.1:9200/_cat/indices?v"
```

---

<a id="section-19-operational-workflow"></a>
## Section 19 — Operational Workflow

### Normal DFIR Ingest Process

1. Place completed artifact CSVs on NAS.
2. Confirm filenames match naming convention.
3. Manually copy CSVs to `/ingest_local`.
4. Clear sincedb if reprocessing is desired.
5. Restart Logstash or start Logstash if stopped.
6. Watch journal logs.
7. Confirm `dfir-*` indices exist.
8. Open Kibana Discover.
9. Filter by `event.dataset.keyword`.
10. Build or update dashboards.

### Example Dataset Filters

```text
event.dataset.keyword : "evtx"
event.dataset.keyword : "hayabusa"
event.dataset.keyword : "mft"
event.dataset.keyword : "usnjrnl"
```

---

<a id="section-20-suggested-initial-dashboards"></a>
## Section 20 — Suggested Initial Dashboards

### Dashboard 1 — DFIR Overview

Panels:

```text
Events over time
Count by event.dataset.keyword
Count by Computer
Count by Channel
Count by Level
Top EventId values
```

### Dashboard 2 — Windows Event Review

Filters:

```text
event.dataset.keyword : "evtx"
```

Fields:

```text
@timestamp
Computer
Channel
Provider
EventId
Level
UserName
UserId
Payload
SourceFile
```

### Dashboard 3 — Hayabusa Detections

Filters:

```text
event.dataset.keyword : "hayabusa"
```

Fields:

```text
@timestamp
Computer
Level
RuleTitle
Channel
EventID
Details
RuleID
```

### Dashboard 4 — File System Timeline

Filters:

```text
event.dataset.keyword : "mft" or "usnjrnl"
```

MFT Fields:

```text
@timestamp
FileName
Extension
ParentPath
FileSize
Created0x10
Created0x30
LastModified0x10
LastModified0x30
LastRecordChange0x10
LastAccess0x10
```

USN Fields:

```text
@timestamp
Name
Extension
ParentPath
UpdateTimestamp
UpdateReasons
FileAttributes
SourceFile
```

---

<a id="section-21-configure-firewall-ufw"></a>
## Section 21 — Configure Firewall (UFW)

Restrict inbound access so SMB and ELK are reachable from `172.16.0.0/24` only.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 172.16.0.0/24 to any port 22 proto tcp
sudo ufw allow from 172.16.0.0/24 to any port 5601 proto tcp
sudo ufw allow from 172.16.0.0/24 to any port 9600 proto tcp
sudo ufw enable
sudo ufw status verbose
```

---

<a id="section-22-final-validation-checklist"></a>
## Section 22 — Final Validation Checklist

Before considering the deployment complete, verify:

```text
[ ] Elasticsearch is running
[ ] Kibana is reachable
[ ] Logstash config test passes
[ ] UFW only allows SSH/5601/9200/9600 from 172.16.0.0/24
[ ] NAS is mounted read-only at /ingest
[ ] Local ingest folder exists at /ingest_local
[ ] Files copied into /ingest_local
[ ] Logstash does not delete source files
[ ] dfir-* indices exist
[ ] event.dataset.keyword has expected values
[ ] @timestamp maps to the correct artifact timestamp
[ ] Kibana data view dfir-* exists
[ ] Analyst users can access Discover and dashboards
[ ] Bad test indices were deleted before production ingest
```

Expected final dataset values:

```text
evtx
hayabusa
mft
usnjrnl
```

---

<a id="appendix-a-timestamp-mapping"></a>
## Appendix A — Timestamp Mapping

```text
EvtxECmd     → TimeCreated
Hayabusa     → Timestamp
MFTECmd $J   → UpdateTimestamp
MFTECmd $MFT → Created0x10
```

---

<a id="appendix-b-safe-delete-and-reingest-commands"></a>
## Appendix B — Safe Delete and Reingest Commands

```bash
sudo systemctl stop logstash
curl -k -u elastic -X DELETE "https://127.0.0.1:9200/dfir-*"
sudo rm -f /var/lib/logstash/sincedb-dfir*
sudo systemctl start logstash
sudo journalctl -u logstash -f
```

---

<a id="appendix-c-quick-health-commands"></a>
## Appendix C — Quick Health Commands

```bash
sudo systemctl status elasticsearch
sudo systemctl status logstash
sudo systemctl status kibana
curl -k -u elastic "https://127.0.0.1:9200/_cat/indices?v"
curl -k -u elastic "https://127.0.0.1:9200/dfir-*/_search?size=1&pretty"
df -h
```

---

<a id="appendix-d-credential-tracking-worksheet"></a>
## Appendix D — Credential Tracking Worksheet

Use this worksheet to track all credentials required by this deployment.  
Do **not** store real passwords directly in this SOP file if it is shared; store secrets in an approved password manager/vault and record only the reference/location.

### Credentials to Track

```text
Credential Name: Elasticsearch superuser (elastic)
Used By: Kibana admin login, security API actions
Username: elastic
Password Location: <vault path / password manager entry>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
Notes: <optional>
```

```text
Credential Name: Logstash ingest user
Used By: Logstash output to Elasticsearch
Username: logstash_ingest
Password Location: <vault path / password manager entry>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
Notes: Update /etc/logstash/conf.d/10-dfir.conf after rotation
```

```text
Credential Name: NAS SMB read-only account
Used By: Mounting /ingest via CIFS
Username: <nas username>
Password Location: <vault path / password manager entry>
Local Secret File: /root/.smbcred
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
Notes: Keep mount read-only for evidence integrity
```

```text
Credential Name: Kibana analyst user(s)
Used By: Analyst login to Discover/Dashboards
Username(s): <dfir analyst account(s)>
Password Location: <vault path / password manager entry>
Set/Rotated Date: <YYYY-MM-DD>
Rotation Due: <YYYY-MM-DD>
Owner: <name/team>
Notes: Ensure least-privilege role assignment
```

### Optional Environment Tracking

```text
Kibana URL: http://<ELK-SERVER-IP>:5601
Elasticsearch URL: https://127.0.0.1:9200
NAS Share: //172.16.0.10/ingest
Credential Vault Reference: <system/name>
```
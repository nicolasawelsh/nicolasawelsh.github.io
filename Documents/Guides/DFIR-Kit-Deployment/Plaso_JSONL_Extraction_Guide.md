---
layout: default
title: "Plaso JSONL Extraction Guide"
---

# DFIR SOP — Generate Plaso JSONL Timelines from Disk Images

## Overview

This guide walks through how to:

- Mount an external forensic drive
- Install Docker and DFIR dependencies
- Run Plaso (`log2timeline`) against:
  - E01 images
  - VMware VMDK images
  - Corrupted images
- Export timelines to JSONL format for Elastic ingestion

---

# 1. Install Docker

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
```

Verify Docker:

```bash
sudo docker run hello-world
```

---

# 2. Install DFIR Utilities

```bash
sudo apt install -y ewf-tools sleuthkit
```

Tools installed:

- `ewfinfo`
- `ewfverify`
- `ewfexport`
- `mmls`
- `tsk_recover`

---

# 3. Mount External Drive

Identify the drive:

```bash
lsblk
```

Example:

```text
sdb      1.8T
└─sdb1
```

Mount read-only:

```bash
MOUNT_POINT="/mnt/external"

sudo mkdir -p $MOUNT_POINT
sudo mount -o ro /dev/sdb1 $MOUNT_POINT
```

Verify:

```bash
df -h
ls -l $MOUNT_POINT
```

---

# 4. Create Working Directories

```bash
sudo mkdir -p /data/images
sudo mkdir -p /data/images_raw
sudo mkdir -p /data/recovered
sudo mkdir -p /data/timelines

sudo chown -R $USER:$USER /data
```

---

# 5. Copy Image Locally (Recommended)

Always process locally for speed and stability.

Example:

```bash
CASE="MINSEG-DISCO2-Kioxia"

sudo cp -r "$MOUNT_POINT/$CASE" /data/images/
```

---

# 6. Workflow Selection

## Normal Images

Use directly:

- `.E01`
- `.vmdk`

## Corrupted Images

Use:

1. `ewfverify`
2. `ewfexport`
3. `tsk_recover`

---

# 7. Processing Standard E01 Images

## Variables

```bash
CASE="MINSEG-Recepcion"
IMAGE_NAME="Recepcion"
WORKERS=14
```

---

## Run Plaso

```bash
sudo mkdir -p /data/timelines/$CASE

sudo docker run --rm -it \
  -v /data/images:/evidence:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers $WORKERS \
  --partitions all \
  --storage_file "/output/$CASE/$IMAGE_NAME.plaso" \
  "/evidence/$CASE/$IMAGE_NAME.E01"
```

---

## Convert to JSONL

```bash
sudo docker run --rm -it \
  -v /data/timelines:/data \
  log2timeline/plaso \
  psort.py \
  -o json_line \
  -w "/data/$CASE/$IMAGE_NAME.jsonl" \
  "/data/$CASE/$IMAGE_NAME.plaso"
```

---

# 8. Processing VMware VMDK Images

## Variables

```bash
CASE="DSKTP-CONS-GHOU-clone"
IMAGE_NAME="DSKTP-CONS-GHOU-clone"
WORKERS=14
```

---

## Identify Partitions

```bash
mmls "/data/images/$CASE/${IMAGE_NAME}_1.vmdk"
```

Example output:

```text
007: 003 0001159168 0208638792 Basic data partition
```

Main Windows partition:

```bash
p3
```

---

## Run Plaso

```bash
sudo mkdir -p /data/timelines/$CASE

sudo docker run --rm -it \
  -v /data/images:/evidence:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers $WORKERS \
  --partitions p3 \
  --storage_file "/output/$CASE/$IMAGE_NAME.plaso" \
  "/evidence/$CASE/${IMAGE_NAME}_1.vmdk"
```

---

## Convert to JSONL

```bash
sudo docker run --rm -it \
  -v /data/timelines:/data \
  log2timeline/plaso \
  psort.py \
  -o json_line \
  -w "/data/$CASE/$IMAGE_NAME.jsonl" \
  "/data/$CASE/$IMAGE_NAME.plaso"
```

---

# 9. Processing Corrupted E01 Images

## Verify Corruption

```bash
CASE="MINSEG-DISCO2-Kioxia"
IMAGE_NAME="DISCO2-Kioxia"
```

```bash
ewfinfo "/data/images/$CASE/$IMAGE_NAME.E01"
ewfverify "/data/images/$CASE/$IMAGE_NAME.E01"
```

If corrupted:

```text
Is corrupted: yes
```

Continue with recovery workflow.

---

# 10. Convert Corrupted E01 to RAW

```bash
sudo mkdir -p /data/images_raw/$CASE

sudo ewfexport \
  -t /data/images_raw/$CASE/$IMAGE_NAME \
  -f raw \
  -S 0 \
  "/data/images/$CASE/$IMAGE_NAME.E01"
```

This skips unreadable sectors.

Output:

```text
/data/images_raw/$CASE/$IMAGE_NAME.raw
```

---

# 11. Identify Main Partition

```bash
mmls "/data/images_raw/$CASE/$IMAGE_NAME.raw"
```

Example:

```text
006: 002 0001255424 0995198975 Basic data partition
```

Start sector:

```bash
START_SECTOR=1255424
```

---

# 12. Recover Logical Filesystem

```bash
sudo mkdir -p "/data/recovered/$CASE"

sudo tsk_recover -e \
  -o $START_SECTOR \
  "/data/images_raw/$CASE/$IMAGE_NAME.raw" \
  "/data/recovered/$CASE"
```

---

# 13. Run Plaso on Recovered Files

```bash
sudo mkdir -p /data/timelines/$CASE

sudo docker run --rm -it \
  -v /data/recovered:/recovered:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers $WORKERS \
  --storage_file "/output/$CASE/$IMAGE_NAME-logical.plaso" \
  "/recovered/$CASE"
```

---

# 14. Convert Corrupted Recovery to JSONL

```bash
sudo docker run --rm -it \
  -v /data/timelines:/data \
  log2timeline/plaso \
  psort.py \
  -o json_line \
  -w "/data/$CASE/$IMAGE_NAME-logical.jsonl" \
  "/data/$CASE/$IMAGE_NAME-logical.plaso"
```

---

# 15. Verify Output

```bash
ls -lh /data/timelines/$CASE
```

Preview:

```bash
head -n 3 /data/timelines/$CASE/*.jsonl
```

---

# 16. Common Issues

## GPT Backup Header Errors

Example:

```text
unable to read backup partition table header
```

Fix:

- Use `mmls`
- Target main partition with `--partitions p3`

---

## Corrupted E01 Chunk Errors

Example:

```text
missing chunk data
```

Fix:

- Convert to RAW with `ewfexport -S 0`

---

## JSONL Export Failure

Incorrect:

```bash
> output.jsonl
```

Correct:

```bash
-w output.jsonl
```

---

# 17. Recommended Performance Settings

Host System Example:

- i9-13900K
- 64 GB RAM

Recommended VM:

- 14 vCPU
- 36 GB RAM

Recommended Plaso:

```bash
--workers 12-14
```

Always process images from local SSD storage.

---

# 18. Cleanup

```bash
sudo rm -rf /data/images/$CASE
sudo rm -rf /data/images_raw/$CASE
sudo rm -rf /data/recovered/$CASE
```

---

# 19. Final Output

You should now have:

```text
/data/timelines/<CASE>/<IMAGE>.jsonl
```

This JSONL output is ready for:

- Elastic ingestion
- Logstash pipelines
- Kibana analysis
- Timeline correlation
- ES|QL hunting

---

## DFIR kit guides

- [Overview](./index)
- [07 Artifact carving](./07_Artifact-Carving)
- [05 ELK deployment](./05_ELK-Deployment)

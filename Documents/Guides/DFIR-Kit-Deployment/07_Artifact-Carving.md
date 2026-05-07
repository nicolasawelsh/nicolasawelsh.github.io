---
layout: default
title: "07 Artifact Carving"
---

## Purpose

This SOP describes how to **extract and normalize** common DFIR artifacts from a mounted Windows disk image or live evidence mount on a **FLARE** analysis VM, using output filenames aligned with **[05 ELK deployment](./05_ELK-Deployment)** so CSV and JSONL exports ingest without renaming logic changes.

**KAPE** (Kroll Artifact Parser and Extractor) can automate **most** of this workflow—targets and modules can collect EVTX, run Zimmerman tools, invoke Hayabusa, and stage outputs in batch. **This guide documents each underlying tool on its own** so you understand sources, switches, and the **exact filenames** the ELK pipeline expects, whether you run commands manually, script them, or wrap them in KAPE (you may still need to **rename** KAPE outputs to match **`DESKTOP-EXAMPLE_*`** conventions).

All examples use host **`DESKTOP-EXAMPLE`**. Replace it with the real computer name when it materially differs from your evidence.

### Outputs expected by the ELK pipeline

| Tool | Example output filename |
|------|-------------------------|
| EvtxECmd | `DESKTOP-EXAMPLE_EvtxECmd_Output.csv` |
| Hayabusa | `DESKTOP-EXAMPLE_Hayabusa_Output.csv` |
| MFTECmd (`$MFT`) | `DESKTOP-EXAMPLE_MFTECmd_MFT_Output.csv` |
| MFTECmd (`$J`) | `DESKTOP-EXAMPLE_MFTECmd_J_Output.csv` |
| Plaso (`psort.py` `json_line`) | `DESKTOP-EXAMPLE_plaso_Output.jsonl` |

Stage finished files on the **NAS ingest share** (then copy into **`/ingest_local`** on the ELK host per the ELK guide).

---

## Prerequisites

- **[06 Flare VM build](./06_Flare-VM-Build)** completed with **Eric Zimmerman** forensic tools, **Hayabusa**, and sufficient disk space for exports.
- Evidence available as a **mounted volume** (e.g. `E:\` from FTK/Arsenal/image mounter) or extracted filesystem paths.
- For **Plaso JSONL** on Windows, either **Docker Desktop** on FLARE or a **Linux helper VM** with Docker (see [Plaso supertimeline (JSONL)](#plaso-supertimeline-jsonl)).

---

## EvtxECmd (Windows event logs)

### Source paths

Typical EVTX directory on a Windows system partition:

```text
<drive>:\Windows\System32\winevt\Logs\
```

### Export

From a command prompt **on FLARE**, with EvtxECmd on `PATH` (adjust paths):

```text
mkdir D:\staging\DESKTOP-EXAMPLE\evtx_csv

EvtxECmd.exe -d "E:\Windows\System32\winevt\Logs" --csv "D:\staging\DESKTOP-EXAMPLE\evtx_csv"
```

Directory mode writes **one CSV per `.evtx` file**. The ELK pipeline expects a **single** consolidated CSV named **`DESKTOP-EXAMPLE_EvtxECmd_Output.csv`** with the standard EvtxECmd column layout.

**Consolidate** EVTX CSVs that share the same header (same EvtxECmd version/options), for example with PowerShell (run from `evtx_csv`):

```text
$out = "D:\staging\DESKTOP-EXAMPLE\DESKTOP-EXAMPLE_EvtxECmd_Output.csv"
$files = Get-ChildItem -Filter *.csv | Sort-Object Name
$header = Get-Content $files[0].FullName -TotalCount 1
Set-Content -Path $out -Value $header -Encoding UTF8
foreach ($f in $files) {
  Get-Content $f.FullName | Select-Object -Skip 1 | Add-Content -Path $out -Encoding UTF8
}
```

If consolidation is not practical (mixed schemas), split by channel or re-export with consistent options—**do not** mix incompatible column sets into one file.

---

## Hayabusa (sigma-style rules, full coverage)

Hayabusa ships with a large **sigma-compatible** ruleset. **Refresh rules before each case or major run** so detections match current community coverage.

### Update rules (required before major runs)

```text
hayabusa.exe update-rules
```

Confirm the rules directory updated without errors. If your environment blocks outbound downloads, sync rules through an approved mirror and place them in the expected Hayabusa `rules` folder per Hayabusa documentation.

### Timeline export (all sigma-style rule levels)

Hayabusa **3.x** renamed several subcommands—run **`hayabusa.exe help`** on your FLARE install and use the subcommand that produces a **CSV timeline** (often still documented as **`csv-timeline`** on **2.x** builds).

Example (**Hayabusa 2.x** style):

```text
mkdir D:\staging\DESKTOP-EXAMPLE

hayabusa.exe csv-timeline -d "E:\Windows\System32\winevt\Logs" -o "D:\staging\DESKTOP-EXAMPLE\DESKTOP-EXAMPLE_Hayabusa_Output.csv" -m informational
```

**`-m informational`** uses the **lowest / broadest** severity threshold so runs include **informational** through **critical** hits across the **updated** sigma-compatible rule packs—i.e. coverage across the full shipped rule set (subject to Hayabusa’s rule taxonomy). If your build lists different level strings, pick the minimum level that still includes **informational** events.

Optional performance tuning (threads, low-memory mode) varies by version—see **`hayabusa.exe help`** for your build.

---

## MFTECmd (`$MFT` and `$J`)

Mount the volume that contains the NTFS filesystem (often the OS partition). Paths below assume the filesystem root is **`E:\`**.

### `$MFT` (Master File Table)

MFTECmd expects the **`$MFT`** file at the NTFS root:

```text
mkdir D:\staging\DESKTOP-EXAMPLE\mft

MFTECmd.exe -f "E:\$MFT" --csv "D:\staging\DESKTOP-EXAMPLE\mft" --csvf DESKTOP-EXAMPLE_MFTECmd_MFT_Output.csv
```

If `--csvf` is unsupported in your build, allow MFTECmd to emit its default name and **rename** the resulting CSV to **`DESKTOP-EXAMPLE_MFTECmd_MFT_Output.csv`**.

### `$J` (USN Journal)

```text
mkdir D:\staging\DESKTOP-EXAMPLE\usnj

MFTECmd.exe -f "E:\$Extend\$J" --csv "D:\staging\DESKTOP-EXAMPLE\usnj" --csvf DESKTOP-EXAMPLE_MFTECmd_J_Output.csv
```

Some images expose **`$J`** under **`E:\$Extend\$J`**. If absent (trimmed collection), document that the USN journal was not available.

---

## Plaso supertimeline (JSONL)

Plaso produces a **storage file** (`.plaso`) via **`log2timeline.py`**, then a **JSON Lines** supertimeline suitable for ELK using **`psort.py`** with **`-o json_line`**. The ELK stack expects:

```text
DESKTOP-EXAMPLE_plaso_Output.jsonl
```

Use the **`log2timeline/plaso`** Docker image with evidence under **`/data`**, **`CASE=DESKTOP-EXAMPLE`**, and **`IMAGE_NAME`** matching your disk image basename. Run on **Linux with Docker** (helper VM or workstation) if you do not use Docker on FLARE.

### 1. Install Docker and DFIR helpers (Linux)

```bash
sudo apt update
sudo apt install -y docker.io ewf-tools sleuthkit
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

### 2. Layout and copy evidence

```bash
sudo mkdir -p /data/images /data/images_raw /data/recovered /data/timelines
sudo chown -R "$USER:$USER" /data
```

Copy disk images onto **local SSD** under **`/data/images/DESKTOP-EXAMPLE/`** (better performance than processing across SMB). If evidence arrives on an external drive, mount it **read-only**, then **`cp`** into `/data/images/` as below.

Optional — mount external evidence and copy:

```bash
MOUNT_POINT="/mnt/external"
sudo mkdir -p "$MOUNT_POINT"
sudo mount -o ro /dev/sdX1 "$MOUNT_POINT"   # replace sdX1 with your device (lsblk)
sudo mkdir -p /data/images/DESKTOP-EXAMPLE
sudo cp -r "$MOUNT_POINT/<case_folder>"/* /data/images/DESKTOP-EXAMPLE/
sudo chown -R "$USER:$USER" /data/images/DESKTOP-EXAMPLE
```

### 3. Standard E01 — create `.plaso` storage file

Set **`CASE`**, **`IMAGE_NAME`** (basename of the `.E01` without extension), and **`WORKERS`** (often **12–14** on a large Linux helper VM; scale down on smaller hosts).

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"
WORKERS=12

sudo mkdir -p "/data/timelines/$CASE"

sudo docker run --rm -it \
  -v /data/images:/evidence:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers "$WORKERS" \
  --partitions all \
  --storage_file "/output/$CASE/$IMAGE_NAME.plaso" \
  "/evidence/$CASE/${IMAGE_NAME}.E01"
```

### 4. VMware VMDK — pick partition with `mmls`

Identify the Windows volume (example uses `p3`; yours may differ):

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"
WORKERS=12

mmls "/data/images/$CASE/${IMAGE_NAME}_1.vmdk"
```

Run **`log2timeline.py`** with **`--partitions pN`** (not **`all`**) against the flat VMDK path your evidence uses:

```bash
sudo mkdir -p "/data/timelines/$CASE"

sudo docker run --rm -it \
  -v /data/images:/evidence:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers "$WORKERS" \
  --partitions p3 \
  --storage_file "/output/$CASE/$IMAGE_NAME.plaso" \
  "/evidence/$CASE/${IMAGE_NAME}_1.vmdk"
```

### 5. Corrupted E01 — export RAW, recover files, then Plaso

Verify:

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"

ewfinfo "/data/images/$CASE/$IMAGE_NAME.E01"
ewfverify "/data/images/$CASE/$IMAGE_NAME.E01"
```

Export RAW skipping unreadable sectors:

```bash
sudo mkdir -p "/data/images_raw/$CASE"

sudo ewfexport \
  -t "/data/images_raw/$CASE/$IMAGE_NAME" \
  -f raw \
  -S 0 \
  "/data/images/$CASE/$IMAGE_NAME.E01"
```

Find the NTFS start sector with **`mmls`** on the **`.raw`** file, then recover with **`tsk_recover`**:

```bash
mmls "/data/images_raw/$CASE/$IMAGE_NAME.raw"
# Note START_SECTOR for the main partition (example):
START_SECTOR=1255424

sudo mkdir -p "/data/recovered/$CASE"

sudo tsk_recover -e \
  -o $START_SECTOR \
  "/data/images_raw/$CASE/$IMAGE_NAME.raw" \
  "/data/recovered/$CASE"
```

Run Plaso against the recovered directory:

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"
WORKERS=12

sudo mkdir -p "/data/timelines/$CASE"

sudo docker run --rm -it \
  -v /data/recovered:/recovered:ro \
  -v /data/timelines:/output \
  log2timeline/plaso \
  log2timeline.py \
  --status_view window \
  --workers "$WORKERS" \
  --storage_file "/output/$CASE/$IMAGE_NAME-logical.plaso" \
  "/recovered/$CASE"
```

### 6. Export JSONL for Elastic (`psort.py`)

From any **`.plaso`** produced above, write **one JSON Lines** file for ELK using **`-w`** (never shell **`>`** redirection):

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"

sudo docker run --rm -it \
  -v /data/timelines:/data \
  log2timeline/plaso \
  psort.py \
  -o json_line \
  -w "/data/$CASE/${CASE}_plaso_Output.jsonl" \
  "/data/$CASE/$IMAGE_NAME.plaso"
```

If you used the **corrupted-image** path, run **`psort.py`** against **`$IMAGE_NAME-logical.plaso`**:

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"

sudo docker run --rm -it \
  -v /data/timelines:/data \
  log2timeline/plaso \
  psort.py \
  -o json_line \
  -w "/data/$CASE/${CASE}_plaso_Output.jsonl" \
  "/data/$CASE/$IMAGE_NAME-logical.plaso"
```

Use **`-w`** (not **`> outfile.jsonl`**)—redirecting stdout breaks JSONL line boundaries for Elasticsearch.

### 7. Verify, troubleshooting, performance, cleanup

```bash
ls -lh "/data/timelines/DESKTOP-EXAMPLE/"
head -n 2 "/data/timelines/DESKTOP-EXAMPLE/DESKTOP-EXAMPLE_plaso_Output.jsonl"
```

Copy **`DESKTOP-EXAMPLE_plaso_Output.jsonl`** to the NAS ingest share.

**Common issues**

```text
unable to read backup partition table header  → use mmls; target Windows partition with --partitions pN
missing chunk data / corrupted E01             → ewfexport -S 0, then recovery workflow above
JSONL empty or malformed in Elastic → ensure psort uses -w path, not shell redirect
```

**Performance:** Prefer **local SSD**, **`--workers`** in the **12–14** range on capable hosts, smaller **`WORKERS`** on constrained VMs.

**Cleanup** (after you have archived outputs):

```bash
CASE="DESKTOP-EXAMPLE"
sudo rm -rf "/data/images/$CASE" "/data/images_raw/$CASE" "/data/recovered/$CASE"
```

---

## Package for NAS / ELK

1. Place **`DESKTOP-EXAMPLE_*.csv`** and **`DESKTOP-EXAMPLE_plaso_Output.jsonl`** on the NAS **`ingest`** share (read-only for analysts).
2. On the ELK server, copy into **`/ingest_local`** per **[05 ELK deployment](./05_ELK-Deployment)** and restart or rely on Logstash file discovery.
3. In Kibana, filter **`event.dataset.keyword`** including **`plaso`** when the supertimeline is loaded.

---

## DFIR kit guides

- [Overview](./index)
- [01 Introduction](./01_Introduction)
- [02 Limitations](./02_Limitations)
- [03 ESXi deployment](./03_ESXi-Deployment)
- [04 NAS deployment](./04_NAS-Deployment)
- [05 ELK deployment](./05_ELK-Deployment)
- [06 Flare VM build](./06_Flare-VM-Build)
- [07 Artifact carving](./07_Artifact-Carving)
- [08 Suggestions](./08_Suggestions)

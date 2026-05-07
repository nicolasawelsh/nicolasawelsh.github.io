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

```batch
mkdir D:\staging\DESKTOP-EXAMPLE\evtx_csv

EvtxECmd.exe -d "E:\Windows\System32\winevt\Logs" --csv "D:\staging\DESKTOP-EXAMPLE\evtx_csv"
```

Directory mode writes **one CSV per `.evtx` file**. The ELK pipeline expects a **single** consolidated CSV named **`DESKTOP-EXAMPLE_EvtxECmd_Output.csv`** with the standard EvtxECmd column layout.

**Consolidate** EVTX CSVs that share the same header (same EvtxECmd version/options), for example with PowerShell (run from `evtx_csv`):

```powershell
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

```batch
hayabusa.exe update-rules
```

Confirm the rules directory updated without errors. If your environment blocks outbound downloads, sync rules through an approved mirror and place them in the expected Hayabusa `rules` folder per Hayabusa documentation.

### Timeline export (all sigma-style rule levels)

Hayabusa **3.x** renamed several subcommands—run **`hayabusa.exe help`** on your FLARE install and use the subcommand that produces a **CSV timeline** (often still documented as **`csv-timeline`** on **2.x** builds).

Example (**Hayabusa 2.x** style):

```batch
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

```batch
mkdir D:\staging\DESKTOP-EXAMPLE\mft

MFTECmd.exe -f "E:\$MFT" --csv "D:\staging\DESKTOP-EXAMPLE\mft" --csvf DESKTOP-EXAMPLE_MFTECmd_MFT_Output.csv
```

If `--csvf` is unsupported in your build, allow MFTECmd to emit its default name and **rename** the resulting CSV to **`DESKTOP-EXAMPLE_MFTECmd_MFT_Output.csv`**.

### `$J` (USN Journal)

```batch
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

The following adapts the **Plaso JSONL extraction workflow** (Docker-based `log2timeline/plaso` image, local evidence under `/data`, variable **`CASE=DESKTOP-EXAMPLE`**). Run these steps on **Linux with Docker** if you do not use Docker on FLARE.

### 1. Install Docker and DFIR helpers (Linux)

```bash
sudo apt update
sudo apt install -y docker.io ewf-tools sleuthkit
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

### 2. Layout and copy evidence

```bash
sudo mkdir -p /data/images /data/timelines
sudo chown -R "$USER:$USER" /data
```

Copy the disk image (E01, VMDK, etc.) into `/data/images/DESKTOP-EXAMPLE/` on the processing host.

### 3. Create Plaso storage file

Example for a single evidence file inside the case folder (adjust `IMAGE_NAME` and extension):

```bash
CASE="DESKTOP-EXAMPLE"
IMAGE_NAME="SYSTEM"
WORKERS=8

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

For **VMDK** images, identify the Windows partition with **`mmls`** and pass **`--partitions pN`** instead of **`all`**. For **corrupted E01**, follow **`ewfexport`** + **`tsk_recover`** recovery steps in the detailed Plaso guide before running **`log2timeline.py`** against recovered files.

### 4. Export JSONL for Elastic

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

Use **`-w`** (not shell redirection **`>`**)—redirecting stdout breaks JSONL formatting for Elasticsearch.

### 5. Verify

```bash
ls -lh "/data/timelines/DESKTOP-EXAMPLE/"
head -n 2 "/data/timelines/DESKTOP-EXAMPLE/DESKTOP-EXAMPLE_plaso_Output.jsonl"
```

Copy **`DESKTOP-EXAMPLE_plaso_Output.jsonl`** to the NAS ingest share for ELK ingestion.

### Reference — full Plaso JSONL guide

For **corrupted E01 handling**, **VMDK partition selection**, **`tsk_recover` workflows**, **performance tuning**, and **cleanup**, follow **[Plaso JSONL extraction guide](./Plaso_JSONL_Extraction_Guide)** (canonical lab supplement). Use **`CASE=DESKTOP-EXAMPLE`** and rename the final **`.jsonl`** to **`DESKTOP-EXAMPLE_plaso_Output.jsonl`** so it matches the ELK pipeline.

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

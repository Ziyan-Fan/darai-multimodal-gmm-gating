# Special_Project Reproduction Guide (For Graders)

This guide explains how to reproduce the Dynamic GMM privacy-gating experiment after unzipping the `Special_Project` folder.

## 1) Change into the project directory

```bash
cd /path/to/Special_Project
pwd
```

Expected top-level folders:
- `darai_raw_zips/`
- `notebooks/`
- `scripts/`
- `results/`

## 2) Prerequisites

Required:
- Python 3.10+ (or compatible with your environment)
- Jupyter notebook support in VS Code
- `unzip` available on system PATH

Python packages used by the notebook include:
- `numpy`, `pandas`, `matplotlib`, `seaborn`
- `scikit-learn`, `Pillow`, `ipywidgets`

If needed:

```bash
pip install numpy pandas matplotlib seaborn scikit-learn pillow ipywidgets
```

## 3) Unzip DARai raw archives

From the project root:

```bash
bash scripts/unzip_darai.sh --clean
```

Default extraction output is:
- `/tmp/${USER}_darai`

You can override input/output paths:

```bash
bash scripts/unzip_darai.sh --zip-dir /your/zip/folder --out-dir /your/output/folder --clean
```

## 4) Open the experiment notebook

Notebook to run:
- `notebooks/FunML_Privacy_Gating_Experiment.ipynb`

## 5) Update path variables in the first main Python setup cell

In the notebook, locate the setup cell that defines:
- `PROJECT_ROOT`
- `RESULTS_DIR`
- `RAW_ZIP_DIR`
- `DATA_ROOT`
- `RGB_ROOT`

The shared version includes machine-specific absolute paths. Replace them for your machine.

Recommended replacement:

```python
from pathlib import Path
import os

# Works whether you launch notebook from project root or notebooks/
cwd = Path.cwd().resolve()
PROJECT_ROOT = cwd.parent if cwd.name == 'notebooks' else cwd

RESULTS_DIR = PROJECT_ROOT / 'results'
EVAL_CSV = RESULTS_DIR / 'eval_df_for_audit.csv'
AUDIT_CSV = RESULTS_DIR / 'rgb_gate_open_audit_sheet.csv'
RAW_ZIP_DIR = PROJECT_ROOT / 'darai_raw_zips'
DATA_ROOT = Path(f"/tmp/{os.environ.get('USER', 'user')}_darai")

# Set this to the DARai RGB-compressed dataset location on your machine
RGB_ROOT = Path('/absolute/path/to/DARai/RGB_compressed')
```

Important:
- `RAW_ZIP_DIR` must point to the folder containing DARai zip files.
- `DATA_ROOT` must match the extraction location used in Step 3.
- `RGB_ROOT` must point to the real RGB frame directory tree (`.../RGB_compressed`).

## 6) Rebuild evaluation table from raw data

In the same setup cell, keep:

```python
FORCE_REBUILD_FROM_RAW = True
```

Then run cells in order from top to bottom.

What this does:
- Unzips/uses extracted raw CSV streams
- Builds fused IMU + BioMonitor window table
- Writes `results/eval_df_for_audit.csv`

## 7) Run full experiment pipeline

Run the remaining cells sequentially. The notebook will:
- Train/calibrate Dynamic GMM gating
- Compare baselines (always-open, sensor-only alerting, heuristic)
- Produce fairness and LOSO diagnostics
- Export figures and inference artifacts

Primary outputs:
- `results/gmm_inference_results.csv`
- `results/figures/*.png`
- `results/figures/*.pdf`

## 8) RGB verification audit (dedicated notebook)

After generating `results/gmm_inference_results.csv` from the main experiment notebook, run:
- `notebooks/FunML_RGB_Verification_Audit.ipynb`

This notebook validates gate-open decisions against RGB labels and reports:
- Hazard Recall (Safety)
- Verified Precision
- False-Open Rate (Wrongful Suspicion)
- Sensor-Video Agreement (Cohen's Kappa)

### Path variables to verify in the audit notebook

In the first setup cell of the audit notebook, confirm:
- `PROJECT_ROOT` points to your unzipped `Special_Project` directory
- `RESULTS_DIR = PROJECT_ROOT / 'results'`
- `INFERENCE_CSV = RESULTS_DIR / 'gmm_inference_results.csv'`

Recommended machine-portable replacement:

```python
from pathlib import Path

cwd = Path.cwd().resolve()
PROJECT_ROOT = cwd.parent if cwd.name == 'notebooks' else cwd
RESULTS_DIR = PROJECT_ROOT / 'results'
INFERENCE_CSV = RESULTS_DIR / 'gmm_inference_results.csv'
```

### What graders should expect

After running all cells in the audit notebook:
- A metrics table is displayed with recall/precision/false-open/kappa values.
- A false-open activity chart is shown when false opens exist.
- A manual-review sampler displays representative false-open events and associated RGB frames (if frame paths exist on disk).

If you get `Missing .../gmm_inference_results.csv`, rerun the main experiment notebook first (Step 7).

## 9) Common path issues and fixes

If you see "Missing required file: eval_df_for_audit.csv":
- Ensure Step 6 setup paths are correct.
- Ensure `FORCE_REBUILD_FROM_RAW = True` and rerun from top.

If RGB coverage is zero or missing:
- Verify `RGB_ROOT` points to the correct dataset location.
- Confirm expected activity subfolders exist under `RGB_ROOT`.

If unzip finds no archives:
- Confirm zip files are present in `darai_raw_zips/` or pass `--zip-dir`.

## 10) Optional: build runtime summary table from Slurm

If you have valid Slurm job IDs in `results/experiment_job_manifest.csv`:

```bash
python scripts/build_runtime_table_from_slurm.py \
  --manifest results/experiment_job_manifest.csv \
  --output-csv results/experiment_runtime_log.csv \
  --output-tex results/experiment_runtime_log.tex
```

This step is optional for reproducing the notebook gating results.

---

If reproducing on a new machine, the three critical values to verify are:
1. `PROJECT_ROOT`
2. `DATA_ROOT`
3. `RGB_ROOT`

#!/usr/bin/env python3
"""Build runtime summary table from Slurm accounting logs.

Usage:
    python scripts/build_runtime_table_from_slurm.py \
        --manifest results/experiment_job_manifest.csv \
        --output-csv results/experiment_runtime_log.csv \
        --output-tex results/experiment_runtime_log.tex

Manifest CSV columns:
    experiment,description,job_id
Optional columns:
    notes,device_override
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass
class SlurmRecord:
    state: str
    elapsed_raw: int
    start: str
    end: str
    alloc_tres: str
    req_tres: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="CSV with experiment/job_id mapping")
    parser.add_argument("--output-csv", required=True, help="Output runtime CSV path")
    parser.add_argument("--output-tex", required=True, help="Output LaTeX table path")
    parser.add_argument(
        "--default-device",
        default="N/A",
        help="Fallback device label when GPU model cannot be inferred",
    )
    parser.add_argument(
        "--sacct-bin",
        default="sacct",
        help="Path to sacct binary (default: sacct)",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    required = {"experiment", "description", "job_id"}
    missing = required - set(rows[0].keys() if rows else set())
    if missing:
        raise ValueError(f"Manifest missing required columns: {sorted(missing)}")

    cleaned: List[Dict[str, str]] = []
    for row in rows:
        if not row.get("job_id", "").strip():
            # Skip placeholder rows until job IDs are available.
            continue
        cleaned.append({k: (v or "").strip() for k, v in row.items()})

    if not cleaned:
        raise ValueError("Manifest contains no rows with a non-empty job_id")
    return cleaned


def _run_sacct(job_ids: Iterable[str], sacct_bin: str) -> str:
    fields = "JobIDRaw,State,ElapsedRaw,Start,End,AllocTRES,ReqTRES"
    cmd = [
        sacct_bin,
        "-P",
        "-n",
        "-X",
        "--format",
        fields,
        "-j",
        ",".join(job_ids),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def load_slurm_records(job_ids: Iterable[str], sacct_bin: str) -> Dict[str, SlurmRecord]:
    raw = _run_sacct(job_ids, sacct_bin)
    records: Dict[str, SlurmRecord] = {}

    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) < 7:
            continue

        job_id_raw = parts[0].strip()
        # With -X and JobIDRaw this should already be the parent ID.
        job_id = job_id_raw.split(".")[0]
        if not job_id:
            continue

        elapsed_raw_str = parts[2].strip()
        try:
            elapsed_raw = int(elapsed_raw_str)
        except ValueError:
            elapsed_raw = 0

        records[job_id] = SlurmRecord(
            state=parts[1].strip(),
            elapsed_raw=elapsed_raw,
            start=parts[3].strip(),
            end=parts[4].strip(),
            alloc_tres=parts[5].strip(),
            req_tres=parts[6].strip(),
        )

    return records


def _normalize_gpu_model(model_token: str) -> str:
    token = model_token.strip().lower().replace("nvidia_", "").replace("nvidia-", "")
    mapping = {
        "h100": "NVIDIA H100",
        "h200": "NVIDIA H200",
        "a100": "NVIDIA A100",
        "v100": "Tesla V100",
        "rtx4090": "NVIDIA RTX 4090",
        "l40s": "NVIDIA L40S",
    }
    return mapping.get(token, f"NVIDIA {token.upper()}")


def infer_device(record: SlurmRecord, default_device: str) -> str:
    combined = f"{record.req_tres},{record.alloc_tres}"

    # Examples: gpu:h100:1, gres/gpu:h100=1
    for pattern in (r"gpu:([a-zA-Z0-9_-]+):\d+", r"gres/gpu:([a-zA-Z0-9_-]+)=\d+"):
        match = re.search(pattern, combined)
        if match:
            return _normalize_gpu_model(match.group(1))

    if "gpu" in combined.lower():
        return "NVIDIA GPU"
    return default_device


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\\textbackslash{}",
        "&": r"\\&",
        "%": r"\\%",
        "$": r"\\$",
        "#": r"\\#",
        "_": r"\\_",
        "{": r"\\{",
        "}": r"\\}",
        "~": r"\\textasciitilde{}",
        "^": r"\\textasciicircum{}",
    }
    out = value
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    columns = ["experiment", "description", "device", "hours", "started_at", "ended_at", "notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_latex(path: Path, rows: List[Dict[str, str]]) -> None:
    lines = [
        r"\begin{tabular}{lllr}",
        r"\toprule",
        r"experiment & description & device & hours \\",
        r"\midrule",
    ]

    for row in rows:
        lines.append(
            "{} & {} & {} & {} \\\\".format(
                latex_escape(row["experiment"]),
                latex_escape(row["description"]),
                latex_escape(row["device"]),
                f"{float(row['hours']):.3f}",
            )
        )

    lines.extend([r"\bottomrule", r"\end{tabular}"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_rows(
    manifest_rows: List[Dict[str, str]],
    slurm_records: Dict[str, SlurmRecord],
    default_device: str,
) -> List[Dict[str, str]]:
    out_rows: List[Dict[str, str]] = []

    for row in manifest_rows:
        job_id = row["job_id"]
        rec = slurm_records.get(job_id)
        if rec is None:
            notes = row.get("notes", "")
            notes = f"{notes}; sacct row not found for job_id={job_id}".strip("; ")
            out_rows.append(
                {
                    "experiment": row["experiment"],
                    "description": row["description"],
                    "device": row.get("device_override", "") or default_device,
                    "hours": "0.0",
                    "started_at": "",
                    "ended_at": "",
                    "notes": notes,
                }
            )
            continue

        device = row.get("device_override", "") or infer_device(rec, default_device)
        notes = row.get("notes", "")
        if rec.state and rec.state not in {"COMPLETED", "COMPLETING"}:
            notes = f"{notes}; state={rec.state}".strip("; ")

        out_rows.append(
            {
                "experiment": row["experiment"],
                "description": row["description"],
                "device": device,
                "hours": f"{rec.elapsed_raw / 3600.0:.12f}",
                "started_at": rec.start,
                "ended_at": rec.end,
                "notes": notes,
            }
        )

    return out_rows


def main() -> None:
    args = parse_args()

    manifest_path = Path(args.manifest)
    output_csv_path = Path(args.output_csv)
    output_tex_path = Path(args.output_tex)

    manifest_rows = load_manifest(manifest_path)
    job_ids = [row["job_id"] for row in manifest_rows]
    slurm_records = load_slurm_records(job_ids, sacct_bin=args.sacct_bin)

    output_rows = build_rows(
        manifest_rows=manifest_rows,
        slurm_records=slurm_records,
        default_device=args.default_device,
    )

    write_csv(output_csv_path, output_rows)
    write_latex(output_tex_path, output_rows)


if __name__ == "__main__":
    main()

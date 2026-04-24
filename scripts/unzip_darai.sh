#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ZIP_DIR="${PROJECT_ROOT}/darai_raw_zips"
OUT_DIR="/tmp/${USER}_darai"
CLEAN_OUT_DIR="false"
MAX_NESTED_PASSES=8

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --zip-dir <path>   Directory containing DARai zip files (default: ${PROJECT_ROOT}/darai_raw_zips)
  --out-dir <path>   Extraction output directory (default: /tmp/\${USER}_darai)
  --clean            Remove output directory before extracting
  -h, --help         Show this help message

Examples:
  bash scripts/unzip_darai.sh
  bash scripts/unzip_darai.sh --clean
  bash scripts/unzip_darai.sh --zip-dir /path/to/zips --out-dir /tmp/zfan89_darai
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zip-dir)
      ZIP_DIR="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --clean)
      CLEAN_OUT_DIR="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v unzip >/dev/null 2>&1; then
  echo "Error: unzip is required but not found in PATH." >&2
  exit 1
fi

if [[ ! -d "${ZIP_DIR}" ]]; then
  echo "Error: zip directory does not exist: ${ZIP_DIR}" >&2
  exit 1
fi

if [[ "${CLEAN_OUT_DIR}" == "true" && -d "${OUT_DIR}" ]]; then
  echo "[1/5] Removing existing output directory: ${OUT_DIR}"
  rm -rf "${OUT_DIR}"
fi

mkdir -p "${OUT_DIR}"

echo "[2/5] Extracting top-level zip files from: ${ZIP_DIR}"
mapfile -t TOP_LEVEL_ZIPS < <(find "${ZIP_DIR}" -maxdepth 1 -type f -iname '*.zip' | sort)

if [[ ${#TOP_LEVEL_ZIPS[@]} -eq 0 ]]; then
  echo "Error: no zip files found in ${ZIP_DIR}" >&2
  exit 1
fi

for zip_file in "${TOP_LEVEL_ZIPS[@]}"; do
  echo "  - $(basename "${zip_file}")"
  unzip -oq "${zip_file}" -d "${OUT_DIR}"
done

echo "[3/5] Expanding nested zip files (if any)"
for ((pass=1; pass<=MAX_NESTED_PASSES; pass++)); do
  mapfile -t NESTED_ZIPS < <(find "${OUT_DIR}" -type f -iname '*.zip' | sort)
  if [[ ${#NESTED_ZIPS[@]} -eq 0 ]]; then
    echo "  No nested zip files remaining after pass ${pass}."
    break
  fi

  echo "  Pass ${pass}: ${#NESTED_ZIPS[@]} nested zip(s)"
  for nested_zip in "${NESTED_ZIPS[@]}"; do
    nested_parent="$(dirname "${nested_zip}")"
    unzip -oq "${nested_zip}" -d "${nested_parent}"
    rm -f "${nested_zip}"
  done

done

echo "[4/5] Extraction summary"
CSV_COUNT=$(find "${OUT_DIR}" -type f -iname '*.csv' | wc -l | tr -d ' ')
ANNOTATION_COUNT=$(find "${OUT_DIR}" -type f \( -iname '*level_3_annotations.csv' -o -iname '*all_level_annotations.csv' \) | wc -l | tr -d ' ')

echo "  Output directory: ${OUT_DIR}"
echo "  CSV files: ${CSV_COUNT}"
echo "  Annotation files: ${ANNOTATION_COUNT}"

echo "[5/5] Sample extracted paths"
# Avoid SIGPIPE (exit 141) under pipefail by not using find|head pipeline.
sample_count=0
while IFS= read -r sample_path; do
  echo "${sample_path}"
  sample_count=$((sample_count + 1))
  if [[ ${sample_count} -ge 20 ]]; then
    break
  fi
done < <(find "${OUT_DIR}" -maxdepth 4 -type f)

echo "Done. Point the notebook DATA_ROOT to: ${OUT_DIR}"

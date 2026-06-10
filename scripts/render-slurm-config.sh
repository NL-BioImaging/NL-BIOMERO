#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_PATH="${PROJECT_ROOT_DIR}/web/slurm-config-template.ini"
OUTPUT_PATH="${PROJECT_ROOT_DIR}/web/slurm-config.ini"
ENV_PATH="${PROJECT_ROOT_DIR}/.env"
EXPLICIT_SPIDER_USER="${SPIDER_USER:-}"
EXPLICIT_SPIDER_PROJECT="${SPIDER_PROJECT:-}"

# Load default values from the repo env file before honoring an explicit shell override.
if [[ -f "${ENV_PATH}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_PATH}"
  set +a
fi

if [[ -n "${EXPLICIT_SPIDER_USER}" ]]; then
  SPIDER_USER="${EXPLICIT_SPIDER_USER}"
fi

if [[ -n "${EXPLICIT_SPIDER_PROJECT}" ]]; then
  SPIDER_PROJECT="${EXPLICIT_SPIDER_PROJECT}"
fi

: "${SPIDER_USER:?SPIDER_USER must be set in .env or the environment}"
: "${SPIDER_PROJECT:?SPIDER_PROJECT must be set in .env or the environment}"

# If only the rendered config exists, turn it into a parameterized template first.
if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  if [[ -f "${OUTPUT_PATH}" ]]; then
    cp "${OUTPUT_PATH}" "${TEMPLATE_PATH}"
    sed -i \
      -e "s#${SPIDER_USER}#\${SPIDER_USER}#g" \
      -e "s#${SPIDER_PROJECT}#\${SPIDER_PROJECT}#g" \
      "${TEMPLATE_PATH}"
    echo "Generated ${TEMPLATE_PATH} from ${OUTPUT_PATH}"
  else
    echo "Missing template: ${TEMPLATE_PATH}" >&2
    exit 1
  fi
fi

# Substitute Spider deployment values into the runtime config consumed by the containers.
envsubst '${SPIDER_USER} ${SPIDER_PROJECT}' < "${TEMPLATE_PATH}" > "${OUTPUT_PATH}"
# The OMERO.biomero admin UI writes this bind-mounted runtime file from the
# omeroweb container as uid 999. A normal git checkout creates 0644 files owned
# by the host user, which is readable but not writable in the container.
chmod 0666 "${OUTPUT_PATH}"
echo "Rendered ${OUTPUT_PATH}"

#!/usr/bin/env bash
# Live AWS bootstrap/teardown for the Career Graph agent, done so your keys
# NEVER appear in this session/transcript.
#
# 1) Create ./aws_live.env manually (never commit it):
#      aws_access_key_id=AKIA...
#      aws_secret_access_key=...
#      aws_region=us-east-1
#      cg_use_bedrock=0            # set 1 only if Bedrock Haiku access is enabled
#    chmod 600 aws_live.env
#
# 2) Run:  ./scripts/bootstrap_aws.sh bootstrap
#    Or:   ./scripts/bootstrap_aws.sh teardown
#
# The env file is sourced but never printed; the only AWS-identifying output is
# resource names/ARNs of what was created/deleted (no secrets).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_DIR/aws_live.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cat >&2 <<'EOF'
Missing aws_live.env. Create it (chmod 600) with your real credentials:

    aws_access_key_id=AKIA...
    aws_secret_access_key=...
    aws_region=us-east-1
    cg_use_bedrock=0
EOF
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export AWS_ACCESS_KEY_ID="${aws_access_key_id:-}"
export AWS_SECRET_ACCESS_KEY="${aws_secret_access_key:-}"
export AWS_REGION="${aws_region:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
[[ "${cg_use_bedrock:-0}" == "1" ]] && export CAREER_GRAPH_USE_BEDROCK=1
# drop the plaintext vars from the env we pass to children after export
unset aws_access_key_id aws_secret_access_key aws_region cg_use_bedrock

PY="$REPO_DIR/.venv/bin/python"
action="${1:-bootstrap}"
if [[ "$action" == "teardown" ]]; then
  exec "$PY" -c '
from career_graph.ingestion.aws_bootstrap import teardown
import json
print(json.dumps(teardown(), indent=2, sort_keys=True))
'
else
  exec "$PY" -c '
from career_graph.ingestion.aws_bootstrap import bootstrap
import json
print(json.dumps(bootstrap(), indent=2, sort_keys=True))
'
fi

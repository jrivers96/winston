#!/usr/bin/env bash
# Source before gcloud/terraform against winston-ops.
# Usage: source ops/winston-ops/scripts/gcloud_env.sh

# gcloud rejects the default conda Python 3.8 on this machine
if [[ -x /Users/jonathanrivers/anaconda3/envs/py3.11/bin/python ]]; then
  export CLOUDSDK_PYTHON=/Users/jonathanrivers/anaconda3/envs/py3.11/bin/python
elif [[ -x /usr/bin/python3 ]]; then
  export CLOUDSDK_PYTHON=/usr/bin/python3
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS="${CLOUDSDK_CORE_DISABLE_PROMPTS:-0}"

#!/usr/bin/env bash
# Example-data builds may only be deployed to the test environment (UI-11).
# Usage: guard-example-mode.sh <environment> <example: true|false>
set -euo pipefail
environment="${1:?environment}"
example="${2:?example}"
if [ "$example" = "true" ] && [ "$environment" != "test" ]; then
  echo "Example mode is only allowed in the test environment, not in '$environment'." >&2
  exit 1
fi
echo "Example mode guard passed (environment=$environment, example=$example)."

# Branch Protection Configuration

This document describes the required branch protection settings for the `main` branch to prevent breaking changes from being merged.

## Required Status Checks

The following CI checks should be configured as **required status checks** in GitHub branch protection settings:

### Option 1: Use the Merge Gate (Recommended)

Configure only the `Merge Gate` check as required. This workflow automatically verifies all other checks have passed:

| Check Name   | Description                                 |
| ------------ | ------------------------------------------- |
| `Merge Gate` | Aggregates all CI checks into a single gate |

The Merge Gate workflow (`.github/workflows/merge-gate.yaml`) verifies:

- All format checks (Java, Kotlin, Python, YAML, Starlark)
- Unit tests with 90% coverage threshold (`run-unit-tests`)
- Helm chart validation (`Validate Helm Chart`)

## Coverage Requirements

The `run-unit-tests` check enforces a **minimum 90% line coverage** threshold. PRs that reduce coverage below 90% will fail this check.

### Option 2: Configure Individual Checks

Alternatively, configure these individual checks as required:

| Check Name                    | Workflow File               | Triggers On               |
| ----------------------------- | --------------------------- | ------------------------- |
| `run-unit-tests`              | `bazel-test.yaml`           | All PRs                   |
| `runner / google-java-format` | `format-java-code.yaml`     | `**/*.java` changes       |
| `runner / buildifier`         | `format-starlark-code.yaml` | `*.bzl`, `BUILD*` changes |
| `runner / ktlint`             | `format-kotlin-code.yaml`   | `**/*.kt`, `**/*.kts`     |
| `runner / black`              | `format-python-code.yaml`   | `**/*.py` changes         |
| `runner / prettier`           | `format-yaml-code.yaml`     | `**/*.yaml`, `**/*.yml`   |
| `Validate Helm Chart`         | `ci.yaml`                   | All PRs                   |

**Note:** Format checks only run when their respective file types are modified. If using individual checks, consider enabling "Do not require status checks for PRs that don't trigger them" option.

## How to Configure Branch Protection

1. Go to **Settings** > **Branches** in the repository
2. Click **Edit** next to the `main` branch protection rule (or create one)
3. Enable **Require status checks to pass before merging**
4. Enable **Require branches to be up to date before merging**
5. Search for and add the required checks (see options above)
6. Save changes

## Additional Recommended Settings

- **Require a pull request before merging**: Prevents direct pushes to main
- **Require approvals**: Require at least 1 approval before merging
- **Dismiss stale pull request approvals when new commits are pushed**: Ensures reviews are current
- **Require conversation resolution before merging**: Ensures all review comments are addressed

## Troubleshooting

### Check not appearing in the list

Status checks only appear in branch protection after they have run at least once. Create a PR that triggers the workflow to make it available.

### Format check not running

Format checks only run when files matching their path filters are modified:

- Java formatter: `**/*.java`
- Kotlin formatter: `**/*.kt`, `**/*.kts`
- Python formatter: `**/*.py`
- YAML formatter: `**/*.yaml`, `**/*.yml`
- Starlark formatter: `BUILD`, `BUILD.bazel`, `WORKSPACE`, `*.bzl`, etc.

### Merge Gate timeout

The Merge Gate workflow waits up to 30 minutes for other checks to complete. If checks take longer, increase the `maxAttempts` value in the workflow.

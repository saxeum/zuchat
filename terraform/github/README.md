# Repository as code

Creates and configures the GitHub repository for this project: visibility,
description, topics, secret scanning with push protection, Dependabot security
updates, and (optionally) branch protection on `master`.

## Prerequisites

- Terraform >= 1.9
- `GITHUB_TOKEN` exported in your shell, with permission to create the repo and
  change its settings. Never put it in CI: a workflow holding it could rewrite
  the protections this configuration sets.
- `terraform.tfvars` with `owner = "your-account"` (copy the `.example`).

## Order matters

The repository is created empty (`auto_init = false`), so branch protection
cannot attach until `master` exists.

```bash
cd terraform/github
terraform init
terraform apply          # enable_branch_protection = false (default)
# ... push the first commit ...
# set enable_branch_protection = true in terraform.tfvars
terraform apply
```

Or from the repo root:

```bash
make tf-init
make tf-apply      # creates the repo
make github-remote # adds origin from the Terraform output
git push -u origin master
make tf-apply      # after enabling branch protection in terraform.tfvars
```

## What is checked

`contexts = ["test"]` refers to the job id in `.github/workflows/ci.yml`. If
you rename that job, update this file, or the required check never reports and
every merge is blocked.

## State

State is local and git-ignored (`.terraform/`, `*.tfstate*`, `terraform.tfvars`).
The lock file `.terraform.lock.hcl` is committed, like `uv.lock`.

terraform {
  required_version = ">= 1.9"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

# Authenticates from GITHUB_TOKEN in the environment: a PAT that can create the
# repository and change its settings. Keep it in your shell, never in CI - a
# workflow holding it could rewrite the protections below.
provider "github" {
  owner = var.owner
}

variable "owner" {
  description = "Account that owns the repository. Set in terraform.tfvars (git-ignored)."
  type        = string
}

variable "name" {
  description = "Repository name."
  type        = string
  default     = "zuchat"
}

variable "default_branch" {
  description = "Branch the protection attaches to."
  type        = string
  default     = "master"
}

variable "enable_branch_protection" {
  description = <<-EOT
    Branch protection needs the branch to exist. Apply with false, push the
    first commit, then flip to true and apply again.
  EOT
  type        = bool
  default     = false
}

locals {
  # The public URL is the homepage in the About panel and part of the
  # description, so it is written once.
  homepage    = "https://zuchat.foonix.net"
  description = "FastAPI chat app backed by DeepSeek, behind Google OIDC, on AWS ECS via Terraform. Live at ${local.homepage} — any Google account can chat."
}

resource "github_repository" "repo" {
  name         = var.name
  description  = local.description
  homepage_url = local.homepage
  visibility   = "public"
  has_issues   = true
  has_wiki     = false
  auto_init    = false

  # auto_init = false on purpose: the history here is the history of the
  # repository, and an initial README commit would have to be reconciled with
  # it before the first push.

  # These match what the repository already carries; keeping them here means a
  # manual `gh repo edit` cannot quietly survive as drift.
  topics = [
    "aws",
    "chat",
    "deepseek",
    "docker",
    "ecs",
    "fastapi",
    "google-oidc",
    "terraform",
  ]

  # Both free on a public repository, and both turn "no secret has ever been
  # near this" from an intention into an enforced property.
  security_and_analysis {
    secret_scanning {
      status = "enabled"
    }
    secret_scanning_push_protection {
      status = "enabled"
    }
  }
}

resource "github_repository_dependabot_security_updates" "repo" {
  repository = github_repository.repo.name
  enabled    = true
}

resource "github_branch_protection" "default" {
  count = var.enable_branch_protection ? 1 : 0

  repository_id = github_repository.repo.node_id
  pattern       = var.default_branch

  enforce_admins      = true
  allows_force_pushes = false
  allows_deletions    = false

  # The status check is the job id from .github/workflows/ci.yml, not the
  # workflow's `name:` (which is "ci") and not its file name.
  required_status_checks {
    strict   = false
    contexts = ["test"]
  }

  # No required_pull_request_reviews: one account cannot approve its own pull
  # request, so requiring one blocks every merge. enforce_admins is what makes
  # the rest apply to the only account there is.
}

output "full_name" {
  description = "owner/name, used by `make github-remote`."
  value       = github_repository.repo.full_name
}

output "ssh_clone_url" {
  description = "What `make github-remote` points origin at."
  value       = github_repository.repo.ssh_clone_url
}

output "html_url" {
  description = "Where the repository lives."
  value       = github_repository.repo.html_url
}

# The gate for Terraform apply: only master, and only once a human has approved
# the deployment. This is the credential boundary, not just a UI pause: the
# apply role's OIDC subject *is* this Environment.
resource "github_repository_environment" "production" {
  repository  = github_repository.repo.name
  environment = "production"

  # The only account here is an admin, so without this the reviewer requirement
  # would be bypassed by the very person it is meant to hold.
  can_admins_bypass = false

  # `prevent_self_review` stays default (false): with one account, forbidding
  # self-approval would mean nothing could ever deploy. The gate is that the
  # deployment has to be approved at all.
  reviewers {
    users = [var.owner]
  }

  deployment_branch_policy {
    protected_branches     = true
    custom_branch_policies = false
  }
}

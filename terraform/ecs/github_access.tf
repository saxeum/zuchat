# Everything GitHub Actions needs to get into AWS, in one place.
locals {
  github_repo  = "saxeum/zuchat"
  account      = data.aws_caller_identity.current.account_id
  state_bucket = "zuchat-tfstate-${local.account}"

  # One subject per role. The plan role is read-only, so it may be assumed from
  # any ref; the apply role's subject *is* the gate, so it stays narrow.
  github_subjects = {
    plan  = "repo:${local.github_repo}:*"
    apply = "repo:${local.github_repo}:environment:${var.github_environment}"
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "github_trust" {
  for_each = local.github_subjects

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [each.value]
    }
  }
}

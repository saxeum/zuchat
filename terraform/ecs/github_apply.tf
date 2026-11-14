# Apply role for Terraform in Actions. Parameterised by GitHub Environment so
# each environment gets its own role and its own OIDC subject.
variable "github_environment" {
  description = "GitHub Environment whose OIDC claim may assume the apply role."
  type        = string
  default     = "production"
}

locals {
  state_bucket = "zuchat-tfstate-${data.aws_caller_identity.current.account_id}"
  account      = data.aws_caller_identity.current.account_id
}

data "aws_iam_policy_document" "tf_apply_assume" {
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
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_repo}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "tf_apply" {
  name                 = "${var.name}-tf-apply-${var.github_environment}"
  assume_role_policy   = data.aws_iam_policy_document.tf_apply_assume.json
  max_session_duration = 3600
  permissions_boundary = aws_iam_policy.tf_apply_boundary.arn
}

data "aws_iam_policy_document" "tf_apply" {
  statement {
    sid       = "State"
    actions   = ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}", "arn:aws:s3:::${local.state_bucket}/*"]
  }

  statement {
    sid       = "Stack"
    actions   = ["ec2:*", "elasticloadbalancing:*", "ecs:*", "ecr:*", "acm:*", "logs:*", "cloudwatch:*", "application-autoscaling:*"]
    resources = ["*"]
  }

  # Only roles/policies this stack owns: no wildcard IAM.
  statement {
    sid       = "Roles"
    actions   = ["iam:GetRole", "iam:CreateRole", "iam:DeleteRole", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PassRole", "iam:TagRole", "iam:UntagRole"]
    resources = ["arn:aws:iam::${local.account}:role/${var.name}-*"]
  }

  statement {
    sid       = "Policies"
    actions   = ["iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:ListPolicyVersions"]
    resources = ["arn:aws:iam::${local.account}:policy/${var.name}-*"]
  }

  statement {
    sid       = "SecretsRead"
    actions   = ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue"]
    resources = [var.deepseek_secret_arn, var.session_secret_arn, var.google_client_secret_arn]
  }
}

resource "aws_iam_role_policy" "tf_apply" {
  name   = "apply"
  role   = aws_iam_role.tf_apply.id
  policy = data.aws_iam_policy_document.tf_apply.json
}

# The boundary is the ceiling: even if the policy above drifts, these stay denied.
data "aws_iam_policy_document" "tf_apply_boundary" {
  statement {
    sid       = "DenyIdentityEscalation"
    effect    = "Deny"
    actions   = ["iam:*User*", "iam:CreateAccessKey", "iam:UpdateAccountPasswordPolicy", "organizations:*", "account:*", "cloudtrail:StopLogging", "cloudtrail:DeleteTrail"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "tf_apply_boundary" {
  name   = "${var.name}-tf-apply-boundary"
  policy = data.aws_iam_policy_document.tf_apply_boundary.json
}

output "tf_apply_role_arn" {
  value = aws_iam_role.tf_apply.arn
}

# The trust anchor only. Roles and their subjects live in github_access.tf,
# plan in github_terraform.tf, apply in github_apply.tf.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# Everything GitHub Actions needs to get into AWS, in one place.
locals {
  github_repo  = "saxeum/zuchat"
  account      = data.aws_caller_identity.current.account_id
  state_bucket = "zuchat-tfstate-${local.account}"

  # One subject per role. The plan role is assumed from any ref, because
  # `terraform plan` runs on pull requests — so its *policy* is the control: it
  # can read the state and describe this stack, and nothing else. The apply
  # role's subject is the gate, so it stays as narrow as an Environment.
  # GitHub issues *immutable* subjects for this repo:
  #   gh api repos/saxeum/zuchat/actions/oidc/customization/sub
  #   -> sub_claim_prefix "repo:saxeum@343752441/zuchat@1457250024"
  github_subject_prefix = "repo:saxeum@343752441/zuchat@1457250024"

  github_subjects = {
    plan  = "${local.github_subject_prefix}:*"
    apply = "${local.github_subject_prefix}:environment:${var.github_environment}"
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

# Read-only role for `terraform plan` on pull requests.
resource "aws_iam_role" "tf_plan" {
  name               = "${var.name}-tf-plan"
  assume_role_policy = data.aws_iam_policy_document.github_trust["plan"].json
}

# Terraform reads the resources it plans against, so this cannot be nothing —
# but it is scoped rather than ReadOnlyAccess, which also grants s3:GetObject
# and ssm:Get* across the whole account. Any pull request can assume this role.
data "aws_iam_policy_document" "tf_plan" {
  statement {
    sid       = "StateBucket"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]
  }

  statement {
    sid       = "StateObjects"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/*"]
  }

  # Describe and List only: they change nothing and expose no application data.
  statement {
    sid = "DescribeStack"
    actions = [
      "acm:Describe*",
      "acm:List*",
      "application-autoscaling:Describe*",
      "application-autoscaling:ListTagsForResource",
      "autoscaling:Describe*",
      "cloudwatch:Describe*",
      "cloudwatch:ListTagsForResource",
      "ec2:Describe*",
      "ecr:Describe*",
      "ecr:GetLifecyclePolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:List*",
      "ecs:Describe*",
      "ecs:List*",
      "elasticloadbalancing:Describe*",
      "logs:Describe*",
      "logs:ListTagsForResource",
      "logs:ListTagsLogGroup",
    ]
    resources = ["*"]
  }

  statement {
    sid = "IamMetadata"
    actions = [
      "iam:GetOpenIDConnectProvider",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListOpenIDConnectProviders",
      "iam:ListPolicyTags",
      "iam:ListPolicyVersions",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = ["*"]
  }

  # A plan reads secret ARNs, never secret values.
  statement {
    sid       = "SecretMetadata"
    actions   = ["secretsmanager:DescribeSecret"]
    resources = ["arn:aws:secretsmanager:${var.region}:${local.account}:secret:${var.name}/*"]
  }
}

resource "aws_iam_role_policy" "tf_plan" {
  name   = "plan"
  role   = aws_iam_role.tf_plan.id
  policy = data.aws_iam_policy_document.tf_plan.json
}

output "tf_plan_role_arn" {
  value = aws_iam_role.tf_plan.arn
}

# Apply role for Terraform in Actions. Parameterised by GitHub Environment so
# each environment gets its own role and its own OIDC subject.
variable "github_environment" {
  description = "GitHub Environment whose OIDC claim may assume the apply role."
  type        = string
  default     = "production"
}

resource "aws_iam_role" "tf_apply" {
  name                 = "${var.name}-tf-apply-${var.github_environment}"
  assume_role_policy   = data.aws_iam_policy_document.github_trust["apply"].json
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

  # Terraform refreshes the OIDC provider it manages, so the apply role has to
  # be able to read (and, on first run, create) that one provider.
  statement {
    sid       = "OidcProviders"
    actions   = ["iam:GetOpenIDConnectProvider", "iam:CreateOpenIDConnectProvider", "iam:DeleteOpenIDConnectProvider", "iam:TagOpenIDConnectProvider", "iam:UntagOpenIDConnectProvider", "iam:UpdateOpenIDConnectProviderThumbprint"]
    resources = ["arn:aws:iam::${local.account}:oidc-provider/token.actions.githubusercontent.com"]
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
  # A permissions boundary is an *intersection*: it must grant everything the
  # role may do, then carve out the denials. Without this Allow, the boundary
  # permits nothing at all.
  statement {
    sid       = "AllowAll"
    effect    = "Allow"
    actions   = ["*"]
    resources = ["*"]
  }

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

# Terraform takes a lock by writing this object, so a plan needs write on the
# lock and nothing else. ReadOnlyAccess still governs the state itself.
resource "aws_iam_role_policy" "tf_plan_lock" {
  name = "state-lock"
  role = aws_iam_role.tf_plan.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:DeleteObject"]
      Resource = "arn:aws:s3:::${local.state_bucket}/ecs/terraform.tfstate.tflock"
    }]
  })
}

# Separate statement so it cannot be lost in a larger policy edit.
data "aws_iam_policy_document" "tf_apply_oidc" {
  statement {
    actions   = ["iam:GetOpenIDConnectProvider", "iam:CreateOpenIDConnectProvider", "iam:DeleteOpenIDConnectProvider", "iam:TagOpenIDConnectProvider", "iam:UntagOpenIDConnectProvider", "iam:UpdateOpenIDConnectProviderThumbprint", "iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "tf_apply_oidc" {
  name   = "oidc"
  role   = aws_iam_role.tf_apply.id
  policy = data.aws_iam_policy_document.tf_apply_oidc.json
}

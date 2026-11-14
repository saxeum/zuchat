# Read-only role for `terraform plan` on pull requests. It can look, never
# change: the trust subject is the PR claim, so even a compromised branch
# cannot use it to apply.
data "aws_iam_policy_document" "tf_plan_assume" {
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
      values   = ["repo:${local.github_repo}:pull_request"]
    }
  }
}

resource "aws_iam_role" "tf_plan" {
  name               = "${var.name}-tf-plan"
  assume_role_policy = data.aws_iam_policy_document.tf_plan_assume.json
}

# ReadOnlyAccess: broad by design. A plan needs to read everything Terraform
# manages, and read access cannot delete the ALB.
resource "aws_iam_role_policy_attachment" "tf_plan" {
  role       = aws_iam_role.tf_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

output "tf_plan_role_arn" {
  value = aws_iam_role.tf_plan.arn
}

# Read-only role for `terraform plan` on pull requests.
resource "aws_iam_role" "tf_plan" {
  name               = "${var.name}-tf-plan"
  assume_role_policy = data.aws_iam_policy_document.github_trust["plan"].json
}

# ReadOnlyAccess: broad by design, and read access cannot delete the ALB.
resource "aws_iam_role_policy_attachment" "tf_plan" {
  role       = aws_iam_role.tf_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

output "tf_plan_role_arn" {
  value = aws_iam_role.tf_plan.arn
}

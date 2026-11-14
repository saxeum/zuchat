# The ECS module creates the execution role (it needs it for ECR and logs), so
# attach the secrets permission to *that* role rather than creating a second one
# that the service never assumes.
data "aws_iam_policy_document" "secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      var.deepseek_secret_arn,
      var.session_secret_arn,
      var.google_client_secret_arn,
    ]
  }
}

resource "aws_iam_role_policy" "secrets" {
  name   = "read-secrets"
  role   = module.ecs.task_exec_iam_role_name
  policy = data.aws_iam_policy_document.secrets.json
}

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 6.0"

  cluster_name = var.name

  # A target group must be attached to a listener before ECS will accept it,
  # and the service is created inside this module - so wait for the listeners.
  depends_on = [aws_lb_listener.http, aws_lb_listener.https]

  services = {
    (var.name) = {
      cpu    = 512
      # The module would otherwise create its own execution role and ignore ours.
      create_task_exec_iam_role = false
      execution_role_arn        = aws_iam_role.execution.arn
      memory = 1024

      container_definitions = {
        app = {
          image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
          essential = true

          portMappings = [{ containerPort = 8000, protocol = "tcp" }]

          environment = [
            { name = "APP_BASE_URL", value = "https://${var.domain}" },
            { name = "GOOGLE_CLIENT_ID", value = var.google_client_id },
            { name = "ALLOWED_EMAILS", value = var.allowed_emails },
          ]

          secrets = [
            { name = "DEEPSEEK_API_KEY", valueFrom = var.deepseek_secret_arn },
            { name = "SESSION_SECRET", valueFrom = var.session_secret_arn },
            { name = "GOOGLE_CLIENT_SECRET", valueFrom = var.google_client_secret_arn },
          ]

          cloudwatch_log_group_retention_in_days = 14
        }
      }

      load_balancer = {
        service = {
          target_group_arn = aws_lb_target_group.app.arn
          container_name   = "app"
          container_port   = 8000
        }
      }

      # No NAT gateway in this VPC, so the task needs a public IP to reach
      # ECR, S3, CloudWatch and Secrets Manager.
      assign_public_ip   = true
      subnet_ids         = module.vpc.public_subnets
      security_group_ids = [aws_security_group.service.id]
      # The module otherwise attaches its own SG too; two SGs, one with no
      # egress, makes connectivity failures ambiguous. One SG, ours.
      create_security_group = false
    }
  }
}

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 6.0"

  cluster_name = var.name

  services = {
    (var.name) = {
      cpu    = 512
      memory = 1024

      execution_role_arn = aws_iam_role.execution.arn

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

      subnet_ids       = module.vpc.public_subnets
      security_group_ids = [aws_security_group.service.id]
    }
  }
}

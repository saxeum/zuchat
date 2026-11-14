# Phase 1: network, registry, certificate. The ECS service lands in phase 2 so
# the certificate can be validated against Cloudflare DNS first.

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = var.name
  cidr = var.vpc_cidr

  azs            = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets = [cidrsubnet(var.vpc_cidr, 8, 1), cidrsubnet(var.vpc_cidr, 8, 2)]

  map_public_ip_on_launch = true
  enable_nat_gateway      = false
  enable_dns_hostnames    = true
  enable_dns_support      = true
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_ecr_repository" "app" {
  name                 = var.name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# DNS lives at Cloudflare, so Terraform creates the certificate and prints the
# validation records. Add them at the registrar, then set certificate_arn.
resource "aws_acm_certificate" "app" {
  domain_name       = var.domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

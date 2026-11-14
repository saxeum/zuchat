terraform {
  required_version = ">= 1.9"

  # State lives in S3 so CI can run Terraform. Native S3 locking (Terraform
  # >= 1.10): no DynamoDB table to keep alive.
  backend "s3" {
    bucket       = "zuchat-tfstate-619071335809"
    key          = "ecs/terraform.tfstate"
    region       = "ap-southeast-2"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}

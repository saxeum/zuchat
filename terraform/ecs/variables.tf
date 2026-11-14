variable "region" {
  description = "AWS region."
  type        = string
  default     = "ap-southeast-2"
}

variable "name" {
  description = "Prefix for every resource."
  type        = string
  default     = "zuchat"
}

variable "domain" {
  description = "Public hostname the ALB serves (Cloudflare DNS, not Route 53)."
  type        = string
  default     = "zuchat.foonix.net"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC (two public subnets, no NAT)."
  type        = string
  default     = "10.42.0.0/16"
}

# Secrets are referenced, never created here: nothing sensitive enters state.
variable "deepseek_secret_arn" {
  description = "Secrets Manager ARN holding the DeepSeek API key."
  type        = string
}

variable "session_secret_arn" {
  description = "Secrets Manager ARN holding SESSION_SECRET."
  type        = string
}

variable "google_client_secret_arn" {
  description = "Secrets Manager ARN holding the Google client secret."
  type        = string
}

variable "google_client_id" {
  description = "Google OAuth client id (not secret)."
  type        = string
}

variable "allowed_emails" {
  description = "Comma-separated allowlist for sign-in."
  type        = string
}

variable "image_tag" {
  description = "Image tag to deploy from the ECR repository created here."
  type        = string
  default     = "latest"
}

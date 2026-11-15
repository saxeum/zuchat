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
  description = "Comma-separated allowlist for sign-in. Empty admits any Google account."
  type        = string
}

variable "rate_limit_per_minute" {
  description = "Chat requests allowed per signed-in user per minute (0 disables)."
  type        = number
  default     = 10
}

variable "rate_limit_global_per_minute" {
  description = "Chat requests allowed across all users per minute (0 disables)."
  type        = number
  default     = 60
}

variable "max_concurrent_per_user" {
  description = "Replies allowed in flight per signed-in user (0 disables)."
  type        = number
  default     = 1
}

variable "max_concurrent_total" {
  description = "Replies allowed in flight across all users (0 disables)."
  type        = number
  default     = 8
}

variable "session_max_age_seconds" {
  description = "Lifetime of the signed session cookie, in seconds."
  type        = number
  default     = 86400
}

variable "max_body_bytes" {
  description = "Largest accepted request body, in bytes (0 disables the check)."
  type        = number
  default     = 65536
}

variable "max_output_tokens" {
  description = "Cap on tokens in one reply, so no single request is unbounded."
  type        = number
  default     = 1024
}

variable "token_budget_per_day" {
  description = "Tokens one user may spend per day, in UTC days (0 disables)."
  type        = number
  default     = 100000
}

variable "token_budget_global_per_day" {
  description = "Tokens all users may spend per day, in UTC days (0 disables)."
  type        = number
  default     = 1000000
}

variable "image_tag" {
  description = "Image tag to deploy from the ECR repository created here."
  type        = string
  default     = "latest"
}

variable "certificate_arn" {
  description = "Issued ACM certificate ARN. Required - a missing value must fail the plan, not delete TLS."
  type        = string
}

variable "enable_https" {
  description = "Create the HTTPS listener (and redirect HTTP to it). Set false only while bootstrapping a certificate."
  type        = bool
  default     = true
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "certificate_validation_records" {
  description = "Add these CNAMEs at Cloudflare (DNS only, not proxied)."
  value = [
    for option in aws_acm_certificate.app.domain_validation_options : {
      name  = option.resource_record_name
      type  = option.resource_record_type
      value = option.resource_record_value
    }
  ]
}

output "alb_dns_name" {
  description = "CNAME zuchat.foonix.net to this (Cloudflare: DNS only)."
  value       = aws_lb.app.dns_name
}

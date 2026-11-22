output "web_url" {
  value = local.web_url
}

output "api_url" {
  value = "${local.api_url}/docs"
}

output "image_bucket" {
  value = aws_s3_bucket.images.bucket
}

output "db_endpoint" {
  value = aws_db_instance.this.address
}

output "instance_id" {
  value = aws_instance.app.id
}

output "redeploy_command" {
  description = "git push 후 실행하면 EC2 에서 최신 코드로 다시 빌드한다"
  value       = "aws ssm send-command --region ${var.region} --instance-ids ${aws_instance.app.id} --document-name AWS-RunShellScript --parameters 'commands=[\"cd /opt/used-market && git pull && cd infra && docker compose up -d --build\"]'"
}

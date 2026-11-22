data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "random_password" "secret_key" {
  length  = 48
  special = false
}

# ---- IAM: S3 업로드 + SSM 접속(SSH 키 없이 콘솔/CLI 로 들어가기) ----
resource "aws_iam_role" "app" {
  name = "${var.name}-app"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_upload" {
  name = "s3-upload"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:DeleteObject"]
      Resource = "${aws_s3_bucket.images.arn}/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.name}-app"
  role = aws_iam_role.app.name
}

# ---- EC2 ----
# 고정 IP 를 먼저 만들어 두고, 그 주소를 웹 빌드(NEXT_PUBLIC_API_URL)와 CORS 에 넣는다
resource "aws_eip" "app" {
  domain = "vpc"
}

locals {
  public_ip = aws_eip.app.public_ip
  web_url   = "http://${local.public_ip}"
  api_url   = "http://${local.public_ip}:8000"
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.ubuntu.value
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # 컨테이너 안의 boto3 가 인스턴스 역할 자격증명을 받으려면 hop 2 가 필요
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url         = var.repo_url
    git_branch       = var.git_branch
    load_sample_data = var.load_sample_data
    env_file = join("\n", [
      "DB_HOST=${aws_db_instance.this.address}",
      "DB_PORT=${aws_db_instance.this.port}",
      "DB_USER=${aws_db_instance.this.username}",
      "DB_PASSWORD=${random_password.db.result}",
      "DB_NAME=used_market",
      "SECRET_KEY=${random_password.secret_key.result}",
      "CORS_ORIGINS=${local.web_url}",
      "AWS_REGION=${var.region}",
      "S3_BUCKET=${aws_s3_bucket.images.bucket}",
      "S3_PUBLIC_URL=https://${aws_s3_bucket.images.bucket_regional_domain_name}",
      "PUBLIC_API_URL=${local.api_url}",
    ])
  })
  user_data_replace_on_change = true

  tags = {
    Name = var.name
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}

# 상품 이미지 버킷. products/* 는 누구나 읽을 수 있다 (화면에서 <img> 로 바로 띄움)
resource "aws_s3_bucket" "images" {
  bucket_prefix = "${var.name}-images-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "images" {
  bucket = aws_s3_bucket.images.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "images_public_read" {
  bucket = aws_s3_bucket.images.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadProductImages"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.images.arn}/products/*"
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.images]
}

variable "name" {
  description = "리소스 이름 접두어"
  type        = string
  default     = "used-market"
}

variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "repo_url" {
  description = "EC2 가 clone 할 공개 git 저장소"
  type        = string
  default     = "https://github.com/joojae02/used-market-db.git"
}

variable "git_branch" {
  description = "배포할 브랜치 (원격에 push 되어 있어야 함)"
  type        = string
  default     = "main"
}

variable "instance_type" {
  description = "Next.js 빌드에 메모리가 필요해서 small 이상 권장"
  type        = string
  default     = "t3.small"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "load_sample_data" {
  description = "첫 부팅 때 db/sample_data.sql 을 넣고 모든 비밀번호를 1234 로 설정"
  type        = bool
  default     = true
}

# 데모 배포 (Terraform + AWS)

데모용으로 최소 구성만 만든다. 기본 VPC를 쓰고 HTTPS·도메인은 없다.

```
브라우저 ──80──▶ EC2 (docker compose: web :80, api :8000) ──3306──▶ RDS MySQL 8.4
   │                         │
   └──── 상품 이미지 GET ────▶ S3 (products/* 공개 읽기) ◀── PutObject (인스턴스 역할)
```

| 리소스 | 내용 |
| --- | --- |
| EC2 `t3.small` (Ubuntu 24.04) | 레포를 clone 해서 `infra/compose.yml` 로 API·웹을 빌드·실행. 고정 IP(EIP) |
| RDS MySQL `db.t4g.micro` | 외부 비공개, EC2 보안그룹에서만 접속. 첫 부팅 때 `db/schema.sql` + 샘플 데이터 적재 |
| S3 버킷 | 업로드한 상품 이미지 저장. `products/*` 만 공개 읽기 |

## 배포

준비물: Terraform 1.6+, AWS CLI (자격증명 설정 완료).

EC2가 GitHub에서 코드를 받으므로 **배포할 브랜치가 원격에 push 되어 있어야 한다** (기본 `main`).

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # 브랜치 등을 바꿀 때만
terraform init
terraform apply
```

RDS 생성에 5~10분, 그 뒤 EC2 첫 부팅(도커 설치 + 빌드)에 5분 정도 걸린다. `apply`가 끝나도 바로 안 뜨면 몇 분 기다린다.

```bash
terraform output web_url   # http://<고정IP>
terraform output api_url   # http://<고정IP>:8000/docs
```

샘플 계정 비밀번호는 전부 `1234` (`load_sample_data = false`면 빈 DB).

## 코드 수정 후 재배포

```bash
git push
$(terraform output -raw redeploy_command)
```

EC2에서 `git pull` 후 이미지를 다시 빌드한다. DB는 건드리지 않는다.
DB까지 처음 상태로 되돌리려면 `terraform apply -replace=aws_instance.app` (EC2를 새로 만들면서 스키마를 다시 넣는다).

## 서버 들여다보기

SSH 키 없이 SSM으로 접속한다 ([Session Manager 플러그인](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) 필요).

```bash
aws ssm start-session --target $(terraform output -raw instance_id)
sudo tail -f /var/log/cloud-init-output.log       # 첫 부팅 로그
cd /opt/used-market/infra && sudo docker compose logs -f
```

## 정리

```bash
terraform destroy
```

S3 버킷은 안에 이미지가 있어도 같이 지워지고, RDS는 최종 스냅샷 없이 삭제된다.

## 주의

- HTTP만 쓴다. 비밀번호가 평문으로 오가므로 데모 외 용도로 쓰지 않는다.
- DB 비밀번호 등은 Terraform state와 EC2 user data에 들어 있다. `terraform.tfstate`를 커밋하지 않는다 (`.gitignore` 처리됨).
- 켜 두면 EC2·RDS·EIP 비용이 계속 나간다. 발표가 끝나면 `destroy`.

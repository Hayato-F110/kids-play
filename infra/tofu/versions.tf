# OpenTofu と provider の版を固定する。provider のハッシュは .terraform.lock.hcl で固定する
terraform {
  required_version = "~> 1.12.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "4.6.0"
    }
  }

  # state と plan を平文で書かせない（fail-safe）。鍵の設定は TF_ENCRYPTION 環境変数で
  # scripts/tofu.ps1 が渡す。渡し忘れたときは、平文で書かずに止まる。
  # パスフレーズをコードや変数ファイルに書かないため、鍵の設定はここに書かない。
  # 注意（v1.12.11 で確かめた）：渡し忘れると、state の行に「Invalid expression」と出て止まる。
  # 式の誤りではなく、鍵の設定がないという意味
  encryption {
    state {
      enforced = true
    }
    plan {
      enforced = true
    }
  }
}

# 既定の接続先（Windows の Docker Desktop の名前付きパイプ）を使う
provider "docker" {}

# compose.yaml と同じ構成（web + api）を OpenTofu で作る。
# 名前に -tofu を付け、compose で作ったものと混ざらないようにする

# イメージは手元にあるものを読むだけ（data）。destroy でイメージを消さないため、resource にしない
data "docker_image" "web" {
  name = var.web_image
}

data "docker_image" "api" {
  name = var.api_image
}

# web と api だけが入るネットワーク。web の nginx は「api」という名前で api に届く
resource "docker_network" "kids_play" {
  name = "kids-play-tofu"
}

# compose の x-hardening と同じ守り。2つのコンテナに同じ値を使う
locals {
  security_opts = ["no-new-privileges:true"]
  tmpfs         = { "/tmp" = "rw,noexec,nosuid,size=16m" }
}

resource "docker_container" "api" {
  name  = "kids-play-tofu-api"
  image = data.docker_image.api.id

  # サーバー保存（KIDS_SERVER_STORAGE）は渡さない。絵と声は端末の中にだけ保存する（T-08、C-12）
  read_only     = true
  tmpfs         = local.tmpfs
  security_opts = local.security_opts
  memory        = var.memory_mb
  # swap を使わせない。書かないと Docker がメモリの2倍にし、コードとずれ続ける（ドリフト）
  memory_swap = var.memory_mb

  capabilities {
    drop = ["ALL"]
  }

  # ports は書かない。web からだけ届く
  networks_advanced {
    name    = docker_network.kids_play.id
    aliases = ["api"]
  }
}

resource "docker_container" "web" {
  name  = "kids-play-tofu-web"
  image = data.docker_image.web.id

  read_only     = true
  tmpfs         = local.tmpfs
  security_opts = local.security_opts
  memory        = var.memory_mb
  memory_swap   = var.memory_mb

  capabilities {
    drop = ["ALL"]
  }

  # この PC の中（127.0.0.1）からだけ開ける
  ports {
    internal = 8080
    external = var.web_port
    ip       = var.listen_ip
  }

  networks_advanced {
    name = docker_network.kids_play.id
  }

  # api の名前が引けるようになってから nginx を起動する
  depends_on = [docker_container.api]
}

variable "listen_ip" {
  description = "web を公開する IP。この PC の中からだけ開けるよう、127.0.0.1 以外は受け付けない"
  type        = string
  default     = "127.0.0.1"

  validation {
    # 0.0.0.0 などを渡すと、同じ Wi-Fi のほかの機器からも届いてしまう（compose と同じ方針）
    condition     = var.listen_ip == "127.0.0.1"
    error_message = "listen_ip は 127.0.0.1 だけを使えます。"
  }
}

variable "web_port" {
  description = "PC 側のポート。compose の 8080 と重ならない番号にする"
  type        = number
  default     = 8090
}

variable "web_image" {
  description = "web（nginx）のイメージ。docker compose build で作った手元のもの"
  type        = string
  default     = "kids-play-web:local"

  validation {
    # :latest やタグなしは、いつの中身かが分からないので使わせない
    condition     = can(regex(":[A-Za-z0-9_.-]+$", var.web_image)) && !endswith(var.web_image, ":latest")
    error_message = "web_image にはタグを付けてください（:latest は使えません）。"
  }
}

variable "api_image" {
  description = "api（FastAPI）のイメージ。docker compose build で作った手元のもの"
  type        = string
  default     = "kids-play-api:local"

  validation {
    condition     = can(regex(":[A-Za-z0-9_.-]+$", var.api_image)) && !endswith(var.api_image, ":latest")
    error_message = "api_image にはタグを付けてください（:latest は使えません）。"
  }
}

variable "memory_mb" {
  description = "1つのコンテナが使えるメモリの上限（MB）。暴走しても PC 全体を止めないため"
  type        = number
  default     = 256

  validation {
    condition     = var.memory_mb >= 64 && var.memory_mb <= 1024
    error_message = "memory_mb は 64〜1024 にしてください。"
  }
}

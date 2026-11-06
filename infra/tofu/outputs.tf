output "url" {
  description = "ブラウザで開く URL"
  value       = "http://${var.listen_ip}:${var.web_port}/"
}

# 構成の守りを、Docker を動かさずに確かめる（CI でも動く）。
# mock_provider で Docker の provider を偽物にし、plan の結果だけを調べる。
# 本物の Docker での確認は scripts/tofu-verify.ps1 が行う。

mock_provider "docker" {}

# A1：既定の公開先は、この PC の中（127.0.0.1:8090）だけ
run "web_listens_only_on_localhost" {
  command = plan

  assert {
    condition     = length(docker_container.web.ports) == 1
    error_message = "web が公開するポートは1つだけのはず"
  }

  assert {
    condition     = one(docker_container.web.ports).ip == "127.0.0.1"
    error_message = "web の公開先が 127.0.0.1 ではない"
  }

  assert {
    condition     = one(docker_container.web.ports).external == 8090 && one(docker_container.web.ports).internal == 8080
    error_message = "web の公開ポートが 127.0.0.1:8090 -> 8080 ではない"
  }
}

# A2：同じ Wi-Fi の機器からも届く 0.0.0.0 を渡すと、plan の前に止まる（fail-safe）
run "reject_listen_on_all_interfaces" {
  command = plan

  variables {
    listen_ip = "0.0.0.0"
  }

  expect_failures = [
    var.listen_ip,
  ]
}

# A3：2つのコンテナとも、compose と同じ最小権限の守りとメモリの上限がある
run "both_containers_are_hardened" {
  command = plan

  assert {
    condition = alltrue([
      for c in [docker_container.web, docker_container.api] : c.read_only
    ])
    error_message = "読み取り専用でないコンテナがある"
  }

  assert {
    condition = alltrue([
      for c in [docker_container.web, docker_container.api] : contains(one(c.capabilities).drop, "ALL")
    ])
    error_message = "capabilities を全部外していないコンテナがある"
  }

  assert {
    condition = alltrue([
      for c in [docker_container.web, docker_container.api] : contains(c.security_opts, "no-new-privileges:true")
    ])
    error_message = "no-new-privileges がないコンテナがある"
  }

  assert {
    condition = alltrue([
      for c in [docker_container.web, docker_container.api] : c.memory == var.memory_mb && var.memory_mb > 0
    ])
    error_message = "メモリの上限がないコンテナがある"
  }

  # swap を書かないと Docker がメモリの2倍にし、作った直後からコードとずれる（21日目に見つけた）
  assert {
    condition = alltrue([
      for c in [docker_container.web, docker_container.api] : c.memory_swap == c.memory
    ])
    error_message = "memory_swap がメモリの上限と同じでないコンテナがある（swap を使わせない）"
  }
}

# A4：api はポートを公開しない（web からだけ届く）
run "api_has_no_published_ports" {
  command = plan

  assert {
    condition     = length(docker_container.api.ports) == 0
    error_message = "api がポートを公開している"
  }
}

# A5：中身が変わりうる :latest は使わせない
run "reject_latest_tag" {
  command = plan

  variables {
    web_image = "kids-play-web:latest"
  }

  expect_failures = [
    var.web_image,
  ]
}

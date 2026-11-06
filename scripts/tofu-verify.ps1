# OpenTofu で作った kids-play を試験する。21日目、KIDS-65。
# 使い方（リポジトリの一番上で、PowerShell）：
#   ./scripts/tofu-verify.ps1 -Phase up     apply のあと（B6〜B8）
#   ./scripts/tofu-verify.ps1 -Phase down   apply（plan-destroy の予告）のあと（B9）
# 結果は PASS / FAIL で1行ずつ出す。FAIL が1つでもあれば終了コード 1。
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('up', 'down')]
  [string]$Phase
)
$ErrorActionPreference = 'Stop'
$failed = 0
$web = 'kids-play-tofu-web'
$api = 'kids-play-tofu-api'
$network = 'kids-play-tofu'
$stateFile = Join-Path $PSScriptRoot '..\infra\tofu\terraform.tfstate'

function Report([string]$name, [bool]$ok, [string]$detail = '') {
  $mark = if ($ok) { 'PASS' } else { 'FAIL' }
  if (-not $ok) { $script:failed++ }
  Write-Host ("{0}  {1}  {2}" -f $mark, $name, $detail)
}

function StatusCode([string]$url) {
  try { (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5).StatusCode } catch { "error: $($_.Exception.Message)" }
}

if ($Phase -eq 'up') {
  # B6：web が開け、web を通して api にも届く
  $top = StatusCode 'http://127.0.0.1:8090/'
  Report 'B6a トップの画面が 200' ($top -eq 200) "$top"
  $status = StatusCode 'http://127.0.0.1:8090/api/storage/status'
  Report 'B6b web を通して api が 200' ($status -eq 200) "$status"

  # B7：テストA3・A4 と同じ守りが、実物のコンテナにも入っている
  foreach ($name in @($web, $api)) {
    $h = (docker inspect $name | ConvertFrom-Json)[0].HostConfig
    Report "B7 $name 読み取り専用" ($h.ReadonlyRootfs -eq $true)
    Report "B7 $name capabilities を全部外す" ($h.CapDrop -contains 'ALL') "$($h.CapDrop)"
    Report "B7 $name no-new-privileges" ($h.SecurityOpt -contains 'no-new-privileges:true') "$($h.SecurityOpt)"
    Report "B7 $name メモリの上限 256MB" ($h.Memory -eq 256MB) "$($h.Memory)"
  }
  $webPorts = (docker inspect $web | ConvertFrom-Json)[0].HostConfig.PortBindings.'8080/tcp'
  Report 'B7 web は 127.0.0.1:8090 だけで公開' (($webPorts.Count -eq 1) -and ($webPorts[0].HostIp -eq '127.0.0.1') -and ($webPorts[0].HostPort -eq '8090')) (($webPorts | ForEach-Object { "$($_.HostIp):$($_.HostPort)" }) -join ',')
  $apiPorts = (docker inspect $api | ConvertFrom-Json)[0].HostConfig.PortBindings
  $apiCount = if ($null -eq $apiPorts) { 0 } else { @($apiPorts.PSObject.Properties).Count }
  Report 'B7 api はポートを公開しない' ($apiCount -eq 0) "$apiCount"

  # B8：state は暗号化されていて、平文の state の目印が見えない
  if (Test-Path $stateFile) {
    $text = Get-Content $stateFile -Raw
    Report 'B8a state に暗号化の印がある' ($text -match '"encryption_version"') ''
    Report 'B8b state に平文の目印がない' (-not ($text -match '"resources"|kids-play-tofu-web|127\.0\.0\.1')) ''
  } else {
    Report 'B8 state のファイルがある' $false $stateFile
  }
} else {
  # B9：コンテナとネットワークは消え、イメージは残る
  $containers = docker ps -a --filter "name=kids-play-tofu" --format '{{.Names}}'
  Report 'B9a コンテナが残っていない' ([string]::IsNullOrWhiteSpace(($containers -join ''))) "$containers"
  $nets = docker network ls --filter "name=^$network$" --format '{{.Name}}'
  Report 'B9b ネットワークが残っていない' ([string]::IsNullOrWhiteSpace(($nets -join ''))) "$nets"
  foreach ($img in @('kids-play-web:local', 'kids-play-api:local')) {
    $id = docker images -q $img
    Report "B9c イメージ $img が残っている" (-not [string]::IsNullOrWhiteSpace(($id -join ''))) ''
  }
}

if ($failed -gt 0) { Write-Host "FAIL の数：$failed"; exit 1 }
Write-Host 'すべて PASS'

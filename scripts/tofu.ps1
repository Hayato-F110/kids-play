# OpenTofu を、state の暗号化の鍵を渡して動かす。21日目、KIDS-65。
# 使い方（リポジトリの一番上で、PowerShell）：
#   ./scripts/tofu.ps1 init | fmt | validate | test | output | state-list
#   ./scripts/tofu.ps1 plan            作る・変える予告を infra/tofu/kids.tfplan に保存する
#   ./scripts/tofu.ps1 plan-destroy    消す予告を infra/tofu/kids.tfplan に保存する
#   ./scripts/tofu.ps1 apply           保存した予告だけを実行する（学習者が予告を読んでから）
#
# なぜ予告を保存するか：人が読んだ予告と、実際に行う変更を同じものにするため。
# apply を予告なしで動かす使い方と -auto-approve は、ここで断る。
# なぜ鍵をここで渡すか：infra/tofu/versions.tf で暗号化を必須にしているため（平文の state を書かない）。
# 鍵はリポジトリの外（ユーザーのフォルダー）に置き、画面に出さない。
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('init', 'fmt', 'validate', 'test', 'plan', 'plan-destroy', 'apply', 'output', 'state-list')]
  [string]$Command
)
$ErrorActionPreference = 'Stop'

$tofu = Join-Path $env:LOCALAPPDATA 'Programs\OpenTofu\1.12.11\tofu.exe'
$dir = Join-Path $PSScriptRoot '..\infra\tofu'
$planFile = 'kids.tfplan'
if (-not (Test-Path $tofu)) { throw "OpenTofu が見つかりません：$tofu" }

# 鍵のファイル。なければ作る（32バイトの乱数）。消すと、いまの state と plan は読めなくなる
$keyDir = Join-Path $env:LOCALAPPDATA 'kids-play'
$keyFile = Join-Path $keyDir 'tofu-encryption.txt'
if (-not (Test-Path $keyFile)) {
  New-Item -ItemType Directory -Force $keyDir | Out-Null
  $bytes = [byte[]]::new(32)
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  Set-Content -Path $keyFile -Value ([Convert]::ToBase64String($bytes)) -NoNewline -Encoding ascii
  Write-Host "鍵のファイルを作りました（中身は表示しません）：$keyFile"
}
$passphrase = (Get-Content $keyFile -Raw).Trim()

# 鍵の設定は、このスクリプトのプロセスの中だけに置く（終われば消える）
$env:TF_ENCRYPTION = @"
key_provider "pbkdf2" "local" {
  passphrase = "$passphrase"
}
method "aes_gcm" "local" {
  keys = key_provider.pbkdf2.local
}
state {
  method = method.aes_gcm.local
}
plan {
  method = method.aes_gcm.local
}
"@

# @( ) で囲む：switch は要素が1つの配列を文字列にほどき、splat で1文字ずつ渡ってしまうため
$tofuArgs = @(switch ($Command) {
  'init' { @('init', '-input=false') }
  'fmt' { @('fmt', '-check', '-recursive', '-diff') }
  'validate' { @('validate') }
  'test' { @('test') }
  'plan' { @('plan', '-input=false', "-out=$planFile") }
  'plan-destroy' { @('plan', '-destroy', '-input=false', "-out=$planFile") }
  'apply' {
    if (-not (Test-Path (Join-Path $dir $planFile))) { throw '予告がありません。先に plan か plan-destroy を実行し、内容を読んでください。' }
    @('apply', '-input=false', $planFile)
  }
  'output' { @('output') }
  'state-list' { @('state', 'list') }
})

Push-Location $dir
try {
  & $tofu @tofuArgs -no-color
  $code = $LASTEXITCODE
  # 使い終わった予告は消す。古い予告を、あとでうっかり実行しないため
  if ($Command -eq 'apply' -and $code -eq 0) { Remove-Item $planFile -Confirm:$false }
} finally {
  Pop-Location
  Remove-Item Env:TF_ENCRYPTION -ErrorAction SilentlyContinue
}
exit $code

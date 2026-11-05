# kind の kids-play を試験する（C-36、C-37）。20日目、KIDS-64。
# 使い方（リポジトリの一番上で、PowerShell）：./scripts/k8s-verify.ps1
# 結果は PASS / FAIL で1行ずつ出す。FAIL が1つでもあれば終了コード 1。
#
# 「止まる」の確かめ方：Service の名前ではなく Pod の IP とポートへ直接つなぐ。
# Service に載せていないポートは、名前でつなぐと規則と関係なく失敗するので、規則の試験にならないため。
# 止まったときは「時間切れ」になることを見る（つなぎ先がない「拒否」とは区別する）。
$ErrorActionPreference = 'Stop'
$context = 'kind-kids-play'
$ns = 'kids-play'
$failed = 0

function Report([string]$name, [bool]$ok, [string]$detail = '') {
  $mark = if ($ok) { 'PASS' } else { 'FAIL' }
  if (-not $ok) { $script:failed++ }
  Write-Host ("{0}  {1}  {2}" -f $mark, $name, $detail)
}

function Kube { kubectl --context $context -n $ns @args }
function PodIp([string]$app) { Kube get pod -l "app.kubernetes.io/name=$app" -o jsonpath='{.items[0].status.podIP}' }

# api の Pod から、ほかへ TCP でつなぐ（Python で。結果は ok / timeout / refused などの1語）
$probePy = 'import socket,sys' + "`n" + 'try:' + "`n" + ' socket.create_connection((sys.argv[1], int(sys.argv[2])), 3); print("ok")' + "`n" + 'except TimeoutError: print("timeout")' + "`n" + 'except OSError as e: print(type(e).__name__)'
# 注意：PowerShell の関数に渡した -- は PowerShell が取り除くので、exec は関数（Kube）を通さずに直接呼ぶ
function FromApi([string]$hostName, [int]$port) {
  $out = kubectl --context $context -n $ns exec deploy/api '--' python -c $probePy $hostName $port 2>&1
  ($out | Select-Object -Last 1).ToString().Trim()
}
# web の Pod から HTTP でつなぐ（busybox の wget。Host は api が受け付ける名前にする）
function FromWeb([string]$url) {
  $out = kubectl --context $context -n $ns exec deploy/web '--' wget -q -T 3 -O /dev/null --header 'Host: localhost' $url 2>&1
  if ($LASTEXITCODE -eq 0) { return 'ok' }
  if ("$out" -match 'timed out') { return 'timeout' }
  return "error: $out"
}

$apiIp = PodIp 'api'
$jaegerIp = PodIp 'jaeger'
Write-Host "api=$apiIp jaeger=$jaegerIp"

# a. 画面が表示される
try {
  $res = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:8081/
  Report 'a. 127.0.0.1:8081 のトップ画面' ($res.StatusCode -eq 200 -and $res.Content -match '<title>') "status=$($res.StatusCode)"
} catch { Report 'a. 127.0.0.1:8081 のトップ画面' $false $_.Exception.Message }

# b. 許した通信は通る
$r = FromWeb "http://${apiIp}:8000/api/storage/status"; Report 'b1. web → api:8000（許可）' ($r -eq 'ok') $r
$r = FromApi $jaegerIp 4318; Report 'b2. api → jaeger:4318（許可）' ($r -eq 'ok') $r

# c. 許していない通信は止まる（時間切れになる）
$r = FromWeb "http://${jaegerIp}:4318/"; Report 'c1. web → jaeger:4318（拒否）' ($r -eq 'timeout') $r
$r = FromWeb "http://${apiIp}:9464/metrics"; Report 'c2. web → api のメトリクス 9464（拒否）' ($r -eq 'timeout') $r
$r = FromApi $jaegerIp 16686; Report 'c3. api → jaeger の画面 16686（拒否）' ($r -eq 'timeout') $r
$r = FromApi '1.1.1.1' 443; Report 'c4. api → 外（1.1.1.1:443）（拒否）' ($r -eq 'timeout') $r

# d. Pod Security（restricted）が危険な Pod を断る。作らずに、サーバーの検査だけを受ける（--dry-run=server）
function TryPod([string]$name, [string]$securityContext) {
  $manifest = @"
apiVersion: v1
kind: Pod
metadata: { name: $name, namespace: $ns }
spec:
  automountServiceAccountToken: false
  securityContext: { seccompProfile: { type: RuntimeDefault } }
  containers:
    - name: c
      image: kids-play-api:local
      imagePullPolicy: Never
      securityContext: $securityContext
"@
  $out = $manifest | kubectl --context $context apply --dry-run=server -f - 2>&1
  return "$out"
}
# 特権と allowPrivilegeEscalation: false は同時に書けない（Kubernetes の形式の検査で先に断られ、規則の試験にならない）
$out = TryPod 'try-privileged' '{ privileged: true, runAsNonRoot: true, capabilities: { drop: [ALL] } }'
Report 'd1. 特権の Pod を断る' ($out -match 'violates PodSecurity') (($out -split "`n")[0])
$out = TryPod 'try-root' '{ runAsUser: 0, allowPrivilegeEscalation: false, capabilities: { drop: [ALL] } }'
Report 'd2. root の Pod を断る' ($out -match 'violates PodSecurity') (($out -split "`n")[0])
# 対照：規則を満たす Pod は通る（d1・d2 が「何でも断る」のでないことを確かめる）
$out = TryPod 'try-ok' '{ runAsNonRoot: true, runAsUser: 10001, allowPrivilegeEscalation: false, capabilities: { drop: [ALL] } }'
Report 'd3. 規則を満たす Pod は通る（対照）' ($out -match 'created \(server dry run\)') (($out -split "`n")[0])

# e. PC 側の入口は 127.0.0.1 だけ
$ports = docker port kids-play-control-plane
$open = $ports | Where-Object { $_ -notmatch '-> 127\.0\.0\.1:' }
Report 'e. ノードのポートは 127.0.0.1 だけ' (-not $open) (($ports -join '; '))

# f. トレースが Jaeger に届いている
1..3 | ForEach-Object { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:8081/api/storage/status?from=verify' | Out-Null }
$pf = Start-Process kubectl -ArgumentList "--context $context -n $ns port-forward deploy/jaeger 16686:16686 --address 127.0.0.1" -PassThru -WindowStyle Hidden
try {
  # Jaeger 2.22 では古い API（/api/traces）がなく、/api/v3 を使う（答えは OTLP の JSON の形）
  $from = [Uri]::EscapeDataString((Get-Date).ToUniversalTime().AddMinutes(-30).ToString('yyyy-MM-ddTHH:mm:ssZ'))
  $to = [Uri]::EscapeDataString((Get-Date).ToUniversalTime().AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ssZ'))
  $url = "http://127.0.0.1:16686/api/v3/traces?query.service_name=kids-play-api&query.start_time_min=$from&query.start_time_max=$to"
  $count = 0
  foreach ($i in 1..10) {
    Start-Sleep -Seconds 2
    try {
      $t = Invoke-RestMethod -TimeoutSec 5 $url
      $count = @($t.result.resourceSpans).Count
      if ($count -gt 0) { break }
    } catch { }
  }
  Report 'f. Jaeger に kids-play-api のトレースがある' ($count -gt 0) "traces=$count"
  if ($count -gt 0) {
    # C-37：届いた属性に、クエリの値が残っていない
    $json = $t | ConvertTo-Json -Depth 20
    Report 'f2. 届いたトレースにクエリの値がない' ($json -notmatch 'from=verify') ''
  }
} finally { Stop-Process -Id $pf.Id -ErrorAction SilentlyContinue }

# g. Trivy の設定検査（手元に Trivy のイメージがあるときだけ。CI では毎回行う）
$trivy = 'aquasec/trivy:0.76.0'
if (docker images -q $trivy) {
  $out = docker run --rm -v "${PWD}/k8s:/k8s:ro" $trivy config --severity HIGH,CRITICAL --exit-code 1 --quiet /k8s 2>&1
  Report 'g. Trivy の設定検査（HIGH・CRITICAL が0件）' ($LASTEXITCODE -eq 0) ''
  if ($LASTEXITCODE -ne 0) { $out | Write-Host }
} else {
  Write-Host "SKIP  g. Trivy のイメージ（$trivy）が手元にない。CI の結果で確かめる"
}

Write-Host ''
if ($failed -gt 0) { Write-Host "FAIL の数：$failed"; exit 1 }
Write-Host 'すべて PASS'

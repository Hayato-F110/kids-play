# kind のクラスター（kids-play）に、kids-play を入れる。20日目、KIDS-64。
# 使い方（リポジトリの一番上で、PowerShell）：
#   kind create cluster --name kids-play --config k8s/kind-config.yaml   # 最初の1回
#   ./scripts/k8s-up.ps1
# 片付け：kind delete cluster --name kids-play
#
# 順番に意味がある（kubectl apply -f k8s/ でまとめて入れると、名前の順に処理されて失敗する）：
#   1. Namespace（Pod Security の規則）を先に作る。中身はその規則で検査される
#   2. api と Jaeger を先に作る。nginx は起動のときに api の名前を引くので、web は後
#   3. 最後に NetworkPolicy。先に入れても動くが、通信を止める規則は「動いたあと」に足すと、
#      止まったのが規則のせいだと見分けやすい
$ErrorActionPreference = 'Stop'
$cluster = 'kids-play'
$context = "kind-$cluster"

function Invoke-Step([string]$label, [scriptblock]$block) {
  Write-Host "== $label"
  & $block
  if ($LASTEXITCODE -ne 0) { throw "失敗：$label（終了コード $LASTEXITCODE）" }
}

# 別のクラスターに誤って入れないよう、操作先を毎回名前で指定する
Invoke-Step 'イメージをビルドする（compose と同じ Dockerfile）' { docker compose build }
Invoke-Step 'イメージを kind のノードに入れる' { kind load docker-image kids-play-web:local kids-play-api:local --name $cluster }
Invoke-Step 'Namespace' { kubectl --context $context apply -f k8s/namespace.yaml }
Invoke-Step 'api と Jaeger' { kubectl --context $context apply -f k8s/api.yaml -f k8s/jaeger.yaml }
Invoke-Step 'api と Jaeger の起動を待つ' {
  kubectl --context $context -n kids-play rollout status deploy/api deploy/jaeger --timeout=180s
}
Invoke-Step 'web' { kubectl --context $context apply -f k8s/web.yaml }
# イメージを入れ直したときは、同じタグでも新しい中身を使うように作り直す
Invoke-Step '作り直し' { kubectl --context $context -n kids-play rollout restart deploy/api deploy/web }
Invoke-Step '起動を待つ' { kubectl --context $context -n kids-play rollout status deploy/api deploy/web --timeout=180s }
Invoke-Step 'NetworkPolicy' { kubectl --context $context apply -f k8s/networkpolicy.yaml }
Write-Host '完了：http://127.0.0.1:8081/ を開く。試験は ./scripts/k8s-verify.ps1'

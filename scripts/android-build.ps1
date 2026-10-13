# Androidアプリ（デバッグ版）を作る。-Install を付けると、USBでつないだ実機に入れる。
#
# 使い方（リポジトリの直下で、PowerShell）：
#   .\scripts\android-build.ps1            # frontend/ をコピーして、ビルドする
#   .\scripts\android-build.ps1 -Install   # ビルドして、実機に入れる
#
# なぜスクリプトにするか：Capacitor 8 が指定する Gradle 8.14 は、Java 25 以降では動かない。
# システムの Java や Android Studio 同梱の Java（25 以降）ではなく、Java 21 を、このビルドのときだけ指定する。
param(
  [switch]$Install
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Java 21 は、ユーザーフォルダの .jdks に置く（リポジトリの外）。版が上がっても動くように、jdk-21 で始まるフォルダを探す
$jdk = Get-ChildItem "$env:USERPROFILE\.jdks" -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue |
  Sort-Object Name -Descending |
  Select-Object -First 1
if (-not $jdk) {
  throw "Java 21 が見つかりません。$env:USERPROFILE\.jdks に、Eclipse Temurin 21 の zip を展開してください。"
}
$env:JAVA_HOME = $jdk.FullName
if (-not $env:ANDROID_HOME) {
  $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
}

Push-Location $root
try {
  # frontend/ の中身を、アプリの中（android/app/src/main/assets/public）にコピーする
  npx cap sync android
  if ($LASTEXITCODE -ne 0) { throw "cap sync に失敗しました。" }

  Push-Location android
  try {
    .\gradlew.bat assembleDebug --console=plain -q
    if ($LASTEXITCODE -ne 0) { throw "ビルドに失敗しました。" }
  } finally {
    Pop-Location
  }

  $apk = "android\app\build\outputs\apk\debug\app-debug.apk"
  Write-Output "できたファイル: $apk"

  if ($Install) {
    # -r は、入っているアプリを、データを残したまま入れ替える指定
    adb install -r $apk
    if ($LASTEXITCODE -ne 0) { throw "実機へのインストールに失敗しました。USBデバッグの接続を確認してください。" }
  }
} finally {
  Pop-Location
}

#!/bin/bash
# WSL（Ubuntu）で使う。clang と libclang-rt-dev と cppcheck が要る（make は使わない）
#   ./run.sh test        ふつうのテスト（サニタイザーつき）と、回帰の入力
#   ./run.sh fuzz [秒]   ファジング（既定で60秒）
#   ./run.sh check       cppcheck の静的解析
set -euo pipefail
cd "$(dirname "$0")"

# ASan：メモリの範囲外や解放後の利用を見つける。UBSan：未定義の動作を見つける。
# どちらも見つけたらすぐ止める（-fno-sanitize-recover）
SAN="-fsanitize=address,undefined -fno-sanitize-recover=all"
CFLAGS="-std=c11 -g -O1 -Wall -Wextra -Werror"
# 作ったものと、ファザーが見つけた入力（crash-*）、育てた入力（corpus）は build/ に置き、Git に入れない
BUILD=build

build() {
    mkdir -p "$BUILD"
    # shellcheck disable=SC2086
    clang $CFLAGS $SAN -o "$BUILD/test_tlv" test_tlv.c tlv.c
    # fuzzer：libFuzzer の main をつなぐ
    # shellcheck disable=SC2086
    clang $CFLAGS $SAN -fsanitize=fuzzer -o "$BUILD/fuzz_tlv" fuzz_tlv.c tlv.c
}

case "${1:-test}" in
    test)
        build
        "./$BUILD/test_tlv"
        # 回帰の入力（../regress/ の各ファイル）は、ファジングせずに1回ずつ試す
        "./$BUILD/fuzz_tlv" ../regress/*
        ;;
    fuzz)
        build
        mkdir -p "$BUILD/corpus"
        "./$BUILD/fuzz_tlv" -max_total_time="${2:-60}" -artifact_prefix="$BUILD/" "$BUILD/corpus" ../regress
        ;;
    check)
        cppcheck --enable=warning,style,performance,portability --error-exitcode=1 --std=c11 -q .
        ;;
    *)
        echo "使い方: $0 [test|fuzz [秒]|check]" >&2
        exit 2
        ;;
esac

/*
 * libFuzzer のハーネス。ファザーが作ったバイト列を、そのままパーサーに入れる。
 * ファイルを引数に渡すと、ファジングせずにそのファイルだけを試す（回帰テストに使う）
 */
#include "tlv.h"

#include <stddef.h>
#include <stdint.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 0;
    if (tlv_parse(data, size, recs, TLV_MAX_RECORDS, &count) != TLV_OK) {
        return 0;
    }
    /* 名前の欄を想定した小さな書き込み先。見つかった種類すべてで、取り出しを試す */
    char name[16];
    for (size_t i = 0; i < count; i++) {
        (void)tlv_get_string(recs, count, recs[i].type, name, sizeof name);
    }
    return 0;
}

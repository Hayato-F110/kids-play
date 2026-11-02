/* ふつうのテスト（決まった入力と、期待する結果）。Rust 版も同じ入力と期待で確かめる */
#include "tlv.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (!(cond)) {                                                  \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);     \
            failures++;                                                 \
        }                                                               \
    } while (0)

static void test_two_records(void)
{
    /* 種類1「hi」、種類2「abc」 */
    const uint8_t buf[] = {0x01, 0x00, 0x02, 'h', 'i', 0x02, 0x00, 0x03, 'a', 'b', 'c'};
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 0;
    CHECK(tlv_parse(buf, sizeof buf, recs, TLV_MAX_RECORDS, &count) == TLV_OK);
    CHECK(count == 2);

    char name[8];
    CHECK(tlv_get_string(recs, count, 2, name, sizeof name) == TLV_OK);
    CHECK(strcmp(name, "abc") == 0);
    CHECK(tlv_get_string(recs, count, 9, name, sizeof name) == TLV_ERR_NOT_FOUND);
}

static void test_empty(void)
{
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 99;
    CHECK(tlv_parse(NULL, 0, recs, TLV_MAX_RECORDS, &count) == TLV_OK);
    CHECK(count == 0);
}

static void test_truncated(void)
{
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 0;
    const uint8_t header_only[] = {0x01, 0x00};
    CHECK(tlv_parse(header_only, sizeof header_only, recs, TLV_MAX_RECORDS, &count) == TLV_ERR_TRUNCATED);
    /* 長さは5と言っているのに、値は2バイトしかない */
    const uint8_t short_value[] = {0x01, 0x00, 0x05, 'h', 'i'};
    CHECK(tlv_parse(short_value, sizeof short_value, recs, TLV_MAX_RECORDS, &count) == TLV_ERR_TRUNCATED);
}

static void test_too_many(void)
{
    /* 長さ0のレコードを17個並べる（上限は16） */
    uint8_t buf[(TLV_MAX_RECORDS + 1) * TLV_HEADER_SIZE] = {0};
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 0;
    CHECK(tlv_parse(buf, sizeof buf, recs, TLV_MAX_RECORDS, &count) == TLV_ERR_TOO_MANY);
}

static void test_too_long(void)
{
    /* 値が8バイト。書き込み先は4バイト */
    const uint8_t buf[] = {0x01, 0x00, 0x08, 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'};
    tlv_record_t recs[TLV_MAX_RECORDS];
    size_t count = 0;
    CHECK(tlv_parse(buf, sizeof buf, recs, TLV_MAX_RECORDS, &count) == TLV_OK);
    char small[4];
    CHECK(tlv_get_string(recs, count, 1, small, sizeof small) == TLV_ERR_TOO_LONG);
}

int main(void)
{
    test_two_records();
    test_empty();
    test_truncated();
    test_too_many();
    test_too_long();
    if (failures == 0) {
        printf("all tests passed\n");
    }
    return failures == 0 ? 0 : 1;
}

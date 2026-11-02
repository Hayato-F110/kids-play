#include "tlv.h"

#include <string.h>

tlv_result_t tlv_parse(const uint8_t *buf, size_t len, tlv_record_t *out, size_t max_out, size_t *count)
{
    size_t pos = 0;
    size_t n = 0;

    while (pos < len) {
        /* 見出し（種類と長さ）の3バイトが残っているか */
        if (len - pos < TLV_HEADER_SIZE) {
            return TLV_ERR_TRUNCATED;
        }
        uint8_t type = buf[pos];
        uint16_t length = (uint16_t)((buf[pos + 1] << 8) | buf[pos + 2]);
        pos += TLV_HEADER_SIZE;

        /* 値が、長さの分だけ残っているか。足し算はあふれうるので、引き算で比べる */
        if (length > len - pos) {
            return TLV_ERR_TRUNCATED;
        }
        if (n >= max_out) {
            return TLV_ERR_TOO_MANY;
        }
        out[n].type = type;
        out[n].length = length;
        out[n].value = &buf[pos];
        n++;
        pos += length;
    }

    *count = n;
    return TLV_OK;
}

tlv_result_t tlv_get_string(const tlv_record_t *records, size_t count, uint8_t type, char *dst, size_t dst_size)
{
    for (size_t i = 0; i < count; i++) {
        if (records[i].type != type) {
            continue;
        }
        /* 最後の NUL の分も要るので、値の長さと同じ大きさでは入らない（ファザーが見つけた。regress/ に入力あり） */
        if (records[i].length > dst_size) {
            return TLV_ERR_TOO_LONG;
        }
        memcpy(dst, records[i].value, records[i].length);
        dst[records[i].length] = '\0';
        return TLV_OK;
    }
    return TLV_ERR_NOT_FOUND;
}

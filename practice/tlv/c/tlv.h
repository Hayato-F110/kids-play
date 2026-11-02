/*
 * 小さな TLV（種類・長さ・値）のパーサー。17日目のファジングの題材（自作。会社のコードではない）。
 *
 * 1つのレコードの形：
 *   種類（1バイト）| 長さ（2バイト、ビッグエンディアン）| 値（長さのバイト数）
 * これがバッファの終わりまで並ぶ。
 */
#ifndef TLV_H
#define TLV_H

#include <stddef.h>
#include <stdint.h>

#define TLV_HEADER_SIZE 3u
#define TLV_MAX_RECORDS 16u

typedef enum {
    TLV_OK = 0,
    TLV_ERR_TRUNCATED = -1, /* レコードの途中でバッファが終わった */
    TLV_ERR_TOO_MANY = -2,  /* レコードの数が上限を超えた */
    TLV_ERR_NOT_FOUND = -3, /* 探した種類のレコードがない */
    TLV_ERR_TOO_LONG = -4,  /* 値が、書き込み先に入らない */
} tlv_result_t;

typedef struct {
    uint8_t type;
    uint16_t length;
    const uint8_t *value; /* 入力のバッファの中を指す。コピーしない */
} tlv_record_t;

/* buf を先頭から読み、レコードを out に並べる。読めた数を *count に入れる */
tlv_result_t tlv_parse(const uint8_t *buf, size_t len, tlv_record_t *out, size_t max_out, size_t *count);

/* 指定した種類の最初のレコードの値を、文字列（最後に NUL）として dst に写す */
tlv_result_t tlv_get_string(const tlv_record_t *records, size_t count, uint8_t type, char *dst, size_t dst_size);

#endif

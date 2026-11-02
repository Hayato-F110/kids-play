//! C 版（../c/tlv.c）と同じ仕様の TLV パーサー。17日目に、メモリ安全な言語との比較のために書き直した。
//!
//! 1つのレコードの形：種類（1バイト）| 長さ（2バイト、ビッグエンディアン）| 値（長さのバイト数）

pub const HEADER_SIZE: usize = 3;
pub const MAX_RECORDS: usize = 16;

#[derive(Debug, PartialEq, Eq)]
pub enum TlvError {
    Truncated,
    TooMany,
    NotFound,
    TooLong,
}

/// 値は入力のバッファを借りて指す（C 版のポインターと同じく、コピーしない）。
/// 借りている間は、入力のバッファを解放できないことをコンパイラーが保証する
#[derive(Debug, PartialEq, Eq)]
pub struct Record<'a> {
    pub kind: u8,
    pub value: &'a [u8],
}

pub fn parse(buf: &[u8]) -> Result<Vec<Record<'_>>, TlvError> {
    let mut records = Vec::new();
    let mut rest = buf;
    while !rest.is_empty() {
        // split_at_checked は、長さが足りなければ None を返す。範囲の外は読めない
        let (header, after) = rest.split_at_checked(HEADER_SIZE).ok_or(TlvError::Truncated)?;
        let length = usize::from(u16::from_be_bytes([header[1], header[2]]));
        let (value, after) = after.split_at_checked(length).ok_or(TlvError::Truncated)?;
        if records.len() >= MAX_RECORDS {
            return Err(TlvError::TooMany);
        }
        records.push(Record { kind: header[0], value });
        rest = after;
    }
    Ok(records)
}

/// C 版の tlv_get_string と同じく、値と最後の NUL を dst に写す。写した値の長さを返す
pub fn get_string(records: &[Record<'_>], kind: u8, dst: &mut [u8]) -> Result<usize, TlvError> {
    let record = records.iter().find(|r| r.kind == kind).ok_or(TlvError::NotFound)?;
    let length = record.value.len();
    if length >= dst.len() {
        return Err(TlvError::TooLong);
    }
    dst[..length].copy_from_slice(record.value);
    dst[length] = 0;
    Ok(length)
}

#[cfg(test)]
mod tests {
    use super::*;

    // C 版の test_tlv.c と同じ入力と期待

    #[test]
    fn two_records() {
        let buf = [0x01, 0x00, 0x02, b'h', b'i', 0x02, 0x00, 0x03, b'a', b'b', b'c'];
        let records = parse(&buf).unwrap();
        assert_eq!(records.len(), 2);
        let mut name = [0u8; 8];
        assert_eq!(get_string(&records, 2, &mut name), Ok(3));
        assert_eq!(&name[..4], b"abc\0");
        assert_eq!(get_string(&records, 9, &mut name), Err(TlvError::NotFound));
    }

    #[test]
    fn empty() {
        assert_eq!(parse(&[]).unwrap().len(), 0);
    }

    #[test]
    fn truncated() {
        assert_eq!(parse(&[0x01, 0x00]), Err(TlvError::Truncated));
        assert_eq!(parse(&[0x01, 0x00, 0x05, b'h', b'i']), Err(TlvError::Truncated));
    }

    #[test]
    fn too_many() {
        let buf = [0u8; (MAX_RECORDS + 1) * HEADER_SIZE];
        assert_eq!(parse(&buf), Err(TlvError::TooMany));
    }

    #[test]
    fn too_long() {
        let buf = [0x01, 0x00, 0x08, b'a', b'b', b'c', b'd', b'e', b'f', b'g', b'h'];
        let records = parse(&buf).unwrap();
        let mut small = [0u8; 4];
        assert_eq!(get_string(&records, 1, &mut small), Err(TlvError::TooLong));
    }

    /// C 版のハーネス（fuzz_tlv.c）と同じ動きを、回帰の入力（../regress/）の全ファイルで試す
    #[test]
    fn regress_inputs() {
        let dir = concat!(env!("CARGO_MANIFEST_DIR"), "/../regress");
        let mut tried = 0;
        for entry in std::fs::read_dir(dir).unwrap() {
            let data = std::fs::read(entry.unwrap().path()).unwrap();
            if let Ok(records) = parse(&data) {
                let mut name = [0u8; 16];
                for r in &records {
                    let _ = get_string(&records, r.kind, &mut name);
                }
            }
            tried += 1;
        }
        assert!(tried >= 2, "回帰の入力が見つからない");
    }

    /// C 版と同じ誤り（> と書く）を Rust で書いたらどうなるか。
    /// C では黙って隣のメモリを壊したが、Rust は範囲の外への書き込みを実行時に止める（panic）
    #[test]
    #[should_panic(expected = "index out of bounds")]
    fn same_mistake_panics_instead_of_corrupting() {
        let value = [b'x'; 16];
        let mut name = [0u8; 16];
        let length = value.len();
        if length > name.len() {
            return;
        }
        name[..length].copy_from_slice(&value);
        name[length] = 0;
    }
}

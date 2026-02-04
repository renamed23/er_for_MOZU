#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from collections import Counter
from pathlib import Path


def is_cp932_2byte(c: str) -> bool:
    try:
        b = c.encode("cp932")
    except UnicodeEncodeError:
        return False
    return len(b) == 2


def get_kanji_max_units() -> int:
    offset = ASCII_FIXED_TAIL.find("C1")
    return int(len(ASCII_FIXED_TAIL[offset:]) / 2) * 256


def get_ascii_free_units() -> int:
    offset = ASCII_FIXED_TAIL.find("N0")
    return 256 - int(len(ASCII_FIXED_TAIL[offset:]) / 2) - offset


JSON_PATH = Path("generated/translated.json")
OUT_PATH = Path("generated/system/System002")

# ASCII 区固定尾部
ASCII_FIXED_TAIL = "　N0N1/S/W/C/EC0C1C2C3C4C5C6C7C8C9/R/R/R/R/R/R/R/R/R"

ASCII_TOTAL_UNITS = 256
ASCII_FREE_UNITS = get_ascii_free_units()
KANJI_MAX_UNITS = get_kanji_max_units()


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    counter = Counter()

    for item in data:
        for key in ("name", "message"):
            text = item.get(key)
            if not text:
                continue
            for c in text:
                # 忽略 ASCII
                if ord(c) < 0x80 or c in ASCII_FIXED_TAIL:
                    continue
                if not is_cp932_2byte(c):
                    raise ValueError(f"不可用字符（非 CP932 双字节）: {repr(c)}")
                counter[c] += 1

    # 按出现次数排序（高 → 低）
    chars_sorted = [c for c, _ in counter.most_common()]

    ascii_chars = chars_sorted[:ASCII_FREE_UNITS]
    kanji_chars = chars_sorted[ASCII_FREE_UNITS:]

    if len(kanji_chars) > KANJI_MAX_UNITS:
        raise ValueError(
            f"汉字区溢出：{len(kanji_chars)} > {KANJI_MAX_UNITS}"
        )

    # 构造最终字符序列（字符单位）
    final_chars = []
    final_chars.extend(ascii_chars)
    final_chars.extend(ASCII_FIXED_TAIL)
    final_chars.extend(kanji_chars)

    # 写出 CP932 二进制
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_bin = bytearray()
    with OUT_PATH.open("wb") as f:
        for c in final_chars:
            out_bin.extend(c.encode("cp932"))
        f.write(out_bin)

    bin_size = len(out_bin)

    config = json.loads(
        Path("generated/config.json").read_text(encoding="utf-8"))
    config['ARG_CHARS_SIZE']['value'] = bin_size

    with open("generated/config.json", "w", encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("完成")
    print(f"ASCII 可用区使用: {len(ascii_chars)}")
    print(f"汉字区使用: {len(kanji_chars)}")
    print(f"总字符数: {len(final_chars)}")
    print(f"输出路径: {OUT_PATH}")


if __name__ == "__main__":
    main()

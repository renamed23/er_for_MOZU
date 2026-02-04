#!/usr/bin/env python3

import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
from utils_tools.libs.ops_lib import Handler, assemble_one_op, byte_slice, flat, h, parse_data, string, u32, u16, u8, i16, i8
from utils_tools.libs.translate_lib import collect_files, de, se


ascii_list: List[str] = []
hanzi_list: List[str] = []

ascii_map = {}
hanzi_map = {}


def read_from_system_file(path: str):
    global ascii_list, ascii_map, hanzi_list, hanzi_map
    chars = Path(path).read_bytes()
    ascii_bytes = chars[:512]
    for i in range(256):
        v = ascii_bytes[i * 2:(i+1) * 2].decode("CP932")
        ascii_list.append(v)
        ascii_map[v] = i

    hanzi_bytes = chars[512:]
    assert len(hanzi_bytes) % 2 == 0

    for i in range(int(len(hanzi_bytes) / 2)):
        v = hanzi_bytes[i * 2:(i+1) * 2].decode("CP932")
        hanzi_list.append(v)
        hanzi_map[v] = i


def decode_text(data: bytes, offset: int) -> Tuple[List[str], int]:
    message = ""
    tail = None
    while offset < len(data):
        ascii = ascii_list[data[offset]]
        if ascii == "/R":
            high = data[offset]
            low = data[offset + 1]
            index = (0xFF - high) * 0x100 + low
            message += hanzi_list[index]
            offset += 2
            continue
        # `/E`文本结束
        # `/C`非中断的文本换行
        # `/W`中断的文本换行，但是还是属于同一段话
        if ascii in ("/E", "/C", "/W"):
            offset += 1
            tail = ascii
            break
        message += ascii
        offset += 1
    assert tail != None
    return ([message, tail], offset)


def encode_text(s: str) -> bytes:
    out = bytearray()
    i = 0

    s_bytes = s.encode("CP932")

    assert len(s_bytes) % 2 == 0

    for i in range(int(len(s_bytes) / 2)):
        v = s_bytes[i * 2: (i+1) * 2].decode("CP932")
        if v in ascii_map:
            out.append(ascii_map[v])
            continue

        if v in hanzi_map:
            v_i = hanzi_map[v]
            high = 0xFF - (v_i // 0x100)
            low = v_i % 0x100
            out.append(high)
            out.append(low)
            continue

        raise ValueError(f"未知的字符{v}")

    return bytes(out)


def asm_one_op(op_entry: Dict) -> bytes:
    return assemble_one_op(op_entry, str_encoding=encode_text)


def i_str_handler(data: bytes, offset: int, ctx: Dict) -> Tuple[List[str], int]:
    return decode_text(data, offset)


i_str = Handler(i_str_handler)

UNKNOWN_BYTES = "19 01 05 F8 07 20 11 01 17 18 00 00 32 27 00 01 33 06 34 27 49 00 3B 01 26 04 04 18 0B 00 3B 00 26 04 04 34 27 49 01 3B 01 26 04 04 18 17 00 3B 00 26 04 04 34 27 49 02 3B 01 26 04 04 18 23 00 3B 00 26 04 04 34 27 49 03 3B 01 26 04 04 18 2F 00 3B 00 26 04 04 34 27 49 04 3B 01 26 04 04 18 3B 00 3B 00 26 04 04 34 27 49 05 3B 01 26 04 04 18 47 00 3B 00 26 04 04 34 27 49 06 3B 01 26 04 04 18 53 00 3B 00 26 04 04 34 27 49 07 3B 01 26 04 04 18 5F 00 3B 00 26 04 04 34 27 49 08 3B 01 26 04 04 18 6B 00 3B 00 26 04 04 34 27 49 09 3B 01 26 04 04 18 77 00 3B 00 26 04 04 34 27 49 0A 3B 01 26 04 04 18 83 00 3B 00 26 04 04 34 27 49 0B 3B 01 26 04 04 18 8F 00 3B 00 26 04 04 34 27 49 0C 3B 01 26 04 04 18 9B 00 3B 00 26 04 04 34 27 49 0D 3B 01 26 04 04 18 AC 00 19 00 16 2C 01 3B 00 26 03 05 1C 00"

OPCODES_MAP = flat({
    h("00"): [],
    h("05"): [u16],
    h("07"): [u8.repeat(4)],
    h("08"): [u8.repeat(4)],
    h("0B"): [u8.repeat(2)],
    h("0F"): [u8.repeat(4)],

    h("16"): [u16],
    h(UNKNOWN_BYTES): [],
    # 跳转文件OP, u16为目标文件的索引
    h("1A"): [u16],
    h("1C"): [],
    h("1E 1D"): [u8],

    h("20"): [u8, u8],
    h("22"): [],
    h("23"): [u8.repeat(2)],
    h("24"): [u8.repeat(3)],
    h("25 00 01 00"): [],
    h("27"): [u16],
    h("28"): [u8.repeat(3)],
    h("2A"): [u8],
    # 应该是和文本颜色相关的OP
    h("2B"): [u8.repeat(3)],
    h("2C"): [],
    h("2D 00 00 C8 00 02"): [],
    h("2E"): [u8.repeat(4)],
    h("2F"): [u8.repeat(2)],

    h("30"): [u8.repeat(2)],
    h("31"): [u8.repeat(2)],
    h("32"): [],
    h("33"): [u8],
    h("34"): [],
    h("3B"): [u8.repeat(4)],
    h("3F"): [u8],

    h("40"): [u8],
    h("42"): [],
    h("43"): [],
    # [文本] 普通文本/选项文本
    h("44"): [i_str],
    # [选项数量] u8为选项数量，接下来的`44`均为选项文本
    h("47"): [u8],
    h("48 03 FC 01 01 F4 01 01 FC 01 01 00 00 01"): [],
    h("49"): [u8, u16],
    # [文本] 名字文本
    h("4A"): [i_str],
    h("4B"): [u8],
    h("4E"): [u8],
})


def disasm_mode(input_path: str, output_path: str):
    """反汇编模式：将二进制文件转换为JSON"""
    read_from_system_file("system/System002")
    files = collect_files(input_path)

    for file in files:
        with open(file, "rb") as f:
            data = f.read()

        json_data: dict = {"size": len(data)}

        # 使用通用解析引擎和opcodes map
        json_data["opcodes"], offset = parse_data({
            "file_name": file,
            "offset": 0,
        }, data, OPCODES_MAP)

        assert offset == len(data)

        # 保存为JSON
        rel_path = os.path.relpath(file, start=input_path)
        out_file = os.path.join(output_path, rel_path + ".json")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)


def asm_mode(input_path: str, output_path: str):
    """汇编模式：将JSON转换回二进制文件"""
    read_from_system_file("generated/system/System002")
    files = collect_files(input_path, "json")

    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        new_blob = bytearray(b"".join([asm_one_op(op)
                             for op in json_data["opcodes"]]))

        if len(new_blob) > json_data["size"]:
            raise ValueError(
                f"{file}: 长度必须小于等于原始文件的长度 ({len(new_blob)} > {json_data['size']})")

        new_blob.extend(
            bytearray([0x00] * (json_data["size"] - len(new_blob))))

        # 保存二进制文件
        rel_path = os.path.relpath(file, start=input_path)
        rel_path = rel_path[:-5]  # 移除.json扩展名
        out_file = os.path.join(output_path, rel_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True)

        with open(out_file, 'wb') as f:
            f.write(new_blob)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='游戏脚本反汇编/汇编工具')
    parser.add_argument(
        'mode', choices=['disasm', 'asm'], help='模式: disasm(反汇编) 或 asm(汇编)')
    parser.add_argument('input', help='输入文件夹路径')
    parser.add_argument('output', help='输出文件夹路径')

    args = parser.parse_args()

    if args.mode == 'disasm':
        disasm_mode(args.input, args.output)
        print(f"反汇编完成: {args.input} -> {args.output}")
    elif args.mode == 'asm':
        asm_mode(args.input, args.output)
        print(f"汇编完成: {args.input} -> {args.output}")


if __name__ == "__main__":
    main()

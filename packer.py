#!/usr/bin/env python3

import argparse
from pathlib import Path


import argparse
import os
import struct
import sys
import re
from typing import List, Tuple


def read_offsets(fp) -> List[int]:
    """从文件开头读取 u32 偏移值直到遇到 0。

    返回值为一个 int 列表，包含所有在 0 之前读取到的偏移值。
    """
    offsets = []
    idx = 0
    while True:
        data = fp.read(4)
        if len(data) < 4:
            raise EOFError("在读取偏移表时意外到达文件末尾")
        val = struct.unpack('<I', data)[0]
        idx += 1
        if val == 0:
            break
        offsets.append(val)
    return offsets


def unpack(path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(path, 'rb') as f:
        filesize = os.path.getsize(path)
        # 读取偏移表直到 0
        f.seek(0)
        offsets = read_offsets(f)
        # 读取完 0 后的当前位置（头部长度）
        header_end = f.tell()

        if len(offsets) < 2:
            print("偏移表项不足，找不到可提取的文件。")
            return

        # 根据题主描述，偏移表第一个值应该等于 header_end，作为简单校验
        if offsets[0] != header_end:
            print(
                f"警告: 偏移表第一个值({offsets[0]}) != 偏移表结束后的第一个字节位置({header_end})。继续按偏移表提取。")

        # 按 offsets[i]..offsets[i+1] 提取，共 len(offsets)-1 个文件
        n_files = len(offsets) - 1
        base_name = os.path.splitext(os.path.basename(path))[0]
        pad_width = max(3, len(str(n_files)))

        for i in range(n_files):
            start = offsets[i]
            end = offsets[i+1]
            if start > filesize:
                print(f"第 {i+1} 个文件的起始偏移 {start} 超过文件长度 {filesize}，跳过。")
                continue
            if end > filesize:
                print(f"警告: 第 {i+1} 个文件的结束偏移 {end} 超过文件长度 {filesize}，截断到文件末尾。")
                end = filesize
            size = end - start
            if size < 0:
                print(f"警告: 第 {i+1} 个文件计算得到负大小 (start={start}, end={end})，跳过。")
                continue
            f.seek(start)
            data = f.read(size)
            out_name = f"{base_name}{str(i+1).zfill(pad_width)}"
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, 'wb') as out_f:
                out_f.write(data)
            print(f"写出: {out_path} ({size} bytes)")

        print(f"共提取 {n_files} 个文件到 {out_dir}")


def extract_trailing_number(filename: str) -> Tuple[int, bool]:
    """尝试从 filename（不含扩展名）尾部提取连续数字，返回 (number, True) 或 (0, False)
    例如 'Event001' -> (1, True)
    """
    stem = os.path.splitext(filename)[0]
    m = re.search(r'(\d+)$', stem)
    if m:
        return (int(m.group(1)), True)
    return (0, False)


def pack(folder: str, output: str) -> None:
    if not os.path.isdir(folder):
        print(f"目录不存在: {folder}")
        return
    files = [f for f in os.listdir(
        folder) if os.path.isfile(os.path.join(folder, f))]
    if not files:
        print("目录中没有可打包的文件。")
        return

    # 优先按文件名尾部数字排序
    numbered = []
    unnumbered = []
    for fn in files:
        num, ok = extract_trailing_number(fn)
        if ok:
            numbered.append((num, fn))
        else:
            unnumbered.append(fn)
    if numbered:
        numbered.sort(key=lambda x: x[0])
        ordered = [fn for _, fn in numbered] + sorted(unnumbered)
    else:
        ordered = sorted(files)

    # 读取所有文件大小
    sizes = []
    paths = []
    for fn in ordered:
        p = os.path.join(folder, fn)
        s = os.path.getsize(p)
        sizes.append(s)
        paths.append(p)

    n_files = len(sizes)
    # header 中实际写入的偏移个数为 n_files+1（包含最后的总长度），外加一个 0 终止 -> 共 n_files+2 个 u32
    header_u32_count = n_files + 2
    header_size = 4 * header_u32_count

    offsets = []
    cur = header_size
    for s in sizes:
        offsets.append(cur)
        cur += s
    # 最后一个偏移（总长度）
    offsets.append(cur)

    # 写入文件
    with open(output, 'wb') as out_f:
        # 写偏移表
        for v in offsets:
            out_f.write(struct.pack('<I', v))
        # 写 0 终止
        out_f.write(struct.pack('<I', 0))
        # 写入每个文件内容
        for p in paths:
            with open(p, 'rb') as in_f:
                data = in_f.read()
                out_f.write(data)

    print(f"已生成 {output}，包含 {n_files} 个文件，总字节数 {cur}（不含额外元数据）。")


def main():
    ap = argparse.ArgumentParser(
        description="packer 解包/打包工具")
    sub = ap.add_subparsers(dest='cmd', required=True)
    ap_unpack = sub.add_parser('unpack', help='解包')
    ap_unpack.add_argument('-i', '--input', required=True, help='输入')
    ap_unpack.add_argument('-o', '--out', required=True, help='输出')
    ap_pack = sub.add_parser('pack', help='打包')
    ap_pack.add_argument('-i', '--input', required=True, help='输入')
    ap_pack.add_argument('-o', '--out', required=True, help='输出')
    args = ap.parse_args()
    if args.cmd == 'unpack':
        unpack(args.input, args.out)
    elif args.cmd == 'pack':
        pack(args.input, args.out)


if __name__ == '__main__':
    main()

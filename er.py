#!/usr/bin/env python3

import os
import json
import argparse
import re
from typing import List, Dict, Optional, Tuple
from utils_tools.libs import translate_lib


names = dict()


def save_names() -> List[Dict]:
    results: List[Dict] = []
    for n in names.keys():
        results.append({"message": n, "is_name": True, "raw_name": n})
    return results


def load_names(text: List[Dict[str, str]],
               trans_index: int) -> int:
    global names
    while trans_index < len(text):
        item = text[trans_index]
        if "is_name" in item and item["is_name"]:
            names[item["raw_name"]] = item["message"]
            trans_index += 1
        else:
            break

    return trans_index


def extract_strings_from_file(file_path: str) -> List[Dict]:
    """
    扫描单文件，提取字符串。
    返回的 results: 每项至少包含 'message'；若该对话有角色名则包含 'name'。
    """
    results: List[Dict] = []
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    current_name = ""
    select_count = 0
    last_message = None

    for op in json_data["opcodes"]:
        if op["op"] == "47":
            assert select_count == 0
            select_count, _ = translate_lib.de(op["value"][0])

        if op["op"] == "4A":
            current_name = op["value"][0]
            names[current_name] = ""

        if op["op"] == "44":
            if op["value"][1] == "/C":  # 合并换行的段
                assert select_count == 0
                if last_message:
                    last_message += op["value"][0]
                else:
                    last_message = op["value"][0]
                continue

            item: dict = {"path": file_path}

            if last_message:
                assert select_count == 0
                item["message"] = last_message + op["value"][0]
                item["merged"] = True
                last_message = None
            else:
                item["message"] = op["value"][0]

            if item["message"].startswith("　"):
                item["need_whitespace"] = True

            if current_name:
                item["name"] = current_name
            if select_count > 0:
                item["is_select"] = True
                select_count -= 1
            results.append(item)

    return results


def extract_strings(path: str, output_file: str):
    files = translate_lib.collect_files(path)
    results = []
    for file in files:
        results.extend(extract_strings_from_file(file))

    final_result = save_names()
    final_result.extend(results)
    print(f"提取了 {len(final_result)} 项")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, indent=2, ensure_ascii=False)

# ========== 替换 ==========


def replace_in_file(
    file_path: str,
    text: List[Dict[str, str]],
    output_dir: str,
    trans_index: int,
    base_root: str
) -> int:
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    new_opcodes = []

    for op in json_data["opcodes"]:
        if op["op"] == "44":
            # 需要换行合并的段，忽略，不消耗译文
            if op["value"][1] == "/C":
                continue

            # 最终行（可能是合并后的）
            trans_item = text[trans_index]
            trans_index += 1

            op["value"][0] = trans_item["message"]

        if op["op"] == "4A":
            # 名字替换
            op["value"][0] = names[op["value"][0]]

        new_opcodes.append(op)

    json_data["opcodes"] = new_opcodes

    # ---------- 保存 ----------
    rel = os.path.relpath(file_path, start=base_root)
    out_path = os.path.join(output_dir, rel)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return trans_index


def replace_strings(path: str, text_file: str, output_dir: str):
    with open(text_file, 'r', encoding='utf-8') as f:
        text = json.load(f)
    files = translate_lib.collect_files(path)
    trans_index = 0
    trans_index = load_names(text, trans_index)

    for file in files:
        trans_index = replace_in_file(
            file, text, output_dir, trans_index, base_root=path)
        print(f"已处理: {file}")
    if trans_index != len(text):
        print(f"错误: 有 {len(text)} 项译文，但只消耗了 {trans_index}。")
        exit(1)

# ---------------- main ----------------


def main():
    parser = argparse.ArgumentParser(description='文件提取和替换工具')
    subparsers = parser.add_subparsers(
        dest='command', help='功能选择', required=True)

    ep = subparsers.add_parser('extract', help='解包文件提取文本')
    ep.add_argument('--path', required=True, help='文件夹路径')
    ep.add_argument('--output', default='raw.json', help='输出JSON文件路径')

    rp = subparsers.add_parser('replace', help='替换解包文件中的文本')
    rp.add_argument('--path', required=True, help='文件夹路径')
    rp.add_argument('--text', default='translated.json', help='译文JSON文件路径')
    rp.add_argument('--output-dir', default='translated',
                    help='输出目录(默认: translated)')

    args = parser.parse_args()
    if args.command == 'extract':
        extract_strings(args.path, args.output)
        print(f"提取完成! 结果保存到 {args.output}")
    elif args.command == 'replace':
        replace_strings(args.path, args.text, args.output_dir)
        print(f"替换完成! 结果保存到 {args.output_dir} 目录")


if __name__ == '__main__':
    main()

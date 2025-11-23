import argparse
import csv
import json
import sys
from typing import List, Dict, Any

INSTRUCTION_SET = {
    "LOAD_CONST": (0x01, 5, ["A", "B", "CONST"]),
    "READ_MEM":   (0x02, 3, ["A", "B", "OFFSET"]),
    "WRITE_MEM":  (0x03, 3, ["A", "B", "OFFSET"]),
    "POPCT":      (0x04, 1, ["A"]),
}


def parse_value(s: str):
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    return int(s)


def load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Удаляем BOM и пробелы у имени колонок
        clean_fieldnames = [name.lstrip("\ufeff").strip() for name in reader.fieldnames]
        reader.fieldnames = clean_fieldnames

        rows = []
        for row in reader:
            clean_row = {
                (k.lstrip("\ufeff").strip() if k else k): v.strip() if isinstance(v, str) else v
                for k, v in row.items()
            }
            rows.append(clean_row)
        return rows


def assemble_instruction(row: Dict[str, str], lineno: int) -> Dict[str, Any]:
    mnemonic = row.get("mnemonic", "").upper()

    if mnemonic == "":
        raise ValueError(f"Empty mnemonic at line {lineno}")

    if mnemonic not in INSTRUCTION_SET:
        raise ValueError(f"Unknown mnemonic '{mnemonic}' at line {lineno}")

    opcode, size, fields = INSTRUCTION_SET[mnemonic]

    parsed_fields = {}
    for f in fields:
        raw = row.get(f, "")
        val = parse_value(raw)
        parsed_fields[f] = val

    return {
        "mnemonic": mnemonic,
        "opcode": opcode,
        "size": size,
        "fields": parsed_fields,
        "src_line": lineno,
    }


def generate_binary(ir_list: List[Dict[str, Any]]) -> bytes:
    out = bytearray()

    for instr in ir_list:
        out.append(instr["opcode"] & 0xFF)

        for _, value in instr["fields"].items():
            if value is None:
                out.extend((0).to_bytes(4, "little"))
            else:
                out.extend(int(value).to_bytes(4, "little"))

    return bytes(out)


def print_binary_readable(binary: bytes):
    print("Binary dump:")
    for i, b in enumerate(binary):
        print(f"{b:02X}", end=" ")
        if (i + 1) % 16 == 0:
            print()
    print("\nTotal bytes:", len(binary))


def print_ir_readable(ir_list: List[Dict[str, Any]]):
    for idx, instr in enumerate(ir_list, start=1):
        print(f"Инструкция #{idx}: {instr['mnemonic']} (opcode=0x{instr['opcode']:02X}, size={instr['size']})")

        for name, value in instr["fields"].items():
            if value is None:
                print(f"  {name}: <None>")
            else:
                print(f"  {name}: {value} (0x{value:X})")

        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(description="CSV → binary assembler")
    parser.add_argument("input", help="Path to input CSV file")
    parser.add_argument("output", help="Path to output binary file")
    parser.add_argument("--test", action="store_true", help="Print assembled binary instead of saving")

    args = parser.parse_args()

    rows = load_csv(args.input)

    ir_list = []
    for i, row in enumerate(rows, start=1):
        try:
            ir = assemble_instruction(row, i)
            ir_list.append(ir)
        except Exception as e:
            print(f"[ERROR] line {i}: {e}", file=sys.stderr)
            sys.exit(1)

    binary = generate_binary(ir_list)

    # TEST MODE — print byte dump
    if args.test:
        print_binary_readable(binary)
        return

    # NORMAL MODE — save file
    with open(args.output, "wb") as f:
        f.write(binary)

    print(f"OK: {len(binary)} bytes written to {args.output}")


if __name__ == "__main__":
    main()

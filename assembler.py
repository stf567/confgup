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


class SimpleUVM:
    def __init__(self):
        self.data_mem = [0] * 65536  # 64 KB данных
        self.registers = [0] * 8     # 8 регистров
        self.pc = 0

    def load_program(self, binary: bytes):
        self.program = binary

    def fetch_byte(self):
        b = self.program[self.pc]
        self.pc += 1
        return b

    def fetch_word(self):
        w = int.from_bytes(self.program[self.pc:self.pc + 4], "little")
        self.pc += 4
        return w

    def run(self):
        while self.pc < len(self.program):
            opcode = self.fetch_byte()

            if opcode == 0x01:  # LOAD_CONST
                A = self.fetch_word()
                B = self.fetch_word()
                CONST = self.fetch_word()
                self.registers[A] = CONST

            elif opcode == 0x02:  # READ_MEM
                A = self.fetch_word()
                B = self.fetch_word()
                OFFSET = self.fetch_word()
                addr = self.registers[B] + OFFSET
                self.registers[A] = self.data_mem[addr]

            elif opcode == 0x03:  # WRITE_MEM
                A = self.fetch_word()
                B = self.fetch_word()
                OFFSET = self.fetch_word()
                addr = self.registers[B] + OFFSET
                self.data_mem[addr] = self.registers[A]

            elif opcode == 0x04:  # POPCT
                A = self.fetch_word()
                self.registers[A] = bin(self.registers[A]).count("1")

            else:
                print(f"ERROR: Unknown opcode 0x{opcode:02X}")
                break

def dump_memory(path: str, data_mem, start: int, end: int):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["address", "value"])
        for addr in range(start, end + 1):
            writer.writerow([addr, data_mem[addr]])


def main():
    parser = argparse.ArgumentParser(description="CSV assembler + UVM interpreter")

    parser.add_argument("input", help="Input CSV or BIN file")
    parser.add_argument("output", help="Output file")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--run", action="store_true", help="Run interpreter instead of assembling")
    parser.add_argument("--dump-start", type=int, default=0)
    parser.add_argument("--dump-end", type=int, default=0)

    args = parser.parse_args()

    if args.run:
        with open(args.input, "rb") as f:
            binary = f.read()

        uvm = SimpleUVM()
        uvm.load_program(binary)
        uvm.run()

        dump_memory(args.output, uvm.data_mem, args.dump_start, args.dump_end)

        print("DONE: memory dump saved.")
        return

    rows = load_csv(args.input)
    ir_list = []
    for i, row in enumerate(rows, start=1):
        ir = assemble_instruction(row, i)
        ir_list.append(ir)

    binary = generate_binary(ir_list)

    if args.test:
        print("Binary dump:")
        print(" ".join(f"{b:02X}" for b in binary))
        return

    with open(args.output, "wb") as f:
        f.write(binary)

    print(f"OK: {len(binary)} bytes written to {args.output}")


if __name__ == "__main__":
    main()

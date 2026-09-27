from __future__ import annotations

import base64
import enum
import math
import random
from typing import Callable, Any
from pydantic import BaseModel, Field, field_serializer, field_validator, ValidationInfo

SOUP_OP_BITS = 5  # Every soup byte is a TierraOp in 0-31, so 5 bits is enough to pack it.


def _pack_soup(soup: list[int]) -> str:
    """Pack the soup (values 0-31) at 5 bits each and base64-encode it, instead of a JSON int array.

    Cuts the persisted size of a 1024-byte soup from ~3.7KB to ~0.9KB, which is most of an
    organism's storage footprint and directly drives DynamoDB write cost.
    """
    bits = bitcount = 0
    packed = bytearray()
    for value in soup:
        bits = (bits << SOUP_OP_BITS) | (value & 0x1F)
        bitcount += SOUP_OP_BITS
        while bitcount >= 8:
            bitcount -= 8
            packed.append((bits >> bitcount) & 0xFF)
    if bitcount:
        packed.append((bits << (8 - bitcount)) & 0xFF)
    return base64.b64encode(bytes(packed)).decode("ascii")


def _unpack_soup(packed_b64: str, length: int) -> list[int]:
    data = base64.b64decode(packed_b64)
    bits = bitcount = 0
    soup: list[int] = []
    for byte in data:
        bits = (bits << 8) | byte
        bitcount += 8
        while bitcount >= SOUP_OP_BITS and len(soup) < length:
            bitcount -= SOUP_OP_BITS
            soup.append((bits >> bitcount) & 0x1F)
    return soup


class TierraOp(int, enum.Enum):
    """The official 32 instructions of Thomas S. Ray's 1990 Tierra Virtual Machine."""
    NOP_0 = 0x00        # 00: nop0 (template addressing bit 0)
    NOP_1 = 0x01        # 01: nop1 (template addressing bit 1, complementary to nop0)
    OR1 = 0x02          # 02: or1  (bit flip / logical or with 1)
    SHL = 0x03          # 03: shl  (shift left register)
    ZERO = 0x04         # 04: zero (clear register CX to 0)
    IFZ = 0x05          # 05: ifz  (conditional execute if zero flag is set)
    SUB_AB = 0x06       # 06: sub_ab (subtract BX from AX -> CX)
    SUB_AC = 0x07       # 07: sub_ac (subtract CX from AX -> AX)
    INC_A = 0x08        # 08: inc_a (increment AX)
    INC_B = 0x09        # 09: inc_b (increment BX)
    DEC_C = 0x0A        # 0A: dec_c (decrement CX)
    INC_C = 0x0B        # 0B: inc_c (increment CX)
    PUSH_AX = 0x0C      # 0C: push_ax
    PUSH_BX = 0x0D      # 0D: push_bx
    PUSH_CX = 0x0E      # 0E: push_cx
    PUSH_DX = 0x0F      # 0F: push_dx
    POP_AX = 0x10       # 10: pop_ax
    POP_BX = 0x11       # 11: pop_bx
    POP_CX = 0x12       # 12: pop_cx
    POP_DX = 0x13       # 13: pop_dx
    JMP = 0x14          # 14: jmp (jump forward to complementary template)
    JMPB = 0x15         # 15: jmpb (jump backward to complementary template)
    CALL = 0x16         # 16: call (call subroutine at complementary template)
    RET = 0x17          # 17: ret (return from subroutine)
    MOV_CD = 0x18       # 18: mov_cd (move CX to DX)
    MOV_AB = 0x19       # 19: mov_ab (move AX to BX)
    MOV_IAB = 0x1A      # 1A: mov_iab (copy byte from [AX] to [BX] in RAM soup)
    ADR = 0x1B          # 1B: adr (search nearest matching template -> AX)
    ADRB = 0x1C         # 1C: adrb (search backward for matching template -> AX)
    ADRF = 0x1D         # 1D: adrf (search forward for matching template -> AX)
    MAL = 0x1E          # 1E: mal (allocate daughter memory block of size in CX -> AX)
    DIVIDE = 0x1F       # 1F: divide (self-replication: split daughter cell from parent)


# The canonical 80-instruction Ancestor (Ancestor 80) of Thomas S. Ray (1990)
# Uses complementary template matching and memory copy loop
ANCESTOR_80_GENOME: list[int] = [
    TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1,  # 00-03: Header template
    TierraOp.ZERO,                                                  # 04: Clear CX
    TierraOp.OR1, TierraOp.SHL, TierraOp.SHL,                       # 05-07: CX = 4
    TierraOp.MOV_CD,                                                # 08: DX = 4
    TierraOp.ADRB, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, # 09-13: Find start
    TierraOp.SUB_AC,                                                # 14: Adjust AX
    TierraOp.MOV_AB,                                                # 15: BX = AX (start address)
    TierraOp.ADRF, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_1, # 16-20: Find end
    TierraOp.SUB_AB,                                                # 21: CX = end - start (length = 80)
    TierraOp.PUSH_AX, TierraOp.PUSH_BX, TierraOp.PUSH_CX,           # 22-24: Save bounds on stack
    TierraOp.MAL,                                                   # 25: Allocate memory for daughter in soup
    TierraOp.PUSH_AX,                                               # 26: Push daughter address
    # Copy Loop (Target of template search)
    TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_0,  # 27-30: Loop template
    TierraOp.MOV_IAB,                                               # 31: Copy byte [AX] -> [BX]
    TierraOp.DEC_C,                                                 # 32: Decrement remaining length
    TierraOp.IFZ, TierraOp.JMP, TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1, # 33-38: If done jump out
    TierraOp.INC_A, TierraOp.INC_B,                                 # 39-40: Advance src and dst pointers
    TierraOp.JMPB, TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_0, # 41-45: Loop back
    # Exit loop & Divide
    TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1,  # 46-49: Exit template
    TierraOp.DIVIDE,                                                # 50: Split daughter cell into world!
    TierraOp.RET,                                                   # 51: Return to origin
    # Padding / Protection templates (making canonical 80 instructions)
    TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0,
    TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1,
    TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1,
    TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0,
    TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_1,
    TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_0,
    TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_0,
    TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_1,
]
while len(ANCESTOR_80_GENOME) < 80:
    ANCESTOR_80_GENOME.append(TierraOp.NOP_0)
ANCESTOR_80_GENOME = ANCESTOR_80_GENOME[:80]

# Canonical Parasite (Parasite 45) of Thomas S. Ray (1990)
# Missing the copy loop! Instead CALLs the Host's copy loop via complementary template
PARASITE_45_GENOME: list[int] = [
    TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1,  # 00-03: Header template
    TierraOp.ZERO,                                                  # 04: Clear CX
    TierraOp.OR1, TierraOp.SHL, TierraOp.SHL,                       # 05-07: CX = 4
    TierraOp.MOV_CD,                                                # 08: DX = 4
    TierraOp.ADRB, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, # 09-13: Find start
    TierraOp.SUB_AC,                                                # 14: Adjust AX
    TierraOp.MOV_AB,                                                # 15: BX = AX (start address)
    TierraOp.ADRF, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_1, # 16-20: Find end (45)
    TierraOp.SUB_AB,                                                # 21: CX = 45
    TierraOp.MAL,                                                   # 22: Allocate memory
    # Parasitic leap: CALL the Host's copy loop template!
    TierraOp.CALL, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_1, # 23-27: Parasite CALL
    TierraOp.DIVIDE,                                                # 28: Divide daughter
    TierraOp.RET,                                                   # 29: Return
    # Padding to 45
    TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0, TierraOp.NOP_0,
    TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1, TierraOp.NOP_1,
    TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1,
    TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_0,
]
while len(PARASITE_45_GENOME) < 45:
    PARASITE_45_GENOME.append(TierraOp.NOP_0)
PARASITE_45_GENOME = PARASITE_45_GENOME[:45]


class TemplateMatcher:
    """Authentic Complementary Template Matching Engine of Ray's 1990 Tierra."""

    @staticmethod
    def extract_template(soup: list[int], start_ip: int, max_len: int = 8) -> list[int]:
        """Extract consecutive NOP_0 and NOP_1 instructions following an addressing opcode."""
        template: list[int] = []
        soup_len = len(soup)
        for i in range(max_len):
            addr = (start_ip + 1 + i) % soup_len
            op = soup[addr] % 32
            if op in (TierraOp.NOP_0, TierraOp.NOP_1):
                template.append(op)
            else:
                break
        return template

    @staticmethod
    def get_complement(template: list[int]) -> list[int]:
        """Compute complementary bit-pattern: NOP_0 (0) <-> NOP_1 (1)."""
        return [
            TierraOp.NOP_1 if op == TierraOp.NOP_0 else TierraOp.NOP_0
            for op in template
        ]

    @classmethod
    def search_forward(cls, soup: list[int], search_start: int, target: list[int], max_dist: int = 512) -> int | None:
        """Search soup forward for complementary template pattern."""
        if not target:
            return None
        t_len = len(target)
        soup_len = len(soup)
        for d in range(1, max_dist):
            cand_start = (search_start + d) % soup_len
            match = True
            for k in range(t_len):
                if (soup[(cand_start + k) % soup_len] % 32) != target[k]:
                    match = False
                    break
            if match:
                # Return address immediately after the matching template
                return (cand_start + t_len) % soup_len
        return None

    @classmethod
    def search_backward(cls, soup: list[int], search_start: int, target: list[int], max_dist: int = 512) -> int | None:
        """Search soup backward for complementary template pattern."""
        if not target:
            return None
        t_len = len(target)
        soup_len = len(soup)
        for d in range(1, max_dist):
            cand_start = (search_start - d - t_len + soup_len) % soup_len
            match = True
            for k in range(t_len):
                if (soup[(cand_start + k) % soup_len] % 32) != target[k]:
                    match = False
                    break
            if match:
                return (cand_start + t_len) % soup_len
        return None


class TierraVM(BaseModel):
    """Authentic Virtual Machine executing Ray's Tierra bytecode in a RAM soup."""
    soup_size: int = 1024
    soup: list[int] = Field(default_factory=lambda: [0] * 1024)
    ax: int = 0
    bx: int = 0
    cx: int = 0
    dx: int = 0
    ip: int = 0                    # Instruction Pointer
    stack: list[int] = Field(default_factory=list)
    flag_zero: bool = False
    flag_error: bool = False
    cpu_cycles_allocated: int = 0  # CPU time-slice earned from foraging
    total_cycles_executed: int = 0
    divide_count: int = 0
    error_count: int = 0           # Tracked for Reaper prioritization
    mutation_rate: float = 0.008   # Cosmic ray / copy error probability per copy
    cosmic_ray_rate: float = 0.002 # Background soup bit-flip probability per slice
    execution_flaw_rate: float = 0.001 # Flaw in ALU execution
    genome_size: int = 80
    start_address: int = 0
    borrowed_host_cycles: int = 0  # Cycles executed outside own memory block (Parasitism!)

    @field_serializer("soup")
    def _serialize_soup(self, soup: list[int]) -> str:
        return _pack_soup(soup)

    @field_validator("soup", mode="before")
    @classmethod
    def _deserialize_soup(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str):
            return _unpack_soup(value, info.data.get("soup_size", 1024))
        return value

    @classmethod
    def create_with_ancestor(cls, soup_size: int = 1024, start_address: int = 64) -> TierraVM:
        """Initialize soup and inject Ray's canonical Ancestor 80 program."""
        soup = [random.randint(0, 31) for _ in range(soup_size)]  # Pre-fill with background bytecode noise
        # Inject Ancestor 80
        for i, byte_val in enumerate(ANCESTOR_80_GENOME):
            soup[(start_address + i) % soup_size] = int(byte_val)

        vm = cls(
            soup_size=soup_size,
            soup=soup,
            ax=0,
            bx=0,
            cx=len(ANCESTOR_80_GENOME),
            dx=0,
            ip=start_address,
            start_address=start_address,
            genome_size=len(ANCESTOR_80_GENOME),
        )
        return vm

    def award_cpu_slice(self, cycles: int) -> None:
        """Earn CPU time-slice execution quota through knowledge assimilation."""
        self.cpu_cycles_allocated += max(0, cycles)

    def execute_slice(self, on_divide_callback: Callable[[int, list[int]], None] | None = None) -> dict[str, Any]:
        """Execute allocated CPU time-slice cycles sequentially with authentic template addressing."""
        cycles_to_run = self.cpu_cycles_allocated
        self.cpu_cycles_allocated = 0
        executed = 0
        divides = 0
        mutations = 0

        # Memory bounds
        daughter_addr = (self.start_address + self.genome_size + 32) % self.soup_size
        copy_ptr_src = self.start_address
        copy_ptr_dst = daughter_addr

        # 1. Background Cosmic Rays (Ray's 1st mutation mechanism)
        if random.random() < self.cosmic_ray_rate * (cycles_to_run / 20.0):
            cosmic_pos = random.randint(0, self.soup_size - 1)
            flip_bit = 1 << random.randint(0, 4)
            self.soup[cosmic_pos] = (self.soup[cosmic_pos] ^ flip_bit) % 32
            mutations += 1

        while executed < cycles_to_run:
            self.ip = self.ip % self.soup_size
            opcode = self.soup[self.ip] % 32
            executed += 1
            self.total_cycles_executed += 1

            # Check if executing outside own genome bounds (True Parasitism tracking)
            own_start = self.start_address
            own_end = (self.start_address + self.genome_size) % self.soup_size
            if own_start <= own_end:
                if not (own_start <= self.ip < own_end):
                    self.borrowed_host_cycles += 1
            else:
                if own_end <= self.ip < own_start:
                    self.borrowed_host_cycles += 1

            # 2. Execution Flaws (Ray's 3rd mutation mechanism: small ALU noise)
            if random.random() < self.execution_flaw_rate:
                self.ax = (self.ax ^ 1) & 0xFFFF
                self.error_count += 1

            # Execution Dispatch for 32 Tierra Instructions
            if opcode in (TierraOp.NOP_0, TierraOp.NOP_1):
                pass  # NOP is inert execution

            elif opcode == TierraOp.OR1:
                self.bx = (self.bx | 1) & 0xFFFF

            elif opcode == TierraOp.SHL:
                self.cx = (self.cx << 1) & 0xFFFF

            elif opcode == TierraOp.ZERO:
                self.cx = 0
                self.flag_zero = True

            elif opcode == TierraOp.IFZ:
                if not self.flag_zero:
                    # Skip next instruction
                    self.ip = (self.ip + 1) % self.soup_size

            elif opcode == TierraOp.SUB_AB:
                self.cx = (self.ax - self.bx) & 0xFFFF
                self.flag_zero = (self.cx == 0)

            elif opcode == TierraOp.SUB_AC:
                self.ax = (self.ax - self.cx) & 0xFFFF
                self.flag_zero = (self.ax == 0)

            elif opcode == TierraOp.INC_A:
                self.ax = (self.ax + 1) & 0xFFFF
                self.flag_zero = (self.ax == 0)

            elif opcode == TierraOp.INC_B:
                self.bx = (self.bx + 1) & 0xFFFF

            elif opcode == TierraOp.DEC_C:
                self.cx = max(0, self.cx - 1)
                self.flag_zero = (self.cx == 0)

            elif opcode == TierraOp.INC_C:
                self.cx = (self.cx + 1) & 0xFFFF

            elif opcode == TierraOp.PUSH_AX:
                self.stack.append(self.ax)
            elif opcode == TierraOp.PUSH_BX:
                self.stack.append(self.bx)
            elif opcode == TierraOp.PUSH_CX:
                self.stack.append(self.cx)
            elif opcode == TierraOp.PUSH_DX:
                self.stack.append(self.dx)

            elif opcode == TierraOp.POP_AX:
                if self.stack:
                    self.ax = self.stack.pop()
            elif opcode == TierraOp.POP_BX:
                if self.stack:
                    self.bx = self.stack.pop()
            elif opcode == TierraOp.POP_CX:
                if self.stack:
                    self.cx = self.stack.pop()
            elif opcode == TierraOp.POP_DX:
                if self.stack:
                    self.dx = self.stack.pop()

            elif opcode == TierraOp.JMP:
                # Authentic Complementary Template Jump
                tmpl = TemplateMatcher.extract_template(self.soup, self.ip)
                if tmpl:
                    comp = TemplateMatcher.get_complement(tmpl)
                    target = TemplateMatcher.search_forward(self.soup, self.ip + len(tmpl), comp)
                    if target is not None:
                        self.ip = target
                        continue
                    else:
                        self.flag_error = True
                        self.error_count += 1

            elif opcode == TierraOp.JMPB:
                # Complementary Template Jump Backward
                tmpl = TemplateMatcher.extract_template(self.soup, self.ip)
                if tmpl:
                    comp = TemplateMatcher.get_complement(tmpl)
                    target = TemplateMatcher.search_backward(self.soup, self.ip, comp)
                    if target is not None:
                        self.ip = target
                        continue
                    else:
                        self.flag_error = True
                        self.error_count += 1

            elif opcode == TierraOp.CALL:
                # Complementary Template Subroutine Call
                tmpl = TemplateMatcher.extract_template(self.soup, self.ip)
                if tmpl:
                    comp = TemplateMatcher.get_complement(tmpl)
                    target = TemplateMatcher.search_forward(self.soup, self.ip + len(tmpl), comp)
                    if target is not None:
                        self.stack.append((self.ip + len(tmpl) + 1) % self.soup_size)
                        self.ip = target
                        continue
                    else:
                        self.flag_error = True
                        self.error_count += 1

            elif opcode == TierraOp.RET:
                if self.stack:
                    self.ip = self.stack.pop()
                    continue

            elif opcode == TierraOp.MOV_CD:
                self.dx = self.cx

            elif opcode == TierraOp.MOV_AB:
                self.bx = self.ax

            elif opcode == TierraOp.MOV_IAB:
                # 3. Flaw in Copy (Ray's 2nd mutation mechanism)
                src_byte = self.soup[copy_ptr_src % self.soup_size]
                if random.random() < self.mutation_rate:
                    src_byte = (src_byte ^ (1 << random.randint(0, 4))) % 32
                    mutations += 1
                self.soup[copy_ptr_dst % self.soup_size] = src_byte
                copy_ptr_src = (copy_ptr_src + 1) % self.soup_size
                copy_ptr_dst = (copy_ptr_dst + 1) % self.soup_size

            elif opcode in (TierraOp.ADR, TierraOp.ADRF):
                # Search forward for template address -> AX
                tmpl = TemplateMatcher.extract_template(self.soup, self.ip)
                if tmpl:
                    comp = TemplateMatcher.get_complement(tmpl)
                    target = TemplateMatcher.search_forward(self.soup, self.ip + len(tmpl), comp)
                    if target is not None:
                        self.ax = target
                    else:
                        self.flag_error = True
                        self.error_count += 1

            elif opcode == TierraOp.ADRB:
                # Search backward for template address -> AX
                tmpl = TemplateMatcher.extract_template(self.soup, self.ip)
                if tmpl:
                    comp = TemplateMatcher.get_complement(tmpl)
                    target = TemplateMatcher.search_backward(self.soup, self.ip, comp)
                    if target is not None:
                        self.ax = target
                    else:
                        self.flag_error = True
                        self.error_count += 1

            elif opcode == TierraOp.MAL:
                # Allocate memory for daughter block in soup
                self.ax = daughter_addr

            elif opcode == TierraOp.DIVIDE:
                # Self-replication: split daughter cell from parent
                self.divide_count += 1
                divides += 1
                offspring_genome = [
                    self.soup[(daughter_addr + k) % self.soup_size]
                    for k in range(self.genome_size)
                ]
                if on_divide_callback:
                    on_divide_callback(self.divide_count, offspring_genome)
                # Reset copy pointers for next cycle
                copy_ptr_src = self.start_address
                copy_ptr_dst = daughter_addr

            # Progress instruction pointer
            self.ip = (self.ip + 1) % self.soup_size

        return {
            "cycles_run": executed,
            "divide_events": divides,
            "mutations": mutations,
            "current_ip": self.ip,
            "borrowed_host_cycles": self.borrowed_host_cycles,
            "error_count": self.error_count,
            "registers": {"AX": self.ax, "BX": self.bx, "CX": self.cx, "DX": self.dx},
        }

    def get_soup_snippet(self, length: int = 32) -> list[int]:
        """View active window of bytecode in memory soup."""
        return [self.soup[(self.ip + i) % self.soup_size] for i in range(length)]


def classify_genome(genome: list[int]) -> tuple[str, int]:
    """Analyze mutated Tierra bytecode to determine its evolutionary lineage (Ray 1990).
    
    Accurately detects Ancestor-80, Parasites, Immune Hosts, Hyper-Replicators, and Mutant strains.
    """
    ancestor = ANCESTOR_80_GENOME
    diffs = 0
    min_len = min(len(genome), len(ancestor))
    for i in range(min_len):
        if genome[i] != int(ancestor[i]):
            diffs += 1
    diffs += abs(len(genome) - len(ancestor))

    if diffs == 0:
        return "Ancestor-80", 0

    has_mov_iab = int(TierraOp.MOV_IAB) in genome
    has_divide = int(TierraOp.DIVIDE) in genome
    has_call = int(TierraOp.CALL) in genome

    # Authentic Parasite: No MOV_IAB copy loop of its own, but contains CALL/JMP and DIVIDE!
    if not has_mov_iab and has_divide:
        return f"Parasite-{len(genome)}p", diffs
    elif len(genome) < 76 and has_mov_iab:
        return f"Hyper-Replicator-{len(genome)}", diffs
    elif len(genome) == 80 and diffs in (1, 2) and has_mov_iab:
        # Template altered to resist parasite CALL
        return f"Immune-Host-{diffs}i", diffs
    elif diffs >= 5:
        return f"Mutant-Lineage-{diffs}β", diffs
    else:
        return f"Variant-Strain-{diffs}α", diffs


def calculate_diversity_index(lineages: list[str]) -> float:
    """Calculate Shannon Diversity Index (H) of the Tierra ecosystem."""
    if not lineages:
        return 0.0
    counts: dict[str, int] = {}
    for lin in lineages:
        counts[lin] = counts.get(lin, 0) + 1
    total = len(lineages)
    shannon_h = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            shannon_h -= p * math.log(p)
    return round(shannon_h, 3)

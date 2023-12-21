import math
import re
from pathlib import Path


def process_phase_name(phase_name: str) -> str:
    """
    Process the phase name to remove special characters
    """
    return re.sub(r"[\s_/\\+–*]", "", phase_name)


def bool2yn(value: bool) -> str:
    """
    Convert boolean to Y (yes) or N (no)
    """
    return "Y" if value else "N"


def read_phase_name_from_str(str_path: Path) -> str:
    """
    Get the phase name from the str file path

    Example of str:
    PHASE=BaSnO3 // generated from pymatgen
    FORMULA=BaSnO3 //
    Lattice=Cubic HermannMauguin=P4/m-32/m Setting=1 SpacegroupNo=221 //
    PARAM=A=0.41168_0.40756^0.41580 //
    RP=4 PARAM=k1=0_0^1 k2=0 PARAM=B1=0_0^0.01 PARAM=GEWICHT=0_0 //
    GOAL:BaSnO3=GEWICHT //
    GOAL=GrainSize(1,1,1) //
    E=BA+2 Wyckoff=b x=0.500000 y=0.500000 z=0.500000 TDS=0.010000
    E=SN+4 Wyckoff=a x=0.000000 y=0.000000 z=0.000000 TDS=0.010000
    E=O-2 Wyckoff=d x=0.000000 y=0.000000 z=0.500000 TDS=0.010000
    """
    text = str_path.read_text()
    return re.search(r"PHASE=(\w*)", text).group(1)


def standardize_coords(x, y, z):
    # Normalize coordinates to be within [0, 1)
    while x < 0.0:
        x += 1.0
    while y < 0.0:
        y += 1.0
    while z < 0.0:
        z += 1.0

    while x >= 1.0:
        x -= 1.0
    while y >= 1.0:
        y -= 1.0
    while z >= 1.0:
        z -= 1.0

    # Adjust coordinates to specific fractional values if close
    fractions = {
        0.3333: 1 / 3,
        0.6667: 2 / 3,
        0.1667: 1 / 6,
        0.8333: 5 / 6,
        0.0833: 1 / 12,
        0.4167: 5 / 12,
        0.5833: 7 / 12,
        0.9167: 11 / 12,
    }

    for key, value in fractions.items():
        if abs(x - key) < 0.0001:
            x = value
        if abs(y - key) < 0.0001:
            y = value
        if abs(z - key) < 0.0001:
            z = value

    return x, y, z


def fuzzy_compare(a, b):
    # Getting the fractional part of the numbers
    fa = math.fmod(a, 1.0)
    fb = math.fmod(b, 1.0)

    # Normalizing the fractional parts to be within [0, 1]
    while fa < 0.0:
        fa += 1.0
    while fb < 0.0:
        fb += 1.0
    while fa > 1.0:
        fa -= 1.0
    while fb > 1.0:
        fb -= 1.0

    # Checking specific fractional values
    fractions = [
        (0.3333, 0.3334),  # 1/3
        (0.6666, 0.6667),  # 2/3
        (0.1666, 0.1667),  # 1/6
        (0.8333, 0.8334),  # 5/6
        (0.0833, 0.0834),  # 1/12
        (0.4166, 0.4167),  # 5/12
        (0.5833, 0.5834),  # 7/12
        (0.9166, 0.9167),  # 11/12
    ]

    for lower, upper in fractions:
        if lower <= fa <= upper and lower <= fb <= upper:
            return True

    # Fuzzy comparison for general case
    def is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
        # Custom implementation of fuzzy comparison
        return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)

    return is_close(fa, fb)


def supercell_coords(postions):
    """
    Generate the supercell coordinates
    """
    extended_coords = []
    for x, y, z in postions:
        for i in range(-1, 2):
            for j in range(-1, 2):
                for k in range(-1, 2):
                    if i == j == k == 0:
                        continue
                    extended_coords.append(standardize_coords(x + i, y + j, z + k))
    return extended_coords


POSSIBLE_SPECIES = """H   
HE
LI
LI+1
BE  
BE+2
B   
C   
N   
O   
O-1 
O-2 
F   
F-1 
NE  
NA  
NA+1
MG  
MG+2
AL  
AL+3
SI  
SI+4
P   
S   
CL  
CL-1
AR  
K   
K+1 
CA  
CA+2
SC  
SC+3
TI  
TI+3
TI+4
V   
V+2 
V+3 
V+5 
CR  
CR+2
CR+3
MN  
MN+2
MN+3
MN+4
FE  
FE+2
FE+3
CO  
CO+2
CO+3
NI  
NI+2
NI+3
CU  
CU+1
CU+2
ZN  
ZN+2
GA  
GA+3
GE  
AS  
SE  
BR  
BR-1
KR  
RB  
RB+1
SR  
SR+2
Y   
Y+3 
ZR  
ZR+4
NB  
NB+3
NB+5
MO  
MO+3
MO+5
MO+6
TC  
RU  
RU+3
RU+4
RH  
RH+3
RH+4
PD  
PD+2
PD+4
AG  
AG+1
AG+2
CD  
CD+2
IN  
IN+3
SN  
SN+2
SN+4
SB  
SB+3
SB+5
TE  
I   
I-1 
XE  
CS  
CS+1
BA  
BA+2
LA  
LA+3
CE  
CE+3
CE+4
PR  
PR+3
PR+4
ND  
ND+3
PM  
PM+3
SM  
SM+3
EU  
EU+2
EU+3
GD  
GD+3
TB  
TB+3
DY  
DY+3
HO  
HO+3
ER  
ER+3
TM  
TM+3
YB  
YB+2
YB+3
LU  
LU+3
HF  
TA  
W   
RE  
OS  
IR  
PT  
AU  
HG  
TL  
PB  
BI  
PO  
AT  
RN  
FR  
RA  
AC  
TH  
PA  
U   
NP  
PU  
AM  
CM  
BK  
CF  
ES  
FM  
MD  
NO  
LW 
"""

POSSIBLE_SPECIES = set(sp.strip() for sp in POSSIBLE_SPECIES.split("\n") if sp.strip())

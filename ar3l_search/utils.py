import math
import re
from fractions import Fraction
from pathlib import Path
from typing import List


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


def normalize_value(value) -> float:
    value = float(value)
    while value >= 1:
        value -= 1
    while value < 0:
        value += 1
    return value


def standardize_coords(x, y, z) -> List[float]:
    """
    Standardize the coordinates to be between 0 and 1
    """

    def adjust_value(value):
        value = normalize_value(value)

        if math.isclose(value, 0.3333, abs_tol=0.0001):
            return Fraction(1, 3)
        elif math.isclose(value, 0.6667, abs_tol=0.0001):
            return Fraction(2, 3)
        elif math.isclose(value, 0.1667, abs_tol=0.0001):
            return Fraction(1, 6)
        elif math.isclose(value, 0.8333, abs_tol=0.0001):
            return Fraction(5, 6)
        elif math.isclose(value, 0.0833, abs_tol=0.0001):
            return Fraction(1, 12)
        elif math.isclose(value, 0.4167, abs_tol=0.0001):
            return Fraction(5, 12)
        elif math.isclose(value, 0.5833, abs_tol=0.0001):
            return Fraction(7, 12)
        elif math.isclose(value, 0.9167, abs_tol=0.0001):
            return Fraction(11, 12)
        else:
            return round(value, 6)  # round to 6 decimal places

    return [adjust_value(x), adjust_value(y), adjust_value(z)]


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

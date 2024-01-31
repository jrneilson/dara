"""Functions related to opening/reading CIF files."""

import re

from monty.json import MSONable
from pymatgen.io.cif import CifBlock as CifBlockPymatgen
from pymatgen.io.cif import CifFile


class CifBlock(MSONable, CifBlockPymatgen):
    """Thin wrapper around CifBlock from pymatgen to enable serialization."""


class Cif(MSONable, CifFile):
    """Thin wrapper around CifFile from pymatgen to enable serialization."""

    @classmethod
    def from_str(cls, string) -> CifFile:
        """Read CifFile from a string. Method closely adapted from
        pymatgen.io.cif.CifFile.from_str.

        Args:
            string: String representation.

        Returns
        -------
            CifFile
        """
        dct = {}

        for block_str in re.split(
            r"^\s*data_", f"x\n{string}", flags=re.MULTILINE | re.DOTALL
        )[1:]:
            if "powder_pattern" in re.split(r"\n", block_str, maxsplit=1)[0]:
                continue
            block = CifBlock.from_str("data_" + block_str)
            dct[block.header] = block

        return cls(dct, string)

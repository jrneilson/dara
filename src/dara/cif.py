"""Functions related to opening/reading CIF files."""
from __future__ import annotations

import re
from pathlib import Path

from monty.json import MSONable
from pymatgen.core import Structure
from pymatgen.io.cif import CifBlock as CifBlockPymatgen
from pymatgen.io.cif import CifFile


class CifBlock(MSONable, CifBlockPymatgen):
    """Thin wrapper around CifBlock from pymatgen to enable serialization."""


class Cif(MSONable, CifFile):
    """Thin wrapper around CifFile from pymatgen to enable serialization."""

    def to_file(self, path: str | Path | None = None):
        """Save to .cif file."""
        if path is None:
            path = f"{next(iter(self.data.keys()))}.cif"

        with open(path, "w") as f:
            f.write(str(self))

    def to_structure(self, **kwargs) -> Structure:
        """Convert to pymatgen Structure."""
        return Structure.from_str(str(self), fmt="cif", **kwargs)

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

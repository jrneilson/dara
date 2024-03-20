"""Functions related to opening/reading CIF files."""

from __future__ import annotations

import re
from pathlib import Path

from monty.json import MSONable
from pymatgen.core import Structure
from pymatgen.io.cif import CifBlock as CifBlockPymatgen
from pymatgen.io.cif import CifFile, CifParser


class CifBlock(MSONable, CifBlockPymatgen):
    """Thin wrapper around CifBlock to enable serialization by subclassing MSONable."""


class Cif(MSONable, CifFile):
    """Thin wrapper around CifFile from pymatgen to enable serialization."""

    def __init__(
        self, data: dict, orig_string: str | None = None, comment: str | None = None, filename: str | None = None
    ) -> None:
        """
        Args:
            data: dict of CifBlock objects.
            orig_string: The original cif string.
            comment: Comment string.
            filename: Filename of the CIF file. Optional; helps for tracking provenance.
        """
        super().__init__(data, orig_string, comment)
        self.filename = filename or ""

        try:
            struct = CifParser.from_str(self.orig_string).parse_structures()[0]
            formula = struct.composition.reduced_formula
            sg = struct.get_space_group_info()[1]
            self._name = f"{formula}_{sg}"
        except Exception:
            raise ValueError("CIF file structure can not be successfully parsed!")

    @classmethod
    def from_file(cls, path: str | Path) -> CifFile:
        """
        Read Cif from a path.

        Args:
            path: File path to read from.

        Returns
        -------
            CifFile object
        """
        obj = super().from_file(path)
        obj.filename = str(Path(path).stem)
        return obj

    def to_file(self, path: str | Path | None = None) -> None:
        """Save to .cif file.

        Args:
            path: Path to save to. If None, will use the filename attribute (if available) or default to the name
                attribute ([formula]_[spacegroup]).
        """
        if path is None:
            path = f"{self.filename}.cif" if self.filename else f"{self.name}.cif"

        with open(path, "w") as f:
            f.write(str(self))

    def to_structure(self, **kwargs) -> Structure:
        """Convert to pymatgen Structure."""
        return Structure.from_str(str(self), fmt="cif", **kwargs)

    @property
    def name(self) -> str:
        """Name of file (acquired either from top of file or from structure's formula)."""
        return self._name

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

        for block_str in re.split(r"^\s*data_", f"x\n{string}", flags=re.MULTILINE | re.DOTALL)[1:]:
            if "powder_pattern" in re.split(r"\n", block_str, maxsplit=1)[0]:
                continue
            block = CifBlock.from_str("data_" + block_str)
            dct[block.header] = block

        return cls(dct, string)

    def __repr__(self) -> str:
        return f"Cif[{self.name}]"

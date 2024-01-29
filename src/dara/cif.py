"""Functions related to opening/reading CIF files."""

from pymatgen.io.cif import CifFile


class Cif(CifFile):
    """Thin wrapper around CifFile from pymatgen to enable serialization."""

    def as_dict(self):
        """Convert CIF file to a dictionary."""
        return {k: v.data for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "Cif":
        """Convert dictionary to CIF file."""
        return cls(d)

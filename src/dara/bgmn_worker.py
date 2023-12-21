import os
import re
from pathlib import Path
from subprocess import run
from typing import Any, Union

from dara.config import Config


class BGMNWorker:
    def __init__(self):
        self.bgmn_folder = (Path(__file__).parent / "3dparty" / "BGMNwin").absolute()

        self.bgmn_path = self.bgmn_folder / "bgmn"

        # for windows
        if not self.bgmn_path.exists():
            self.bgmn_path = self.bgmn_folder / "bgmn.exe"

        if not self.bgmn_path.exists():
            raise FileNotFoundError("Cannot find BGMN executable.")

        os.environ["EFLECH"] = self.bgmn_folder.as_posix()
        os.environ["PATH"] += os.pathsep + self.bgmn_folder.as_posix()

    def run_refinement_cmd(self, control_file: Path):
        """
        Run refinement via BGMN executable.

        :param control_file: the path to the control file (.sav)
        """
        cp = run(
            [self.bgmn_path.as_posix(), control_file.absolute().as_posix()],
            cwd=control_file.parent.absolute().as_posix(),
            capture_output=not Config()["bgmn"]["print_progress"],
        )
        if cp.returncode:
            raise RuntimeError(
                f"Error in BGMN refinement for {control_file}. The exit code is {cp.returncode}\n"
                f"{cp.stdout}\n"
                f"{cp.stderr}"
            )

    @staticmethod
    def get_result(control_file: Path):
        """
        Get the result from the refinement.

        :param control_file: the path to the control file (.sav)

        Example of the .lst file:

        Rietveld refinement to file(s) Mg3MnNi3O8.xy
        BGMN version 4.2.23, 8301 measured points, 78 peaks, 20 parameters
        Start: Mon Dec 18 11:43:20 2023; End: Mon Dec 18 11:43:21 2023
        43 iteration steps

        Rp=4.14%  Rpb=50.39%  R=13.55%  Rwp=8.98% Rexp=1.47%
        Durbin-Watson d=0.06
        1-rho=13.6%

        Global parameters and GOALs
        ****************************
        QMg3MnNi3O8166sym=0.0700+-0.0046
        QNiO=0.9300+-0.0046
        EPS2=-0.001657+-0.000033

        Local parameters and GOALs for phase Mg3MnNi3O8166sym
        ******************************************************
        SpacegroupNo=166
        HermannMauguin=R-32/m
        XrayDensity=4.943
        Rphase=26.64%
        UNIT=NM
        A=0.5898+-0.0013
        C=1.4449+-0.0062
        k1=1.00000
        B1=0.00492+-0.00076
        GEWICHT=0.0288+-0.0019
        GrainSize(1,1,1)=64.7+-10.0
        Atomic positions for phase Mg3MnNi3O8166sym
        ---------------------------------------------
          9     0.5000  0.0000  0.0000     E=(MG(1.0000))
          3     0.0000  0.0000  0.0000     E=(MN(1.0000))
          9     0.5000  0.0000  0.5000     E=(NI(1.0000))
         18     0.0268 -0.0268  0.7429     E=(O(1.0000))
          6     0.0000  0.0000  0.2511     E=(O(1.0000))

        Local parameters and GOALs for phase NiO
        ******************************************************
        SpacegroupNo=225
        HermannMauguin=F4/m-32/m
        XrayDensity=6.760
        Rphase=11.31%
        UNIT=NM
        A=0.418697+-0.000027
        k1=0
        B1=0.00798+-0.00022
        GEWICHT=0.3827+-0.0049
        GrainSize(1,1,1)=53.2+-1.5
        Atomic positions for phase NiO
        ---------------------------------------------
          4     0.0000  0.0000  0.0000     E=(NI+2(1.0000))
          4     0.5000  0.5000  0.5000     E=(O-2(1.0000))

        """

        def parse_values(v_: str) -> Union[float, tuple[float, float], None, str, int]:
            try:
                v_ = v_.strip("%")
                if v_ == "ERROR" or v_ == "UNDEF":
                    return None
                if "+-" in v_:
                    v_ = (float(v_.split("+-")[0]), float(v_.split("+-")[1]))
                else:
                    v_ = float(v_)
                    if v_.is_integer():
                        v_ = int(v_)
            except ValueError:
                pass
            return v_

        def parse_section(text: str) -> dict[str, Any]:
            section = dict(re.findall(r"^(\w+)=(.+?)$", text, re.MULTILINE))
            section = {k: parse_values(v) for k, v in section.items()}
            return section

        lst_path = control_file.parent / f"{control_file.stem}.lst"
        if not lst_path.exists():
            raise FileNotFoundError(f"Cannot find the .lst file for {control_file}")

        with lst_path.open() as f:
            texts = f.read()

        result = {"raw_lst": texts}

        num_steps = int(re.search(r"(\d+) iteration steps", texts).group(1))
        result["num_steps"] = num_steps

        for var in ["Rp", "Rpb", "R", "Rwp", "Rexp"]:
            result[var] = float(re.search(rf"{var}=(\d+\.\d+)%", texts).group(1))
        result["d"] = float(re.search(r"Durbin-Watson d=(\d+\.\d+)", texts).group(1))
        result["1-rho"] = float(re.search(r"1-rho=(\d+\.\d+)%", texts).group(1))

        # global goals
        global_parameters_text = re.search(r"Global parameters and GOALs\n(.*?)\n(?:\n|\Z)", texts, re.DOTALL).group(1)
        global_parameters = parse_section(global_parameters_text)
        result.update(global_parameters)

        phases_results = dict(
            re.findall(
                r"Local parameters and GOALs for phase (.+?)\n(.*?)\n(?:\n|\Z)",
                texts,
                re.DOTALL,
            )
        )

        phases_results = {k: parse_section(v) for k, v in phases_results.items()}

        result["phases_results"] = phases_results
        return result

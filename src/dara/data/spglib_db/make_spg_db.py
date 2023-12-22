import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

## New symbol	Aem2	Aea2	Cmce	Cmme	Ccce
## Old Symbol	Abm2	Aba2	Cmca	Cmma	Ccca
new2old = {
    "Aem2": "Abm2",
    "Aea2": "Aba2",
    "Cmce": "Cmca",
    "Cmme": "Cmma",
    "Ccme": "Ccca",
}


def xml2dict_sp(xml_file):
    """
    Convert xml file to dict

    :param xml_file
    :return:
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    data = {}
    for child in root:
        for sub_child in child:
            if sub_child.tag == "setting":
                settings = sub_child.attrib
                if "Number" in settings:
                    settings["Setting"] = settings.pop("Number")

                wycs = {}
                for wyckoff in sub_child:
                    wycoff_letter = wyckoff.attrib["Symbol"]
                    wycs[wycoff_letter] = {
                        **wyckoff.attrib,
                        "std_notations": [
                            elem.text
                            for elem in wyckoff
                            if elem.attrib["Standard"] == "1"
                        ],
                    }

                data.setdefault(sub_child.get("HermannMauguin"), []).append(
                    {**settings, "SpacegroupNo": child.get("Number"), "Wyckoffs": wycs}
                )
    return data


def csv2dict_sp(csv_file):
    """
    Convert csv file to dict

    :param csv_file:
    :return:
    """
    data = {}
    keys = {
        "Hall": 0,
        "group_number": 1,
        "spacegroup": 4,
        "hall_symb": 6,
        "international_full": 8,
    }
    with open(csv_file) as f:
        reader = csv.reader(f)
        for row in reader:
            hall_number = row[keys["Hall"]]
            group_number = row[keys["group_number"]]
            spacegroup = row[keys["spacegroup"]]
            international_short = row[keys["hall_symb"]]
            international_full = row[keys["international_full"]].replace(" ", "")

            data[hall_number] = {
                "group_number": group_number,
                "spacegroup": spacegroup,
                "hall_symb": international_short,
                "international_full": international_full,
            }

    return data


if __name__ == "__main__":
    data1 = xml2dict_sp(Path("spacegrp.xml"))
    data2 = csv2dict_sp(Path("spg.csv"))

    for k, v in data2.items():
        hm = v["international_full"]
        if hm in new2old:
            hm = new2old[hm]
        if hm not in data1:
            print(f"{k} {hm} not in xml file")

    # merge two table
    data = {}

    for k, v in data2.items():
        hm = v["international_full"]
        if hm in data1:
            settings = data1[hm]
            settings_list = []
            for setting in settings:
                setting = {**setting}
                wyckoffs = setting.pop("Wyckoffs")
                settings_list.append({"setting": setting, "wyckoffs": wyckoffs})
            data[k] = {**v, "settings": settings_list}
        else:
            data[k] = {
                **v,
                "settings": [
                    {
                        "setting": {
                            "HermannMauguin": hm,
                            "SpacegroupNo": v["spacegroup"],
                        },
                        "wyckoffs": {},
                    }
                ],
            }

    with (Path("__file__").parent / "spg.json").open("w") as f:
        json.dump(data, f, indent=1)

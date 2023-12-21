import os
import platform
import zipfile
from pathlib import Path

import requests


def download_bgmn():
    # get os
    os_name = platform.system()  # Darwin, Linux, Windows

    if os_name not in ["Darwin", "Linux", "Windows"]:
        raise Exception("Unsupported OS: " + os_name + ".")

    # get url
    URL = f"https://ocf.berkeley.edu/~yuxingfei/bgmn/bgmnwin_{os_name}.zip"

    # download
    # add a progress bar when downloading
    from tqdm import tqdm

    r = requests.get(URL, stream=True)
    if r.status_code != 200:
        raise Exception(f"Cannot download from {URL}.")

    total_size = int(r.headers.get("content-length", 0))
    block_size = 1024
    t = tqdm(total=total_size, unit="iB", unit_scale=True)
    with (Path(__file__).parent / "bgmnwin.zip").open("wb") as f:
        for data in r.iter_content(block_size):
            t.update(len(data))
            f.write(data)
    t.close()

    # unzip
    with zipfile.ZipFile("bgmnwin.zip", "r") as zip_ref:
        zip_ref.extractall()

    # delete zip
    os.remove("bgmnwin.zip")

    # give permission
    if os_name == "Linux":
        os.system("chmod +x bgmnwin/bgmn")
    elif os_name == "Darwin":
        os.system("chmod +x bgmnwin/bgmn")


if __name__ == "__main__":
    download_bgmn()

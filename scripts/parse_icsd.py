"""Parse the ICSD and return unique, oldest CIFs at room temperature."""
from dara.parse_icsd import ICSDParser

PATH_TO_ICSD = "/Users/mcdermott/Documents/ICSD"

if __name__ == "__main__":
    print("Parsing ICSD...")
    ICSDParser(PATH_TO_ICSD).parse_all_cifs_with_icsd_codes_and_years()

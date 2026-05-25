import re
from pathlib import Path

# Mapping of speakers to country codes
SPEAKER_COUNTRY_MAP = {
    "Abdul Hamid": "PS",
    "Abdul Hamid Siyam": "PS",
    "Ahmed Al-Sharaa": "SY",
    "Andrii Sybiha": "UA",
    "André Corrêa do Lago": "BR",
    "Azali Assoumani": "KM",
    "Babatunde Ahonsi": "NG",
    "Baiba Braže": "LV",
    "Carl Skau": "SE",
    "Cevdet Yılmaz": "TR",
    "Daniel Levy": "UK",
    "David Moinina Sengeh": "SL",
    "Deniz Kilislioğlu": "TR",
    "Eda Özdemir": "TR",
    "Emile Hokayem": "LB",
    "Faisal Dawjee": "ZA",
    "Félix Antoine Tshisekedi": "CD",
    "Félix Ulloa": "SV",
    "Gordana Siljanovska-Davkova": "MK",
    "Gökhan Çeliker": "TR",
    "Hakan Fidan": "TR",
    "Hassan Sheikh Mohamud": "SO",
    "Hikmet Hajiyev": "AZ",
    "Irakli Kobakhidze": "GE",
    "Kassym-Jomart Tokayev": "KZ",
    "Keir Simmons": "UK",
    "Kemal Cebe": "TR",
    "Kęstutis Budrys": "LT",
    "Laurent Fabius": "FR",
    "Levent Gümrükçü": "TR",
    "Lizzie Porter": "UK",
    "Manolis Kostidis": "GR",
    "Marabski [Soyisim]": "PL",
    "Maria Fantappiè": "IT",
    "Mercy Bamola": "NG",
    "Mevlüt Çavuşoğlu": "TR",
    "Miloš Vučević": "RS",
    "Mukhtar Babayev": "AZ",
    "Murat Kurum": "TR",
    "Olga Osacheva": "BY",
    "Radmila Šekerinska": "MK",
    "Recep Tayyip Erdoğan": "TR",
    "Selwin Hart": "BB",
    "Sergei Lavrov": "RU",
    "Shayea Mohsin Al-Zindani": "YE",
    "Thomas Greminger": "CH",
    "Tom Barrack": "US",
    "Varsen Aghabekian": "PS",
    "Xəyalə Rəis": "AZ",
    "İsmail": "TR",
    "Əli Vəliyev": "AZ",
}

# Metadata mapping for the 12 files
PANELS_METADATA = {
    "01_Ahmed Al-Sharaa.txt": {
        "title": "Ahmed Al-Sharaa Interview",
        "date": "April 2026",
        "theme": "Syrian Reconstruction & Middle East Relations",
        "panel_number": 1,
    },
    "02_Cevdet Yılmaz.txt": {
        "title": "Cevdet Yılmaz Keynote Address",
        "date": "April 2026",
        "theme": "Turkish Economic Outlook & Regional Trade",
        "panel_number": 2,
    },
    "03_Erdoğan.txt": {
        "title": "Recep Tayyip Erdoğan Address",
        "date": "April 2026",
        "theme": "Global Diplomacy & Multipolar World Order",
        "panel_number": 3,
    },
    "04_Avrupa Başkanları.txt": {
        "title": "European Leaders Panel",
        "date": "April 2026",
        "theme": "Eurasian Security Architecture & Cooperation",
        "panel_number": 4,
    },
    "05_Gazze Konuşması.txt": {
        "title": "Gaza Crisis & Middle East Peace Panel",
        "date": "April 2026",
        "theme": "Conflict Resolution & Palestine Crisis",
        "panel_number": 5,
    },
    "06_Mevlüt Çavuşoğlu ve Cumhurbaşkanları.txt": {
        "title": "Regional Presidents Dialogue",
        "date": "April 2026",
        "theme": "Presidents Panel & Regional Connectivity",
        "panel_number": 6,
    },
    "07_Sergei Lavrov.txt": {
        "title": "Sergei Lavrov Interview",
        "date": "April 2026",
        "theme": "Russian Foreign Policy & Global Order Crises",
        "panel_number": 7,
    },
    "08_Somali.txt": {
        "title": "Somalia & Horn of Africa Security Panel",
        "date": "April 2026",
        "theme": "Maritime Security & East Africa Stability",
        "panel_number": 8,
    },
    "09_Tom Barrack.txt": {
        "title": "Tom Barrack Dialogue",
        "date": "April 2026",
        "theme": "US Middle East Policy & Investment",
        "panel_number": 9,
    },
    "10_Ukrayna Dışişleri Bakanı.txt": {
        "title": "Andrii Sybiha Interview",
        "date": "April 2026",
        "theme": "Ukraine Conflict & Security Guarantees",
        "panel_number": 10,
    },
    "11_Hakan Fidan.txt": {
        "title": "Hakan Fidan Foreign Policy Q&A",
        "date": "April 2026",
        "theme": "Turkish Mediation & Strategic Autonomy",
        "panel_number": 11,
    },
    "12_Climate.txt": {
        "title": "Climate Finance & Future COPs Panel",
        "date": "April 2026",
        "theme": "Climate Change, Energy Transition & Cooperation",
        "panel_number": 12,
    },
}


def clean_speaker_name(speaker: str) -> tuple[str, str]:
    """Extract clean speaker name and existing country code if present, otherwise map it."""
    # Check if speaker already has country in parentheses, e.g. "Sergei Lavrov (RU)"
    match = re.search(r"\(([^)]+)\)$|\[([^\]]+)\]$", speaker)
    if match:
        country = (match.group(1) or match.group(2)).strip().upper()
        clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker).strip()
        return clean_name, country

    clean_name = speaker.strip()
    # Find country from mapping
    country = SPEAKER_COUNTRY_MAP.get(clean_name, "unknown")
    return clean_name, country


def main():
    data_dir = Path("data/Antalya Diplomatic Forum 2026")
    processed = 0
    logs = []

    for file_path in data_dir.rglob("*.txt"):
        name = file_path.name
        if name not in PANELS_METADATA:
            continue

        meta = PANELS_METADATA[name]
        logs.append(f"Standardizing: {name}")

        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        # Prepend Metadata header
        new_lines.append(f"TITLE: {meta['title']}\n")
        new_lines.append(f"DATE: {meta['date']}\n")
        new_lines.append(f"THEME: {meta['theme']}\n")
        new_lines.append(f"PANEL_NUMBER: {meta['panel_number']}\n")
        new_lines.append("---\n")

        # Parse and convert dialog lines
        for line in lines:
            line_str = line.strip()
            if not line_str:
                new_lines.append("\n")
                continue

            # Skip any existing metadata header if we rerun
            if line_str.startswith(
                ("TITLE:", "DATE:", "THEME:", "PANEL_NUMBER:", "---")
            ):
                continue

            # Process dialogue turn
            if " : " in line_str:
                parts = line_str.split(" : ", 1)
                speaker_part = parts[0].strip()
                text_part = parts[1].strip()

                clean_name, country = clean_speaker_name(speaker_part)
                new_lines.append(f"{clean_name} ({country}) : {text_part}\n")
            elif ":" in line_str:
                parts = line_str.split(":", 1)
                speaker_part = parts[0].strip()
                text_part = parts[1].strip()

                clean_name, country = clean_speaker_name(speaker_part)
                new_lines.append(f"{clean_name} ({country}) : {text_part}\n")
            else:
                new_lines.append(f"{line_str}\n")

        # Write clean UTF-8 text back
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        processed += 1

    logs.append(f"Successfully standardized {processed} files.")

    # Save log file
    with open("scratch/standardize_log.txt", "w", encoding="utf-8") as log_file:
        log_file.write("\n".join(logs))


if __name__ == "__main__":
    main()

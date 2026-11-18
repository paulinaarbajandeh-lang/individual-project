"""
Step 1 – Collection

Collects ended auctions from auctionet.com, one auction house at a time,
going back to HISTORY_START (1 July 2026).

How it works:
- Search pages are read newest first (order=sold_recent).
- After every page, the results so far are saved to a checkpoint CSV,
  so an interrupted run never loses data.
- Collection for a house stops as soon as a page contains items older
  than HISTORY_START.
- Finally, all checkpoint files are combined into one file and a coverage
  overview per auction house is written.

Note: in the original work the houses were collected one by one over
several sessions, with checks in between. Houses that already have a
checkpoint file are skipped here, so the script can be resumed.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent / "src"))
from auctionet_scraping import (  # noqa: E402
    DATA_DIR,
    HISTORY_START,
    parse_auction_date,
    scrape_ended_page,
)

# Auctionet search shows at most 209 pages per query (about 10,000 items).
MAX_PAGES = 209
SLEEP_SECONDS = 1

# company_id -> auction house name (as listed on auctionet.com)
AUCTION_HOUSES = {
    319: "Lawrences",  # first house collected (pilot)
    414: "Acreman St Auctioneers & Valuers",
    491: "Arce Auctions",
    712: "Auktionsbyrån Varberg",
    398: "Auktionsfirma Kenneth Svensson i Kalmar",
    90: "Auktionshaus Blank",
    93: "Auktionshaus Bossard",
    408: "Auktionshaus Stuber's Hammerschlag",
    1: "Auktionshuset Kolonn",
    407: "Auktionshuset STO Bohuslän",
    46: "Auktionshuset Thelin & Johansson",
    411: "Auktionshuset Thörner & Ek",
    487: "Auktionskammaren Sydost Kalmar",
    324: "Auktionsmagasinet Vänersborg",
    6: "Auktionsverket Engelholm",
    223: "Balclis",
    248: "Barcelona Auctions",
    676: "Batemans of Stamford",
    566: "Bidstrup Auktioner",
    365: "Bishop & Miller",
    323: "Björnssons Auktionskammare",
    604: "Borås Auktionshall",
    320: "Chalkwell Auctions",
    67: "Colombos",
    91: "Connoisseur Bokauktioner",
    112: "Crafoord Auktioner Lund",
    283: "Crafoord Auktioner Malmö",
    232: "Crafoord Auktioner Stockholm",
    643: "Ekenbergs Auktioner",
    606: "Falun Auktionsbyrå",
    405: "Formstad Auktioner",
    4: "Garpenhus Auktioner",
    447: "Gomér & Andersson Jönköping",
    9: "Gomér & Andersson Linköping",
    95: "Gomér & Andersson Norrköping",
    234: "Gomér & Andersson Nyköping",
    639: "Griffin’s Auctioneers",
    10: "Göteborgs Auktionsverk",
    231: "Halmstads Auktionskammare",
    326: "Handelslagret Auktionsservice",
    11: "Helsingborgs Auktionskammare",
    227: "Hälsinglands Auktionsverk",
    152: "Höganäs Auktionsverk",
    224: "Höörs Auktionshall",
    49: "Kalmar Auktionsverk",
    642: "Karljohan Auktioner",
    243: "Karlstad Hammarö Auktionsverk",
    222: "Kunst- und Auktionshaus Kleinhenz",
    565: "Kurage Auktion",
    225: "Laholms Auktionskammare",
    322: "Limhamns Auktionsbyrå",
    600: "Lyme Bay Auctions",
    102: "Lysekils Auktionsbyrå",
    528: "Ma San Auction",
    524: "Markus Auktioner",
    12: "Mauritz Widforss",
    780: "Metropol Auktioner",
    187: "Norrlands Auktionsverk",
    404: "Palsgaard Kunstauktioner",
    602: "Preziosi Auctions",
    81: "RA Auktionsverket Norrköping",
    564: "Rheinveld Auktionen",
    321: "Roslagens Auktionsverk",
    100: "Rumsey’s Auctioneers",
    410: "Sajab Vintage",
    601: "Skandia Auktion",
    412: "Skånes Auktionsverk",
    48: "Stadsauktion Sundsvall",
    236: "Stockholms Auktionsverk Düsseldorf/Neuss",
    238: "Stockholms Auktionsverk Fine Art",
    245: "Stockholms Auktionsverk Göteborg",
    244: "Stockholms Auktionsverk Hamburg",
    241: "Stockholms Auktionsverk Helsingborg",
    242: "Stockholms Auktionsverk Helsinki",
    237: "Stockholms Auktionsverk Köln",
    239: "Stockholms Auktionsverk Magasin 5",
    240: "Stockholms Auktionsverk Sickla",
    99: "Södermanlands Auktionsverk",
    603: "Sørensen Auktioner",
    450: "TOKA Auktionshus",
    567: "Uppsala Auktionskammare",
    72: "Växjö Auktionskammare",
    229: "Walter Borg",
    745: "Wickmans",
    526: "Woxholt Auktionshus",
    562: "Young's Auctions",
    413: "Örebro Stadsauktioner",
}

CHECKPOINT_DIR = DATA_DIR / "checkpoints"

# The pilot house was saved under a different file name.
LEGACY_CHECKPOINTS = {319: "lawrences_checkpoint.csv"}


def checkpoint_path(company_id):
    legacy_name = LEGACY_CHECKPOINTS.get(company_id)
    if legacy_name and (CHECKPOINT_DIR / legacy_name).exists():
        return CHECKPOINT_DIR / legacy_name
    return CHECKPOINT_DIR / f"auctionet_{company_id}_checkpoint.csv"


def collect_auction_house(company_id, company_name):
    """Collect ended auctions for one house back to HISTORY_START."""
    filename = checkpoint_path(company_id)
    results = []
    previous_oldest = None
    reached_start = False
    checkpoint = pd.DataFrame()

    for page in range(1, MAX_PAGES + 1):
        print(f"{company_name} – page {page}")

        df = scrape_ended_page(page, company_id=company_id)
        if df is None or df.empty:
            # An empty page in the middle would mean missing data: stop.
            raise RuntimeError(f"Page {page} returned no data. Check before continuing.")

        df["end_date"] = df["auction_end_time"].apply(parse_auction_date)

        missing = df["end_date"].isna().sum()
        if missing:
            print(f"  Skipping {missing} items without a valid date")
        df = df.dropna(subset=["end_date"]).copy()

        if df.empty:
            time.sleep(SLEEP_SECONDS)
            continue

        oldest = df["end_date"].min()
        newest = df["end_date"].max()

        # Pages must go back in time; anything else means the order changed.
        if previous_oldest is not None and newest > previous_oldest:
            raise RuntimeError(f"Unexpected date order on page {page}.")

        results.append(df[df["end_date"] >= HISTORY_START])

        # Save after every page so progress is never lost.
        checkpoint = pd.concat(results, ignore_index=True)
        checkpoint = checkpoint.drop_duplicates(subset=["item_id"])
        checkpoint.to_csv(filename, index=False)

        print(f"  Saved: {len(checkpoint)} | Oldest date: {oldest.date()}")

        if oldest < HISTORY_START:
            reached_start = True
            break

        previous_oldest = oldest
        time.sleep(SLEEP_SECONDS)

    print(f"Done: {company_name} | file: {filename.name} | reached start date: {reached_start}\n")
    return checkpoint


def combine_checkpoints():
    """Combine all checkpoint files and add company_id from the file name."""
    files = sorted(CHECKPOINT_DIR.glob("*_checkpoint.csv"))
    if not files:
        raise FileNotFoundError("No checkpoint files found.")

    legacy_ids = {name: cid for cid, name in LEGACY_CHECKPOINTS.items()}
    frames, coverage = [], []

    for file in files:
        df = pd.read_csv(file)
        df["end_date"] = pd.to_datetime(df["end_date"], format="mixed", errors="coerce")

        company_id = legacy_ids.get(file.name) or int(file.name.split("_")[1])
        df["company_id"] = company_id
        frames.append(df)

        coverage.append({
            "company_id": company_id,
            "filename": file.name,
            "object_count": len(df),
            "earliest_date": df["end_date"].min(),
            "latest_date": df["end_date"].max(),
        })

    combined = pd.concat(frames, ignore_index=True)

    print("Checkpoint files:", len(files))
    print("Total rows:", len(combined))
    print("Unique items:", combined["item_id"].nunique())
    print("Duplicates:", combined["item_id"].duplicated().sum())
    print("Missing dates:", combined["end_date"].isna().sum())
    print("Date range:", combined["end_date"].min().date(), "–", combined["end_date"].max().date())

    combined.to_csv(DATA_DIR / "auctionet_historical_combined.csv", index=False)
    (
        pd.DataFrame(coverage)
        .sort_values("earliest_date", ascending=False)
        .to_csv(DATA_DIR / "auctionet_house_coverage.csv", index=False)
    )
    return combined


if __name__ == "__main__":
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    for company_id, company_name in AUCTION_HOUSES.items():
        if checkpoint_path(company_id).exists():
            print(f"Checkpoint exists, skipping: {company_name}")
            continue
        collect_auction_house(company_id, company_name)

    combine_checkpoints()

"""Populate the shipment database from the three shipping spreadsheets.

Spreadsheet 0 is self contained: each row is one product line of a shipment.
Spreadsheet 1 lists one product per row, so rows sharing a shipment identifier
are combined to find the quantity of each product in that shipment.
Spreadsheet 2 holds the origin and destination for every shipment in
spreadsheet 1, keyed by the same shipment identifier.
"""

import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DB = Path(__file__).parent / "shipment_database.db"


def read_csv(path):
    """Yield each row of a spreadsheet as a dict keyed by column name."""
    with open(path, newline="", encoding="utf-8") as spreadsheet:
        yield from csv.DictReader(spreadsheet)


def get_product_id(cursor, name):
    """Return the id of a product, adding it to the product table if it is new."""
    cursor.execute("INSERT OR IGNORE INTO product (name) VALUES (?)", (name,))
    cursor.execute("SELECT id FROM product WHERE name = ?", (name,))
    return cursor.fetchone()[0]


def insert_shipment(cursor, product_name, quantity, origin, destination):
    """Add one row to the shipment table for a product in a shipment."""
    product_id = get_product_id(cursor, product_name)
    cursor.execute(
        "INSERT INTO shipment (product_id, quantity, origin, destination) "
        "VALUES (?, ?, ?, ?)",
        (product_id, quantity, origin, destination),
    )


def load_spreadsheet_0(cursor):
    """Insert spreadsheet 0 directly: every row already has everything we need."""
    count = 0
    for row in read_csv(DATA_DIR / "shipping_data_0.csv"):
        insert_shipment(
            cursor,
            product_name=row["product"],
            quantity=int(row["product_quantity"]),
            origin=row["origin_warehouse"],
            destination=row["destination_store"],
        )
        count += 1
    return count


def load_spreadsheets_1_and_2(cursor):
    """Combine spreadsheets 1 and 2 into one shipment row per product per shipment."""
    # Spreadsheet 2: shipment identifier -> (origin, destination).
    routes = {
        row["shipment_identifier"]: (row["origin_warehouse"], row["destination_store"])
        for row in read_csv(DATA_DIR / "shipping_data_2.csv")
    }

    # Spreadsheet 1: each row is one unit, so count rows per (shipment, product).
    quantities = Counter(
        (row["shipment_identifier"], row["product"])
        for row in read_csv(DATA_DIR / "shipping_data_1.csv")
    )

    for (shipment_identifier, product_name), quantity in quantities.items():
        origin, destination = routes[shipment_identifier]
        insert_shipment(cursor, product_name, quantity, origin, destination)
    return len(quantities)


def main(database_path=DEFAULT_DB):
    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.cursor()
        from_sheet_0 = load_spreadsheet_0(cursor)
        from_sheets_1_and_2 = load_spreadsheets_1_and_2(cursor)
        connection.commit()  # all-or-nothing: nothing is saved if an error occurs above
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(f"Inserted {from_sheet_0} rows from spreadsheet 0")
    print(f"Inserted {from_sheets_1_and_2} rows from spreadsheets 1 and 2")


if __name__ == "__main__":
    main(*sys.argv[1:2])

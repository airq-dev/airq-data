import datetime
import decimal
import geohash
import json
import math
import os
import requests
import sqlite3
import textwrap
import zipfile


def haversine_distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles
    return c * r


def refresh_data():
    try:
        os.remove("airq.db")
    except FileNotFoundError:
        pass

    try:
        os.remove("US.zip")
    except FileNotFoundError:
        pass

    try:
        os.remove("purpleair.json")
    except FileNotFoundError:
        pass


def get_connection():
    return sqlite3.connect("airq.db")


def create_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        textwrap.dedent(
            """
        CREATE TABLE sensors (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            geohash_bit_1 VARCHAR NOT NULL,
            geohash_bit_2 VARCHAR NOT NULL,
            geohash_bit_3 VARCHAR NOT NULL,
            geohash_bit_4 VARCHAR NOT NULL,
            geohash_bit_5 VARCHAR NOT NULL,
            geohash_bit_6 VARCHAR NOT NULL,
            geohash_bit_7 VARCHAR NOT NULL,
            geohash_bit_8 VARCHAR NOT NULL,
            geohash_bit_9 VARCHAR NOT NULL,
            geohash_bit_10 VARCHAR NOT NULL,
            geohash_bit_11 VARCHAR NOT NULL,
            geohash_bit_12 VARCHAR NOT NULL
        );
    """
        )
    )
    cursor.execute(
        textwrap.dedent(
            """
        CREATE TABLE zipcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            zipcode VARCHAR NOT NULL UNIQUE,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            geohash_bit_1 VARCHAR NOT NULL,
            geohash_bit_2 VARCHAR NOT NULL,
            geohash_bit_3 VARCHAR NOT NULL,
            geohash_bit_4 VARCHAR NOT NULL,
            geohash_bit_5 VARCHAR NOT NULL,
            geohash_bit_6 VARCHAR NOT NULL,
            geohash_bit_7 VARCHAR NOT NULL,
            geohash_bit_8 VARCHAR NOT NULL,
            geohash_bit_9 VARCHAR NOT NULL,
            geohash_bit_10 VARCHAR NOT NULL,
            geohash_bit_11 VARCHAR NOT NULL,
            geohash_bit_12 VARCHAR NOT NULL,
            FOREIGN KEY(city_id) REFERENCES city(id)
        );
    """
        )
    )
    cursor.execute(
        textwrap.dedent(
            """
        CREATE TABLE cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            state_code VARCHAR NOT NULL
        );
    """
        )
    )
    cursor.execute(
        textwrap.dedent(
            """
        CREATE TABLE sensors_zipcodes (
            sensor_id INTEGER NOT NULL,
            zipcode_id INTEGER NOT NULL,
            distance REAL NOT NULL,
            PRIMARY KEY(sensor_id, zipcode_id),
            FOREIGN KEY(sensor_id) REFERENCES sensors(id),
            FOREIGN KEY(zipcode_id) REFERENCES zipcodes(id)
        );
    """
        )
    )
    conn.commit()


def get_zipcodes_from_geonames():
    r = requests.get("http://download.geonames.org/export/zip/US.zip", stream=True)
    with open("US.zip", "wb") as fd:
        for chunk in r.iter_content(chunk_size=512):
            fd.write(chunk)

    with zipfile.ZipFile("US.zip") as zf:
        with zf.open("US.txt", "r") as fd:
            for line in fd.readlines():
                fields = line.decode().strip().split("\t")
                zipcode = fields[1].strip()
                city_name = fields[2].strip()
                state_code = fields[4].strip()

                latitude = decimal.Decimal(fields[9].strip())
                longitude = decimal.Decimal(fields[10].strip())
                place_name = fields[2].strip()
                # Skip army prefixes
                if not place_name.startswith(("FPO", "APO")):
                    yield zipcode, city_name, state_code, latitude, longitude


def create_sensors_zipcodes(cursor, zipcode_id, zipcode, latitude, longitude, gh):
    # Get up to 25 sensors within a max of 25km along with their distances
    gh = list(gh)
    sensors = set()
    while gh:
        sql = "SELECT id, latitude, longitude FROM sensors WHERE {}".format(
            " AND ".join([f"geohash_bit_{i + 1}=?" for i in range(len(gh))])
        )
        if sensors:
            sql += " AND id NOT IN ({})".format(", ".join(["?" for _ in sensors]))
        cursor.execute(sql, tuple(gh) + tuple(sensors))
        new_sensors = sorted(
            [
                (r[0], haversine_distance(longitude, latitude, r[2], r[1]))
                for r in cursor.fetchall()
            ],
            key=lambda s: s[1],
        )
        for sensor_id, distance in new_sensors:
            if distance >= 25:
                return
            if len(sensors) >= 25:
                return
            sensors.add(sensor_id)
            cursor.execute(
                "INSERT INTO sensors_zipcodes VALUES (?, ?, ?)",
                (sensor_id, zipcode_id, distance),
            )
        gh.pop()


def create_city(cursor, city_name, state_code):
    cursor.execute(
        "SELECT id FROM cities WHERE name=? AND state_code=?", (city_name, state_code)
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO cities(name, state_code) VALUES(?, ?)", (city_name, state_code)
    )
    return cursor.lastrowid


def create_zipcodes():
    print("Creating zipcodes")
    for i, (zipcode, city_name, state_code, latitude, longitude) in enumerate(
        get_zipcodes_from_geonames()
    ):
        if i % 50 == 0:
            print(f"Created {i} zipcodes")
        conn = get_connection()
        cursor = conn.cursor()
        city_id = create_city(cursor, city_name, state_code)
        gh = geohash.encode(latitude, longitude)
        cursor.execute(
            textwrap.dedent(
                """
                INSERT INTO zipcodes(zipcode, city_id, latitude, longitude, {}) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """.format(
                    ", ".join([f"geohash_bit_{i}" for i in range(1, 13)])
                )
            ),
            (
                zipcode,
                city_id,
                round(float(latitude), ndigits=6),
                round(float(longitude), ndigits=6),
                *list(gh),
            ),
        )
        zipcode_id = cursor.lastrowid
        create_sensors_zipcodes(cursor, zipcode_id, zipcode, latitude, longitude, gh)
        conn.commit()


def get_purpleair_data():
    if not os.path.exists("purpleair.json"):
        resp = requests.get("https://www.purpleair.com/json")
        resp.raise_for_status()
        with open("purpleair.json", "w") as fd:
            json.dump(resp.json()["results"], fd)
    with open("purpleair.json", "r") as fd:
        return json.load(fd)


def create_sensors():
    print("Creating sensors")
    results = get_purpleair_data()
    num_created = 0
    for result in results:
        if result.get("DEVICE_LOCATIONTYPE") != "outside":
            continue
        if result.get("ParentID"):
            # I don't know what this means but feel it's probably
            # best to skip?
            continue
        if result.get("LastSeen") < datetime.datetime.now().timestamp() - (
            24 * 60 * 60
        ):
            # Out of date / maybe dead
            continue
        pm25 = result.get("PM2_5Value")
        if not pm25:
            continue
        try:
            pm25 = float(pm25)
        except (TypeError, ValueError):
            continue
        if pm25 < 0 or pm25 > 500:
            # Something is very wrong
            continue
        latitude = result.get("Lat")
        longitude = result.get("Lon")
        if not latitude or not longitude:
            continue
        gh = geohash.encode(latitude, longitude)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            textwrap.dedent(
                """
            INSERT INTO sensors
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
            ),
            (
                result["ID"],
                round(float(latitude), ndigits=6),
                round(float(longitude), ndigits=6),
                *list(gh),
            ),
        )
        conn.commit()
        num_created += 1
        if num_created % 50 == 0:
            print(f"Created {num_created} sensors of {len(results)} purpleair sensors")


def generate():
    refresh_data()
    create_db()
    create_sensors()
    create_zipcodes()


if __name__ == "__main__":
    generate()

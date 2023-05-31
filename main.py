import hashlib
import json
import math
import os
import sys
from PIL import Image
from pathlib import Path
import requests
import shutil


def ensure_dir(dir):
    Path(dir).mkdir(parents=True, exist_ok=True)


def ensure_sprite(sprite_id, url):
    hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
    sprite_id = f"{sprite_id}_{hash}"

    file_name = f"./data/sprite_cache/{sprite_id}.jpg"

    if not os.path.isfile(file_name):
        res = requests.get(url, stream=True)

        if res.status_code == 200:
            with open(file_name, "wb") as f:
                shutil.copyfileobj(res.raw, f)
        else:
            raise Exception(f"Sprite {url} could not be downloaded, aborting.")

    return sprite_id


def extract_card(card_id, sprite_id, sprite_idx, sprite_cols, sprite_rows, rotate=False):
    file_name = f"./data/cards/{card_id}.png"

    if not os.path.isfile(file_name):
        with Image.open(f"./data/sprite_cache/{sprite_id}.jpg") as im:
            w = int(im.width / sprite_cols)
            h = int(im.height / sprite_rows)
            offset_x = sprite_idx % sprite_cols * w
            offset_y = math.floor(sprite_idx / sprite_cols) * h
            cropped = im.crop((offset_x, offset_y, offset_x + w, offset_y + h))
            if rotate:
                cropped = cropped.rotate(90, expand=True)
            cropped.save(file_name)


def save_player_card(card):
    card_id = json.loads(card["GMNotes"])["id"]
    (sprite_id, sprite_data) = list(card["CustomDeck"].items())[0]

    idx = int(str(card["CardID"]).removeprefix(sprite_id))

    cols = sprite_data["NumWidth"]
    rows = sprite_data["NumHeight"]

    front_sprite_id = ensure_sprite(sprite_id, sprite_data["FaceURL"])
    extract_card(card_id, front_sprite_id, idx, cols, rows, card["SidewaysCard"])

    if sprite_data["UniqueBack"]:
        back_sprite_id = ensure_sprite(f"{sprite_id}b", sprite_data["BackURL"])
        extract_card(f"{card_id}b", back_sprite_id, idx, cols, rows, card["SidewaysCard"])


def save_player_cards(manifest):
    object_states = manifest["ObjectStates"]

    cards = next(o for o in object_states if o["Nickname"] == "All Player Cards")[
        "ContainedObjects"
    ]

    for card in [c for c in cards if "PlayerCard" in c["Tags"]]:
        save_player_card(card)


def main():
    ensure_dir("./data/sprite_cache")
    ensure_dir("./data/cards")

    with open(sys.argv[1]) as file:
        manifest = json.load(file)
        save_player_cards(manifest)


if __name__ == "__main__":
    main()

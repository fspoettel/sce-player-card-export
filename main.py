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


def fetch_url(url):
    res = requests.get(url, stream=True)
    if res.status_code == 200:
        return res
    else:
        raise Exception(f"Asset at {url} could not be downloaded, aborting.")


def get_sprite_id(url):
    sprite_id = hashlib.sha1(url.encode("utf-8")).hexdigest()
    file_name = f"./data/sprite_cache/{sprite_id}.jpg"
    return file_name


def fetch_sprite(url):
    file_name = get_sprite_id(url)

    if not os.path.isfile(file_name):
        res = fetch_url(url)
        with open(file_name, "wb") as f:
            shutil.copyfileobj(res.raw, f)


def fetch_manifest(path):
    REPO = "https://raw.githubusercontent.com/chr1z93/loadable-objects/main/"
    url = f"{REPO}{path}"
    manifest_name = path.replace("/", "_")
    file_name = f"./data/manifest_cache/{manifest_name}"

    if os.path.isfile(file_name):
        with open(file_name) as f:
            return json.load(f)
    else:
        res = fetch_url(url)
        data = res.json()
        with open(file_name, "w") as f:
            json.dump(data, f)
        return data


def extract_card(card_id, sprite, sprite_idx, sprite_cols, sprite_rows, rotate=False):
    file_name = f"./data/cards/{card_id}.png"
    try:
        if not os.path.isfile(file_name):
            with Image.open(sprite) as im:
                w = int(im.width / sprite_cols)
                h = int(im.height / sprite_rows)
                offset_x = sprite_idx % sprite_cols * w
                offset_y = math.floor(sprite_idx / sprite_cols) * h
                cropped = im.crop((offset_x, offset_y, offset_x + w, offset_y + h))
                if rotate:
                    cropped = cropped.rotate(90, expand=True)
                cropped.save(file_name)
    except Exception as e:
        print("error saving: ", file_name)
        print(e)


def save_sprite(card):
    sprite_data = list(card["CustomDeck"].values())[0]
    fetch_sprite(sprite_data["FaceURL"])
    if sprite_data["UniqueBack"] or "Location" in card["Tags"]:
        fetch_sprite(sprite_data["BackURL"])


def save_card(card):
    try:
        metadata = json.loads(card["GMNotes"])
        card_id = metadata.get("id")
        if not card_id:
            guid = card.get("GUID")
            raise Exception(f"skipping card {guid}")
    except Exception as e:
        print(e)
        return

    sprite_data = list(card["CustomDeck"].values())[0]
    idx = int(str(card["CardID"])[-2:])

    cols = sprite_data["NumWidth"]
    rows = sprite_data["NumHeight"]

    front_sprite = get_sprite_id(sprite_data["FaceURL"])
    extract_card(card_id, front_sprite, idx, cols, rows, card["SidewaysCard"])

    if sprite_data["UniqueBack"]:
        back_sprite = get_sprite_id(sprite_data["BackURL"])
        extract_card(f"{card_id}b", back_sprite, idx, cols, rows, card["SidewaysCard"])


def is_card(c):
    tags = c.get("Tags")
    return c.get("Name") == "Card" and isinstance(c.get("Tags"), list) and (
        "Minicard" in tags or "ScenarioCard" in tags or "PlayerCard" in tags
    )


def traverse_manifest(root, callback):
    for obj in root.get("ContainedObjects"):
        if is_card(obj):
            callback(obj)
        elif isinstance(obj.get("ContainedObjects"), list):
            traverse_manifest(obj, callback)


def save_player_cards(manifest):
    object_states = manifest["ObjectStates"]
    card_root = next(o for o in object_states if o["Nickname"] == "All Player Cards")
    traverse_manifest(card_root, save_sprite)
    traverse_manifest(card_root, save_card)


def traverse_encounter_cards(manifest, callback):
    object_states = manifest["ObjectStates"]
    for obj in object_states:
        # official campaigns.
        if "campaigns" in obj["GMNotes"]:
            data = fetch_manifest(obj["GMNotes"])
            traverse_manifest(data, callback)

        # # official side scenarios.
        if "Official Standalone" in obj["Nickname"]:
            # nested bags.
            for obj in obj["ContainedObjects"]:
                # contained scenarios.
                for obj in obj["ContainedObjects"]:
                    if "scenarios" in obj["GMNotes"]:
                        data = fetch_manifest(obj["GMNotes"])
                        traverse_manifest(data, callback)


def save_encounter_cards(manifest):
    traverse_encounter_cards(manifest, save_sprite)
    traverse_encounter_cards(manifest, save_card)

def main():
    ensure_dir("./data/sprite_cache")
    ensure_dir("./data/manifest_cache")
    ensure_dir("./data/cards")

    with open(sys.argv[1]) as file:
        manifest = json.load(file)
        save_player_cards(manifest)
        save_encounter_cards(manifest)

if __name__ == "__main__":
    main()

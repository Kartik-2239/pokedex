#!/usr/bin/env python3
import sys
import urllib.request
import os
import json
import random
import time
from PIL import Image
from io import BytesIO

ASCII_CHARS = [' ', '.', ':', '-', '=', 'o', 'X', '#', '%', '@']
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".pokedex", "cache")
INDEX_FILE = os.path.join(os.path.expanduser("~"), ".pokedex", "index.json")


def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_index(index):
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f)


def fetch_pokemon(identifier):
    """Fetch pokemon data by name or ID. Returns (id, name, default_sprite_url, shiny_sprite_url)."""
    url = f"https://pokeapi.co/api/v2/pokemon/{str(identifier).lower()}"
    request = urllib.request.Request(url, headers={'User-Agent': 'Python/urllib'})
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError:
        print(f"Error: Pokemon '{identifier}' not found")
        sys.exit(1)
    data = json.loads(response.read())
    sprites = data['sprites']
    default_sprite = sprites['front_default']
    shiny_sprite = sprites['front_shiny'] or sprites['front_default']
    return data['id'], data['name'], default_sprite, shiny_sprite


def cache_key(pokemon_number, shiny):
    """Returns the index key for a given pokemon number and shiny flag."""
    return f"{pokemon_number}_shiny" if shiny else str(pokemon_number)


def cache_filename(pokemon_name, shiny):
    """Returns the cache filename for a given pokemon name and shiny flag."""
    suffix = "_shiny" if shiny else ""
    return f"{pokemon_name.lower()}{suffix}.txt"


def get_cached_ascii_by_number(pokemon_number, shiny, index):
    key = cache_key(pokemon_number, shiny)
    if key in index:
        cache_file = os.path.join(CACHE_DIR, index[key])
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return f.read()
    return None


def get_cached_ascii_by_name(pokemon_name, shiny):
    cache_file = os.path.join(CACHE_DIR, cache_filename(pokemon_name, shiny))
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return f.read()
    return None


def save_ascii(pokemon_name, pokemon_number, shiny, ascii_art, index):
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = cache_filename(pokemon_name, shiny)
    cache_file = os.path.join(CACHE_DIR, filename)
    with open(cache_file, 'w') as f:
        f.write(ascii_art)
    index[cache_key(pokemon_number, shiny)] = filename
    save_index(index)


def download_image(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Python/urllib'})
    response = urllib.request.urlopen(request)
    return Image.open(BytesIO(response.read())).convert('RGBA')


def crop_transparent(image):
    bbox = image.getbbox()
    return image.crop(bbox) if bbox else image


def resize_image(image, new_height=20):
    width, height = image.size
    new_width = int(new_height * (width / height) * 1.9)
    return image.resize((new_width, new_height))


def pixels_to_ascii(image):
    chars = []
    for pixel in image.get_flattened_data():  # returns list of (r, g, b, a) tuples
        r, g, b, a = pixel
        if a < 128:
            chars.append((' ', (0, 0, 0)))
        else:
            gray = (r + g + b) // 3
            char_index = min(int(gray / 256 * len(ASCII_CHARS)), len(ASCII_CHARS) - 1)
            chars.append((ASCII_CHARS[char_index], (r, g, b)))
    return chars


def generate_ascii(image):
    ascii_data = pixels_to_ascii(image)
    lines = []
    for i in range(0, len(ascii_data), image.width):
        line = ""
        for char, (r, g, b) in ascii_data[i:i + image.width]:
            line += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        lines.append(line)
    return "\n".join(lines)


def build_ascii_from_url(sprite_url):
    fetch_start = time.time()
    image = download_image(sprite_url)
    image = crop_transparent(image)
    image = resize_image(image, new_height=20)
    ascii_art = generate_ascii(image)
    return ascii_art, time.time() - fetch_start


def get_random_pokemon_id():
    return random.randint(1, 1025)


def name_from_index_by_number(pokemon_number, shiny, index):
    """Look up pokemon name from index by number."""
    filename = index.get(cache_key(pokemon_number, shiny), "")
    return filename.replace("_shiny.txt", "").replace(".txt", "") if filename else f"#{pokemon_number}"


def name_from_index_by_name(pokemon_name, shiny, index):
    """Reverse-lookup pokedex number from index by name."""
    filename = cache_filename(pokemon_name, shiny)
    return next((k.replace("_shiny", "") for k, v in index.items() if v == filename), "?")


def print_result(ascii_art, pokemon_name, pokemon_number, shiny, cache_hit, start_time, fetch_time, verbose):
    print(ascii_art)
    shiny_tag = " ✨" if shiny else ""
    print(f"\n{pokemon_name.capitalize()}{shiny_tag} (#{pokemon_number})")
    if verbose:
        total = (time.time() - start_time) * 1000
        if cache_hit:
            print(f"⚡ Cache hit! (resolved in {total:.2f}ms)")
        else:
            print(f"🌐 Fetched from API (took {fetch_time * 1000:.2f}ms, total {total:.2f}ms)")


def handle_fetch_and_display(pokemon_number, pokemon_name, shiny, sprite_url, index, start_time, verbose):
    """Check cache by number+name, fetch if needed, save, and print."""
    cached = get_cached_ascii_by_number(pokemon_number, shiny, index)
    if not cached:
        cached = get_cached_ascii_by_name(pokemon_name, shiny)

    if cached:
        print_result(cached, pokemon_name, pokemon_number, shiny, True, start_time, None, verbose)
        return

    ascii_art, fetch_time = build_ascii_from_url(sprite_url)
    save_ascii(pokemon_name, pokemon_number, shiny, ascii_art, index)
    print_result(ascii_art, pokemon_name, pokemon_number, shiny, False, start_time, fetch_time, verbose)


def main():
    start_time = time.time()
    index = load_index()

    # Strip flags
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    shiny = '--shiny' in sys.argv
    args = [a for a in sys.argv[1:] if a not in ('--verbose', '-v', '--shiny')]

    if not args:
        print("Usage: pokedex <pokemon_name> [--shiny]")
        print("       pokedex --random [--shiny]")
        print("       pokedex --random-cached [--shiny]")
        print("       pokedex --number <pokedex_number> [--shiny]")
        print("       pokedex [-v | --verbose] to show timing info")
        sys.exit(1)

    mode = args[0]

    # --- Random from cache ---
    if mode == '--random-cached':
        matching_keys = [k for k in index if k.endswith('_shiny') == shiny]
        if not matching_keys:
            variant = "shiny" if shiny else "normal"
            print(f"No cached {variant} Pokemon found. Fetch some first!")
            sys.exit(1)
        chosen_key = random.choice(matching_keys)
        filename = index[chosen_key]
        cache_file = os.path.join(CACHE_DIR, filename)
        with open(cache_file, 'r') as f:
            cached = f.read()
        name = filename.replace("_shiny.txt", "").replace(".txt", "")
        number = chosen_key.replace("_shiny", "")
        print_result(cached, name, number, shiny, True, start_time, None, verbose)
        return

    # --- Named lookup ---
    if mode not in ('--random', '--random-cached', '--number'):
        pokemon_name = mode.lower()

        # Check cache first — skip API entirely on hit
        cached = get_cached_ascii_by_name(pokemon_name, shiny)
        if cached:
            number = name_from_index_by_name(pokemon_name, shiny, index)
            print_result(cached, pokemon_name, number, shiny, True, start_time, None, verbose)
            return

        # Cache miss: fetch both sprites in one API call
        pokemon_number, pokemon_name, default_sprite, shiny_sprite = fetch_pokemon(pokemon_name)
        sprite_url = shiny_sprite if shiny else default_sprite
        handle_fetch_and_display(pokemon_number, pokemon_name, shiny, sprite_url, index, start_time, verbose)
        return

    # --- Number lookup ---
    if mode == '--number':
        if len(args) != 2:
            print("Usage: pokedex --number <pokedex_number> [--shiny]")
            sys.exit(1)
        try:
            pid = int(args[1])
            if not (1 <= pid <= 1025):
                raise ValueError
        except ValueError:
            print("Error: Pokedex number must be between 1 and 1025")
            sys.exit(1)

        # Check cache by number first
        cached = get_cached_ascii_by_number(pid, shiny, index)
        if cached:
            name = name_from_index_by_number(pid, shiny, index)
            print_result(cached, name, pid, shiny, True, start_time, None, verbose)
            return

        pokemon_number, pokemon_name, default_sprite, shiny_sprite = fetch_pokemon(pid)
        sprite_url = shiny_sprite if shiny else default_sprite
        handle_fetch_and_display(pokemon_number, pokemon_name, shiny, sprite_url, index, start_time, verbose)
        return

    # --- Random ---
    if mode == '--random':
        pid = get_random_pokemon_id()

        # Check cache by number first
        cached = get_cached_ascii_by_number(pid, shiny, index)
        if cached:
            name = name_from_index_by_number(pid, shiny, index)
            print_result(cached, name, pid, shiny, True, start_time, None, verbose)
            return

        pokemon_number, pokemon_name, default_sprite, shiny_sprite = fetch_pokemon(pid)
        sprite_url = shiny_sprite if shiny else default_sprite
        handle_fetch_and_display(pokemon_number, pokemon_name, shiny, sprite_url, index, start_time, verbose)
        return


if __name__ == "__main__":
    main()
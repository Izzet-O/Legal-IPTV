import re
import requests
import sys
import json
import os
from urllib.parse import urljoin
from slugify import slugify
from tqdm import tqdm

def get_stream_url(url, pattern, method="GET", headers=None, body=None, timeout=10):
    headers = headers or {}
    body = body or {}
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == "POST":
            r = requests.post(url, json=body, headers=headers, timeout=timeout)
        else:
            print(f"⚠️ Warning: HTTP method {method!r} not supported for URL {url!r}")
            return None
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Warning: failed to fetch URL {url!r}: {e}")
        return None

    results = re.findall(pattern, r.text)
    if results:
        return results[0]
    else:
        print(f"⚠️ Warning: no regex match for pattern {pattern!r} on URL {url!r}")
        return None

def playlist_text(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        text = ""
        for line in r.iter_lines():
            line = line.decode("utf-8", errors="ignore")
            if not line:
                continue
            if line.startswith("#"):
                text += line + "\n"
            else:
                text += urljoin(url, line) + "\n"
        return text
    except Exception as e:
        print(f"⚠️ Warning: failed to fetch playlist {url!r}: {e}")
        return ""

def main():
    if len(sys.argv) < 2:
        print("Usage: build_playlists.py path/to/config.json")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error: could not load config file {config_path!r}: {e}")
        sys.exit(1)

    for site in config:
        slug = site.get("slug")
        site_dir = os.path.join(os.getcwd(), slug)
        os.makedirs(site_dir, exist_ok=True)

        for channel in tqdm(site.get("channels", []), desc=f"Building {slug}", unit="channel"):
            name = channel.get("name", "")
            filename = slugify(name.lower()) + ".m3u8"
            filepath = os.path.join(site_dir, filename)

            # Build the raw channel URL by replacing variables
            channel_url = site.get("url", "")
            for var in channel.get("variables", []):
                channel_url = channel_url.replace(var.get("name", ""), var.get("value", ""))

            stream_url = get_stream_url(
                channel_url,
                site.get("pattern", ""),
                method=site.get("method", "GET"),
                headers=site.get("headers", {}),
                body=site.get("body", {}),
            )
            if not stream_url:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                continue

            output_filter = site.get("output_filter")
            if output_filter and output_filter not in stream_url:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                continue

            mode = site.get("mode")
            if mode == "variant":
                playlist = playlist_text(stream_url)
            elif mode == "master":
                bandwidth = site.get("bandwidth", "")
                playlist = (
                    "#EXTM3U\n"
                    "#EXT-X-VERSION:3\n"
                    f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth}\n"
                    f"{stream_url}\n"
                )
            else:
                print(f"⚠️ Warning: unknown mode {mode!r} for site {slug}")
                playlist = ""

            if playlist:
                try:
                    with open(filepath, "w", encoding="utf-8") as out:
                        out.write(playlist)
                except Exception as e:
                    print(f"Error writing file {filepath!r}: {e}")
            else:
                if os.path.isfile(filepath):
                    os.remove(filepath)

if __name__ == "__main__":
    main()

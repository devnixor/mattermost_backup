"""
mattermost_backup.py – Backup rozmów z Mattermost do plików JSON i Markdown
Analogiczny do skryptu eksportu kanałów autorstwa RobertKrajewski (https://gist.github.com/RobertKrajewski/5847ce49333062ea4be1a08f2913288c).

Wymagania:
    pip install mattermostdriver

Użycie:
    python mattermost_backup.py
    python mattermost_backup.py --config config.json
    python mattermost_backup.py --format markdown
    python mattermost_backup.py --after 2024-01-01 --before 2024-12-31
"""

import argparse
import getpass
import json
import os
import pathlib
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from mattermostdriver import Driver


# ── Połączenie ────────────────────────────────────────────────────────────────

def connect(host: str, login_token: str = None, username: str = None, password: str = None) -> Driver:
    d = Driver({
        "url": host,
        "port": 443,
        "token": login_token,
        "username": username,
        "password": password,
    })
    d.login()
    return d


# ── Użytkownicy ───────────────────────────────────────────────────────────────

def get_users(d: Driver) -> Tuple[Dict[str, str], str]:
    my_user = d.users.get_user("me")
    my_username = my_user["username"]
    my_user_id = my_user["id"]
    print(f"Zalogowano jako {my_username} ({my_user_id})")

    user_id_to_name = {}
    page = 0
    print("Pobieranie listy użytkowników... ", end="", flush=True)
    while True:
        users_resp = d.users.get_users(params={"per_page": 200, "page": page})
        if not users_resp:
            break
        for user in users_resp:
            user_id_to_name[user["id"]] = user["username"]
        page += 1
    print(f"Znaleziono {len(user_id_to_name)} użytkowników.")
    return user_id_to_name, my_user_id


def resolve_username(d: Driver, user_id: str, user_id_to_name: Dict[str, str]) -> str:
    if user_id not in user_id_to_name:
        try:
            user_id_to_name[user_id] = d.users.get_user(user_id)["username"]
        except Exception:
            user_id_to_name[user_id] = f"unknown({user_id[:8]})"
    return user_id_to_name[user_id]


# ── Wybór zespołu ─────────────────────────────────────────────────────────────

def select_team(d: Driver, my_user_id: str) -> dict:
    teams = d.teams.get_user_teams(my_user_id)
    print(f"\nDostępne zespoły ({len(teams)}):")
    for i, team in enumerate(teams):
        print(f"  {i}\t{team['name']}\t({team['id']})")
    team_idx = int(input("Wybierz zespół (numer): "))
    team = teams[team_idx]
    print(f"Wybrany zespół: {team['name']}")
    return team


# ── Wybór kanałów ─────────────────────────────────────────────────────────────

def select_channels(d: Driver, team: dict, my_user_id: str,
                    user_id_to_name: Dict[str, str]) -> List[dict]:
    print("Pobieranie listy kanałów... ", end="", flush=True)
    channels = d.channels.get_channels_for_user(my_user_id, team["id"])

    # Uzupełnij display_name dla wiadomości bezpośrednich (DM)
    for ch in channels:
        if ch["type"] == "D":
            parts = ch["name"].split("__")
            other_id = parts[1] if parts[0] == my_user_id else parts[0]
            ch["display_name"] = resolve_username(d, other_id, user_id_to_name)

    channels = sorted(channels, key=lambda x: x["display_name"].lower())
    print(f"Znaleziono {len(channels)} kanałów.")

    type_labels = {"O": "publiczny", "P": "prywatny", "D": "DM", "G": "grupowy"}
    for i, ch in enumerate(channels):
        typ = type_labels.get(ch["type"], ch["type"])
        print(f"  {i:3d}\t[{typ:8s}]\t{ch['display_name']}")

    choice = input("\nPodaj numery kanałów oddzielone przecinkami lub 'all': ").strip()
    if choice.lower() == "all":
        selected = channels
    else:
        idxs = [int(x.strip()) for x in choice.split(",")]
        selected = [channels[i] for i in idxs]

    print("Wybrane kanały:", ", ".join(ch["display_name"] for ch in selected))
    return selected


# ── Pobieranie postów ─────────────────────────────────────────────────────────

def fetch_all_posts(d: Driver, channel_id: str) -> List[dict]:
    """Fetch all posts from a channel with pagination."""
    all_posts = []
    page = 0
    while True:
        print(f"  Page {page}... ", end="", flush=True)
        resp = d.posts.get_posts_for_channel(channel_id, params={"per_page": 200, "page": page})
        batch = resp.get("posts", {})
        order = resp.get("order", [])
        if not order:
            print("done.")
            break
        all_posts.extend([batch[pid] for pid in order if pid in batch])
        print(f"{len(all_posts)} posts total")
        page += 1
    return all_posts


def fetch_pinned_posts(d: Driver, channel_id: str) -> set:
    """Return a set of post IDs that are pinned in the given channel."""
    try:
        resp = d.client.get(f"/channels/{channel_id}/pinned")
        return set(resp.get("order", []))
    except Exception as e:
        print(f"  [!] Could not fetch pinned posts: {e}")
        return set()


# ── Eksport ───────────────────────────────────────────────────────────────────

def export_channel(
    d: Driver,
    channel: dict,
    user_id_to_name: Dict[str, str],
    output_base: str,
    download_files: bool = True,
    export_format: str = "json",
    after: Optional[str] = None,
    before: Optional[str] = None,
):
    channel_name = channel["display_name"].replace("\\", "").replace("/", "")
    print(f"\n── Eksportuję kanał: {channel_name} ──")

    after_ts = datetime.strptime(after, "%Y-%m-%d").timestamp() if after else None
    before_ts = datetime.strptime(before, "%Y-%m-%d").timestamp() if before else None

    raw_posts = fetch_all_posts(d, channel["id"])
    print(f"  Fetched {len(raw_posts)} posts")

    pinned_ids = fetch_pinned_posts(d, channel["id"])
    if pinned_ids:
        print(f"  Pinned posts: {len(pinned_ids)}")

    out_dir = pathlib.Path(output_base) / "".join(
        c for c in channel_name if c not in r'?!/\\.;:*"<>|'
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # Buduj wątki: post główny → lista odpowiedzi
    threads: Dict[str, List[dict]] = {}
    for post in reversed(raw_posts):  # chronologicznie
        ts = post["create_at"] / 1000
        if (after_ts and ts < after_ts) or (before_ts and ts > before_ts):
            continue
        root_id = post.get("root_id") or post["id"]
        threads.setdefault(root_id, []).append(post)

    simple_posts = []
    for i_post, post in enumerate(reversed(raw_posts)):
        ts = post["create_at"] / 1000
        if (after_ts and ts < after_ts) or (before_ts and ts > before_ts):
            continue

        username = resolve_username(d, post["user_id"], user_id_to_name)
        created = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
        message = post.get("message", "")

        simple = {
            "idx": i_post,
            "id": post["id"],
            "root_id": post.get("root_id", ""),
            "created": created,
            "username": username,
            "message": message,
            "pinned": post["id"] in pinned_ids,
        }

        # Zapis fragmentów kodu do osobnych plików
        if message.count("```") > 1:
            start = message.find("```") + 3
            end = message.rfind("```")
            code = message[start:end]
            if code.strip():
                code_file = out_dir / f"{i_post:04d}_code.txt"
                code_file.write_bytes(code.encode("utf-8"))

        # Pobieranie załączników
        if download_files and "files" in post.get("metadata", {}):
            filenames = []
            for file_meta in post["metadata"]["files"]:
                fname = f"{i_post:04d}_{file_meta['name']}"
                print(f"  Pobieranie pliku: {file_meta['name']}")
                try:
                    resp = d.files.get_file(file_meta["id"])
                    fpath = out_dir / fname
                    if isinstance(resp, dict):
                        fpath.write_text(json.dumps(resp), encoding="utf-8")
                    else:
                        fpath.write_bytes(resp.content)
                    filenames.append(fname)
                except Exception as e:
                    print(f"  [!] Błąd pobierania pliku: {e}")
            if filenames:
                simple["files"] = filenames

        simple_posts.append(simple)

    # Metadane kanału
    team_name = ""
    try:
        team_name = d.teams.get_team(channel.get("team_id", ""))["name"]
    except Exception:
        pass

    output_data = {
        "channel": {
            "id": channel["id"],
            "name": channel["name"],
            "display_name": channel["display_name"],
            "type": channel["type"],
            "header": channel.get("header", ""),
            "team": team_name,
            "team_id": channel.get("team_id", ""),
            "exported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "posts": simple_posts,
    }

    safe_name = "".join(c for c in channel_name if c not in r'?!/\\.;:*"<>|')

    if export_format in ("json", "both"):
        json_path = out_dir / f"{safe_name}.json"
        json_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✓ JSON: {json_path}")

    if export_format in ("markdown", "both"):
        md_path = out_dir / f"{safe_name}.md"
        _write_markdown(output_data, md_path)
        print(f"  ✓ Markdown: {md_path}")


def _write_markdown(data: dict, path: pathlib.Path):
    ch = data["channel"]
    lines = [
        f"# {ch['display_name']}",
        f"",
        f"| Pole | Wartość |",
        f"|------|---------|",
        f"| Kanał | `{ch['name']}` |",
        f"| Typ | {ch['type']} |",
        f"| Zespół | {ch['team']} |",
        f"| Eksport | {ch['exported_at']} |",
        f"",
        "---",
        "",
    ]
    for post in data["posts"]:
        lines.append(f"**{post['username']}** – {post['created']}")
        if post.get("root_id"):
            lines.append(f"> ↩ odpowiedź w wątku `{post['root_id'][:8]}`")
        lines.append("")
        lines.append(post["message"] or "_[pusta wiadomość]_")
        if post.get("files"):
            lines.append("")
            lines.append("📎 Załączniki: " + ", ".join(post["files"]))
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Konfiguracja ──────────────────────────────────────────────────────────────

def load_config(filename: str = "config.json") -> dict:
    p = pathlib.Path(filename)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict, filename: str = "config.json"):
    safe = {k: v for k, v in config.items() if k != "password"}
    pathlib.Path(filename).write_text(json.dumps(safe, indent=2), encoding="utf-8")
    print(f"Konfiguracja zapisana do {filename}")


def complete_config(config: dict, config_file: str = "config.json") -> dict:
    changed = False

    if config.get("host"):
        print(f"Host: {config['host']}")
    else:
        config["host"] = input("Adres serwera (bez https://): ").strip()
        changed = True

    if config.get("login_mode"):
        print(f"Tryb logowania: {config['login_mode']}")
    else:
        mode = ""
        while mode not in ("password", "token"):
            mode = input("Tryb logowania – 'password' lub 'token': ").strip()
        config["login_mode"] = mode
        changed = True

    password = None
    if config["login_mode"] == "password":
        if not config.get("username"):
            config["username"] = input("Nazwa użytkownika: ").strip()
            changed = True
        else:
            print(f"Użytkownik: {config['username']}")
        password = getpass.getpass("Hasło (ukryte): ")
    else:
        if not config.get("token"):
            print("Czy chcesz spróbować automatycznie znaleźć token z Firefox?")
            ans = ""
            while ans not in ("y", "n"):
                ans = input("y/n: ").strip().lower()
            token = None
            if ans == "y":
                token = _find_token_firefox(config["host"])
            if not token:
                token = input("Wklej token (MMAUTHTOKEN): ").strip()
            config["token"] = token
            changed = True
        else:
            print(f"Token: {config['token'][:12]}…")

    if "download_files" not in config:
        ans = ""
        while ans not in ("y", "n"):
            ans = input("Pobierać załączniki? y/n: ").strip().lower()
        config["download_files"] = ans == "y"
        changed = True

    if "export_format" not in config:
        fmt = ""
        while fmt not in ("json", "markdown", "both"):
            fmt = input("Format eksportu (json / markdown / both): ").strip().lower()
        config["export_format"] = fmt
        changed = True

    if changed:
        ans = ""
        while ans not in ("y", "n"):
            ans = input("Zapisać konfigurację (bez hasła) do pliku? y/n: ").strip().lower()
        if ans == "y":
            save_config(config, config_file)

    config["password"] = password
    return config


def _find_token_firefox(host: str) -> Optional[str]:
    import shutil, tempfile
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    profiles = pathlib.Path(appdata) / "Mozilla/Firefox/Profiles"
    tokens = []
    for cookie_file in profiles.rglob("cookies.sqlite"):
        print(f"  Sprawdzam {cookie_file}")
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(str(cookie_file), tmp_path)
            conn = sqlite3.connect(tmp_path)
            rows = conn.execute(
                "SELECT host, value FROM moz_cookies WHERE name = 'MMAUTHTOKEN'"
            ).fetchall()
            conn.close()
            os.unlink(tmp_path)
            tokens.extend([(h, v) for h, v in rows if host in h])
        except Exception as e:
            print(f"  Błąd: {e}")
    if not tokens:
        return None
    print(f"Znaleziono {len(tokens)} token(ów) dla {host}")
    return tokens[0][1]


# ── Główna pętla ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backup rozmów z Mattermost")
    parser.add_argument("--config", default="config.json", help="Plik konfiguracyjny")
    parser.add_argument("--format", dest="fmt", choices=["json", "markdown", "both"],
                        help="Format eksportu (nadpisuje config)")
    parser.add_argument("--after", help="Eksportuj posty po dacie (YYYY-MM-DD)")
    parser.add_argument("--before", help="Eksportuj posty przed datą (YYYY-MM-DD)")
    args = parser.parse_args()

    config = load_config(args.config)
    config = complete_config(config, args.config)

    # Argumenty CLI nadpisują config
    if args.fmt:
        config["export_format"] = args.fmt
    after = args.after or config.get("after")
    before = args.before or config.get("before")

    output_base = f"results/{date.today().strftime('%Y%m%d')}"
    print(f"\nWyniki będą zapisane w: {output_base}")

    d = connect(
        config["host"],
        config.get("token"),
        config.get("username"),
        config.get("password"),
    )
    user_id_to_name, my_user_id = get_users(d)
    team = select_team(d, my_user_id)
    channels = select_channels(d, team, my_user_id, user_id_to_name)

    for i, channel in enumerate(channels, 1):
        print(f"\n[{i}/{len(channels)}] ", end="")
        export_channel(
            d, channel, user_id_to_name, output_base,
            download_files=config.get("download_files", True),
            export_format=config.get("export_format", "json"),
            after=after,
            before=before,
        )

    print("\n✓ Eksport zakończony!")


if __name__ == "__main__":
    main()

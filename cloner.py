import base64
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import textwrap
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    pass

import requests

VERSION = "1.0"
CONFIG_PATH = Path(__file__).with_name("config.json")
BACKUPS_DIR = Path(__file__).parent / "backups"
LOGS_PATH = Path(__file__).parent / "logs.txt"

YELLOW = "\033[93m"
BLUE = "\033[94m"
WHITE = "\033[97m"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"
CYAN = "\033[96m"
DIM = "\033[90m"
BOLD = "\033[1m"


def clear() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


def set_title(title: str) -> None:
    if os.name == "nt":
        os.system(f"title {title}")
    else:
        print(f"\033]0;{title}\007", end="")


def current_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _ui_layout() -> Tuple[int, str]:
    columns = max(20, shutil.get_terminal_size((100, 30)).columns)
    width = min(88, max(18, columns - 4))
    return width, " " * max(0, (columns - width) // 2)


def _ui_rule(title: str = "", bottom: bool = False) -> None:
    width, indent = _ui_layout()
    label = (f" {title} " if title else "")[:width - 4]
    print(f"{indent}{DIM}+-{CYAN}{label}{DIM}{'-' * (width - 3 - len(label))}+{RESET}")


def _ui_line(text: str = "", color: str = WHITE, center: bool = False) -> None:
    width, indent = _ui_layout()
    plain = re.sub(r"\x1b\[[0-9;]*m", "", str(text))
    for line in textwrap.wrap(plain, width=width - 6) or [""]:
        aligned = line.center(width - 6) if center else line.ljust(width - 6)
        print(f"{indent}{DIM}|{RESET}  {color}{aligned}{RESET}  {DIM}|{RESET}")


def _ui_metric(label: str, value: str, color: str = GREEN) -> None:
    width, indent = _ui_layout()
    label_width = min(38, max(12, width // 2))
    text = f"{label:<{label_width}}  {value}"
    for line in textwrap.wrap(text, width=width - 4, replace_whitespace=False) or [""]:
        print(f"{indent}  {color}{line}{RESET}")


def _ui_prompt(label: str) -> str:
    _, indent = _ui_layout()
    label = re.sub(r"\x1b\[[0-9;]*m", "", label).rstrip(": ")
    return f"\n{indent}{BLUE}[{CYAN}>{BLUE}]{RESET} {WHITE}{label}{RESET} {CYAN}> {RESET}"


def pause(message: str = "Press ENTER to return to the menu...") -> None:
    input(_ui_prompt(message))


def answer_yes(question: str, default: bool = False) -> bool:
    options = " [Y/n]" if default else " [y/N]"
    answer = input(_ui_prompt(question + options)).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def log_action(status: str, text: str, color: str = WHITE) -> None:
    width, indent = _ui_layout()
    ts = current_time()
    label = f"[{ts}] [{status}] "
    log_line = f"[{ts}] [{status}] {text}\n"
    try:
        with open(LOGS_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass

    for number, line in enumerate(textwrap.wrap(str(text), width=max(10, width - len(label))) or [""]):
        prefix = label if number == 0 else " " * len(label)
        print(f"{indent}{DIM}{prefix}{color}{line}{RESET}")


def show_header() -> None:
    width, indent = _ui_layout()
    art = (
        r" ____   ___ _____   _____ _     _______  __ ",
        r"|  _ \ / _ \_   _| |  ___| |   | ____\ \/ / ",
        r"| | | | | | || |   | |_  | |   |  _|  \  /  ",
        r"| |_| | |_| || |   |  _| | |___| |___ /  \  ",
        r"|____/ \___/ |_|   |_|   |_____|_____/_/\_\ ",
        r"                 C L O N E R                ",
    )
    print()
    art_width = max(map(len, art))
    if width >= art_width:
        for i, line in enumerate(art):
            line_color = [BLUE, BLUE, CYAN, CYAN, WHITE, DIM][i % 6]
            print(f"{indent}{BOLD}{line_color}{line.center(width)}{RESET}")
    else:
        print(f"{indent}{CYAN}{'DOT FLEX CLONER'.center(width)}{RESET}")
    print(f"{indent}{DIM}{f'v{VERSION}'.center(width)}{RESET}")
    print()


def load_config() -> Dict[str, Any]:
    default_config = {
        "token": "",
        "is_bot": True,
        "request_delay": 0.4,
        "clone_settings": {
            "clone_roles": True,
            "clone_categories": True,
            "clone_channels": True,
            "clone_emojis": True,
            "clone_server_name": True,
            "clone_server_icon": True,
            "clear_target_channels": True,
            "clear_target_roles": False,
        },
    }
    if not CONFIG_PATH.is_file():
        save_config(default_config)
        return default_config
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_config
            return {**default_config, **data}
    except Exception:
        return default_config


def save_config(config: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        log_action("ERROR", f"Failed to save config: {e}", RED)


class DiscordAPI:
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, token: str, is_bot: bool = True, request_delay: float = 0.4):
        self.token = token.strip()
        self.is_bot = is_bot
        self.request_delay = request_delay
        self.session = requests.Session()

    def get_headers(self) -> Dict[str, str]:
        if self.is_bot:
            auth_val = f"Bot {self.token}" if not self.token.lower().startswith("bot ") else self.token
            ua = "DotFlexCloner/1.0 (Python/Requests)"
        else:
            auth_val = self.token
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        return {
            "Authorization": auth_val,
            "Content-Type": "application/json",
            "User-Agent": ua,
        }

    def request(self, method: str, endpoint: str, json_data: Any = None, max_retries: int = 5) -> Optional[requests.Response]:
        url = f"{self.BASE_URL}{endpoint}"
        headers = self.get_headers()

        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, headers=headers, timeout=20)
                elif method.upper() == "POST":
                    resp = self.session.post(url, headers=headers, json=json_data, timeout=20)
                elif method.upper() == "PATCH":
                    resp = self.session.patch(url, headers=headers, json=json_data, timeout=20)
                elif method.upper() == "PUT":
                    resp = self.session.put(url, headers=headers, json=json_data, timeout=20)
                elif method.upper() == "DELETE":
                    resp = self.session.delete(url, headers=headers, timeout=20)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if resp.status_code == 429:
                    try:
                        retry_info = resp.json()
                        retry_after = float(retry_info.get("retry_after", 1.5))
                    except Exception:
                        retry_after = 2.0
                    log_action("RATE-LIMIT", f"Rate limited. Sleeping {retry_after:.2f}s...", YELLOW)
                    time.sleep(retry_after + 0.2)
                    continue

                if self.request_delay > 0 and method.upper() in {"POST", "PATCH", "DELETE", "PUT"}:
                    time.sleep(self.request_delay)

                return resp
            except requests.exceptions.RequestException as e:
                log_action("NET-ERROR", f"Attempt {attempt+1}/{max_retries} failed: {e}", RED)
                time.sleep(1.0)

        return None

    def validate_token(self) -> Tuple[bool, str]:
        resp = self.request("GET", "/users/@me")
        if resp and resp.status_code == 200:
            user_data = resp.json()
            username = f"{user_data.get('username')}#{user_data.get('discriminator', '0')}"
            return True, username
        return False, "Invalid token or unauthorized."

    def get_guild(self, guild_id: str) -> Optional[Dict[str, Any]]:
        resp = self.request("GET", f"/guilds/{guild_id}?with_counts=true")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    def get_guild_roles(self, guild_id: str) -> List[Dict[str, Any]]:
        resp = self.request("GET", f"/guilds/{guild_id}/roles")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    def get_guild_channels(self, guild_id: str) -> List[Dict[str, Any]]:
        resp = self.request("GET", f"/guilds/{guild_id}/channels")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    def get_guild_emojis(self, guild_id: str) -> List[Dict[str, Any]]:
        resp = self.request("GET", f"/guilds/{guild_id}/emojis")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    def wipe_channels(self, guild_id: str) -> int:
        channels = self.get_guild_channels(guild_id)
        deleted_count = 0
        log_action("WIPE", f"Found {len(channels)} channels to remove on target server...", CYAN)
        for ch in channels:
            res = self.request("DELETE", f"/channels/{ch['id']}")
            if res and res.status_code in {200, 204}:
                deleted_count += 1
                log_action("DELETE", f"Removed channel #{ch['name']} ({ch['id']})", DIM)
            else:
                log_action("WARN", f"Failed removing channel #{ch['name']}", YELLOW)
        return deleted_count

    def wipe_roles(self, guild_id: str) -> int:
        roles = self.get_guild_roles(guild_id)
        deleted_count = 0
        for r in roles:
            if r.get("name") == "@everyone" or r.get("id") == guild_id or r.get("managed"):
                continue
            res = self.request("DELETE", f"/guilds/{guild_id}/roles/{r['id']}")
            if res and res.status_code in {200, 204}:
                deleted_count += 1
                log_action("DELETE", f"Removed role @{r['name']}", DIM)
            else:
                log_action("WARN", f"Could not remove role @{r['name']}", YELLOW)
        return deleted_count

    def download_image_as_b64(self, url: str) -> Optional[str]:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                content_type = r.headers.get("Content-Type", "image/png")
                b64_str = base64.b64encode(r.content).decode("utf-8")
                return f"data:{content_type};base64,{b64_str}"
        except Exception:
            pass
        return None


class ServerCloner:
    def __init__(self, api: DiscordAPI, settings: Dict[str, Any]):
        self.api = api
        self.settings = settings

    def export_server(self, guild_id: str) -> Optional[Dict[str, Any]]:
        log_action("FETCH", f"Fetching source server info for ID: {guild_id}...", CYAN)
        guild = self.api.get_guild(guild_id)
        if not guild:
            log_action("ERROR", f"Could not fetch server {guild_id}. Verify bot permissions or ID.", RED)
            return None

        server_name = guild.get("name", "Unknown")
        log_action("FOUND", f"Connected to server: {server_name}", GREEN)

        roles = self.api.get_guild_roles(guild_id)
        log_action("FETCH", f"Fetched {len(roles)} roles.", CYAN)

        channels = self.api.get_guild_channels(guild_id)
        log_action("FETCH", f"Fetched {len(channels)} channels.", CYAN)

        emojis = self.api.get_guild_emojis(guild_id)
        log_action("FETCH", f"Fetched {len(emojis)} emojis.", CYAN)

        icon_url = None
        icon_b64 = None
        if guild.get("icon"):
            ext = "gif" if guild["icon"].startswith("a_") else "png"
            icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{guild['icon']}.{ext}"
            icon_b64 = self.api.download_image_as_b64(icon_url)

        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "guild": {
                "id": guild_id,
                "name": server_name,
                "icon_url": icon_url,
                "icon_b64": icon_b64,
                "description": guild.get("description"),
            },
            "roles": roles,
            "channels": channels,
            "emojis": emojis,
        }
        return data

    def save_backup_file(self, data: Dict[str, Any]) -> Path:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        guild_name = re.sub(r'[\\/*?:"<>| ]', "_", data["guild"]["name"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{guild_name}_{ts}.json"
        path = BACKUPS_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def clone_from_data(self, data: Dict[str, Any], target_guild_id: str) -> bool:
        target_guild = self.api.get_guild(target_guild_id)
        if not target_guild:
            log_action("ERROR", f"Could not access target server {target_guild_id}.", RED)
            return False

        target_name = target_guild.get("name", "Unknown")
        log_action("TARGET", f"Target Server: {target_name} ({target_guild_id})", GREEN)

        clone_opts = self.settings.get("clone_settings", {})

        if clone_opts.get("clear_target_channels", True):
            log_action("PROCESS", "Clearing existing target channels...", YELLOW)
            self.api.wipe_channels(target_guild_id)

        if clone_opts.get("clear_target_roles", False):
            log_action("PROCESS", "Clearing existing target roles...", YELLOW)
            self.api.wipe_roles(target_guild_id)

        if clone_opts.get("clone_server_name", True) or clone_opts.get("clone_server_icon", True):
            patch_payload: Dict[str, Any] = {}
            if clone_opts.get("clone_server_name", True):
                patch_payload["name"] = data["guild"]["name"]
            if clone_opts.get("clone_server_icon", True) and data["guild"].get("icon_b64"):
                patch_payload["icon"] = data["guild"]["icon_b64"]
            if patch_payload:
                res = self.api.request("PATCH", f"/guilds/{target_guild_id}", patch_payload)
                if res and res.status_code == 200:
                    log_action("SUCCESS", "Updated target server name/icon.", GREEN)
                else:
                    log_action("WARN", "Could not update server name/icon.", YELLOW)

        role_mapping: Dict[str, str] = {
            data["guild"]["id"]: target_guild_id,
        }

        if clone_opts.get("clone_roles", True):
            log_action("PROCESS", "Cloning roles...", CYAN)
            target_roles = self.api.get_guild_roles(target_guild_id)
            target_everyone = next((r for r in target_roles if r.get("name") == "@everyone" or r.get("id") == target_guild_id), None)
            source_everyone = next((r for r in data["roles"] if r.get("name") == "@everyone" or r.get("id") == data["guild"]["id"]), None)

            if target_everyone and source_everyone:
                role_mapping[source_everyone["id"]] = target_everyone["id"]
                self.api.request(
                    "PATCH",
                    f"/guilds/{target_guild_id}/roles/{target_everyone['id']}",
                    {"permissions": str(source_everyone.get("permissions", "0"))},
                )
                log_action("SUCCESS", "Updated target @everyone permissions.", GREEN)

            roles_to_create = [
                r for r in data["roles"]
                if not r.get("managed") and r.get("name") != "@everyone" and r.get("id") != data["guild"]["id"]
            ]
            roles_to_create.sort(key=lambda x: x.get("position", 0))

            for r in roles_to_create:
                payload = {
                    "name": r["name"],
                    "permissions": str(r.get("permissions", "0")),
                    "color": r.get("color", 0),
                    "hoist": r.get("hoist", False),
                    "mentionable": r.get("mentionable", False),
                }
                res = self.api.request("POST", f"/guilds/{target_guild_id}/roles", payload)
                if res and res.status_code in {200, 201}:
                    new_role = res.json()
                    role_mapping[r["id"]] = new_role["id"]
                    log_action("ROLE", f"Created role: @{r['name']}", GREEN)
                else:
                    log_action("WARN", f"Failed creating role: @{r['name']}", YELLOW)

        category_mapping: Dict[str, str] = {}
        all_channels = data.get("channels", [])

        def map_overwrites(overwrites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            mapped = []
            for ow in overwrites:
                ow_type = ow.get("type", 0)
                old_id = str(ow.get("id"))
                if ow_type == 0:
                    if old_id in role_mapping:
                        mapped.append({
                            "id": role_mapping[old_id],
                            "type": 0,
                            "allow": str(ow.get("allow", "0")),
                            "deny": str(ow.get("deny", "0")),
                        })
            return mapped

        if clone_opts.get("clone_categories", True):
            log_action("PROCESS", "Cloning categories...", CYAN)
            categories = [ch for ch in all_channels if ch.get("type") == 4]
            categories.sort(key=lambda x: x.get("position", 0))

            for cat in categories:
                cat_payload = {
                    "name": cat["name"],
                    "type": 4,
                    "position": cat.get("position", 0),
                    "permission_overwrites": map_overwrites(cat.get("permission_overwrites", [])),
                }
                res = self.api.request("POST", f"/guilds/{target_guild_id}/channels", cat_payload)
                if res and res.status_code in {200, 201}:
                    new_cat = res.json()
                    category_mapping[cat["id"]] = new_cat["id"]
                    log_action("CATEGORY", f"Created category: {cat['name']}", GREEN)
                else:
                    log_action("WARN", f"Failed creating category: {cat['name']}", YELLOW)

        if clone_opts.get("clone_channels", True):
            log_action("PROCESS", "Cloning channels...", CYAN)
            channels = [ch for ch in all_channels if ch.get("type") != 4]
            channels.sort(key=lambda x: x.get("position", 0))

            for ch in channels:
                old_parent = ch.get("parent_id")
                new_parent = category_mapping.get(old_parent) if old_parent else None

                ch_payload = {
                    "name": ch["name"],
                    "type": ch.get("type", 0),
                    "position": ch.get("position", 0),
                    "topic": ch.get("topic"),
                    "nsfw": ch.get("nsfw", False),
                    "permission_overwrites": map_overwrites(ch.get("permission_overwrites", [])),
                }
                if new_parent:
                    ch_payload["parent_id"] = new_parent

                if ch.get("type") in {2, 13}:
                    if ch.get("bitrate"):
                        ch_payload["bitrate"] = min(ch["bitrate"], 96000)
                    if ch.get("user_limit") is not None:
                        ch_payload["user_limit"] = ch["user_limit"]

                if ch.get("rate_limit_per_user"):
                    ch_payload["rate_limit_per_user"] = ch["rate_limit_per_user"]

                res = self.api.request("POST", f"/guilds/{target_guild_id}/channels", ch_payload)
                if res and res.status_code in {200, 201}:
                    log_action("CHANNEL", f"Created channel #{ch['name']}", GREEN)
                else:
                    log_action("WARN", f"Failed creating channel #{ch['name']}", YELLOW)

        if clone_opts.get("clone_emojis", True):
            emojis = data.get("emojis", [])
            if emojis:
                log_action("PROCESS", f"Cloning {len(emojis)} custom emojis...", CYAN)
                for emoji in emojis:
                    emoji_id = emoji["id"]
                    is_animated = emoji.get("animated", False)
                    ext = "gif" if is_animated else "png"
                    img_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
                    img_b64 = self.api.download_image_as_b64(img_url)
                    if img_b64:
                        emoji_payload = {
                            "name": emoji["name"],
                            "image": img_b64,
                        }
                        res = self.api.request("POST", f"/guilds/{target_guild_id}/emojis", emoji_payload)
                        if res and res.status_code in {200, 201}:
                            log_action("EMOJI", f"Created emoji :{emoji['name']}:", GREEN)
                        else:
                            log_action("WARN", f"Failed uploading emoji :{emoji['name']}:", YELLOW)

        log_action("COMPLETE", "Server cloning process finished successfully!", GREEN)
        return True


def ensure_token(config: Dict[str, Any]) -> Tuple[DiscordAPI, Dict[str, Any]]:
    token = config.get("token", "").strip()
    is_bot = config.get("is_bot", True)
    request_delay = config.get("request_delay", 0.4)

    if not token:
        clear()
        show_header()
        _ui_rule("AUTHENTICATION")
        _ui_line("Please enter your Discord Bot Token (or User Token):", WHITE)
        _ui_rule(bottom=True)
        token = input(_ui_prompt("Token")).strip()
        if not token:
            print(f"{RED}Token cannot be empty.{RESET}")
            sys.exit(1)

        is_bot = not answer_yes("Are you using a User Token (Self-bot)?", default=False)
        config["token"] = token
        config["is_bot"] = is_bot

        if answer_yes("Do you want to save this token to config.json?", default=True):
            save_config(config)

    api = DiscordAPI(token, is_bot=is_bot, request_delay=request_delay)
    valid, info = api.validate_token()
    if not valid:
        log_action("ERROR", f"Token authentication failed: {info}", RED)
        if answer_yes("Would you like to reset the saved token in config.json?", default=True):
            config["token"] = ""
            save_config(config)
        pause("Press ENTER to exit...")
        sys.exit(1)

    return api, config


def show_menu(account_info: str) -> None:
    clear()
    set_title(f"Dot Flex Cloner v{VERSION}")
    show_header()
    _ui_rule("DOT FLEX CLONER WORKSPACE")
    for item in (
        "01  DIRECT SERVER CLONE (SOURCE -> TARGET)",
        "02  BACKUP SERVER TO FILE",
        "03  RESTORE SERVER FROM BACKUP FILE",
        "04  CLEAN / WIPE TARGET SERVER",
    ):
        _ui_line(item, CYAN)
        _ui_line()
    _ui_rule(bottom=True)
    _ui_rule("SESSION & SETTINGS")
    _ui_line("05  SETTINGS & TOGGLES       06  EXIT", WHITE)
    _ui_rule(bottom=True)
    _ui_metric("LOGGED IN AS", account_info, GREEN)
    _ui_metric("BACKUPS FOLDER", str(BACKUPS_DIR.resolve()), DIM)


def handle_settings(config: Dict[str, Any]) -> None:
    while True:
        clear()
        show_header()
        _ui_rule("CLONER SETTINGS")
        opts = config.get("clone_settings", {})
        _ui_line(f"1. Clone Roles:            [{'ON' if opts.get('clone_roles') else 'OFF'}]", CYAN)
        _ui_line(f"2. Clone Categories:       [{'ON' if opts.get('clone_categories') else 'OFF'}]", CYAN)
        _ui_line(f"3. Clone Channels:         [{'ON' if opts.get('clone_channels') else 'OFF'}]", CYAN)
        _ui_line(f"4. Clone Emojis:           [{'ON' if opts.get('clone_emojis') else 'OFF'}]", CYAN)
        _ui_line(f"5. Clone Server Name/Icon: [{'ON' if opts.get('clone_server_name') else 'OFF'}]", CYAN)
        _ui_line(f"6. Clear Target Channels:  [{'ON' if opts.get('clear_target_channels') else 'OFF'}]", YELLOW)
        _ui_line(f"7. Clear Target Roles:     [{'ON' if opts.get('clear_target_roles') else 'OFF'}]", RED)
        _ui_line(f"8. Request Delay (seconds): {config.get('request_delay', 0.4)}s", WHITE)
        _ui_line("9. Change Token", WHITE)
        _ui_line("0. Back to Main Menu", WHITE)
        _ui_rule(bottom=True)

        choice = input(_ui_prompt("Select option (0-9)")).strip()
        if choice == "0":
            break
        elif choice == "1":
            opts["clone_roles"] = not opts.get("clone_roles", True)
        elif choice == "2":
            opts["clone_categories"] = not opts.get("clone_categories", True)
        elif choice == "3":
            opts["clone_channels"] = not opts.get("clone_channels", True)
        elif choice == "4":
            opts["clone_emojis"] = not opts.get("clone_emojis", True)
        elif choice == "5":
            val = not opts.get("clone_server_name", True)
            opts["clone_server_name"] = val
            opts["clone_server_icon"] = val
        elif choice == "6":
            opts["clear_target_channels"] = not opts.get("clear_target_channels", True)
        elif choice == "7":
            opts["clear_target_roles"] = not opts.get("clear_target_roles", False)
        elif choice == "8":
            new_delay = input(_ui_prompt("Enter delay between requests in seconds (e.g. 0.3)")).strip()
            try:
                config["request_delay"] = max(0.1, float(new_delay))
            except ValueError:
                pass
        elif choice == "9":
            new_token = input(_ui_prompt("Enter new Token")).strip()
            if new_token:
                config["token"] = new_token
                config["is_bot"] = not answer_yes("Is this a User Token?", default=False)
        config["clone_settings"] = opts
        save_config(config)


def main() -> None:
    set_title(f"Dot Flex Cloner v{VERSION}")
    config = load_config()
    api, config = ensure_token(config)
    cloner = ServerCloner(api, config)

    _, account_name = api.validate_token()

    while True:
        show_menu(account_name)
        choice = input(_ui_prompt("Select an option (01-06)")).strip()

        if choice in {"01", "1"}:
            clear()
            show_header()
            _ui_rule("DIRECT SERVER CLONE")
            _ui_line("Clone all channels, roles, and emojis from one server to another.", WHITE)
            _ui_rule(bottom=True)

            source_id = input(_ui_prompt("Source Server (Guild) ID")).strip()
            target_id = input(_ui_prompt("Target Server (Guild) ID")).strip()

            if not source_id or not target_id:
                log_action("ERROR", "Both Source and Target Server IDs are required.", RED)
                pause()
                continue

            if source_id == target_id:
                log_action("ERROR", "Source and Target Server IDs cannot be identical.", RED)
                pause()
                continue

            print()
            if answer_yes(f"Proceed with cloning server {source_id} -> {target_id}?", default=True):
                print()
                data = cloner.export_server(source_id)
                if data:
                    cloner.clone_from_data(data, target_id)
            pause()

        elif choice in {"02", "2"}:
            clear()
            show_header()
            _ui_rule("BACKUP SERVER TO FILE")
            _ui_line("Save a full snapshot of roles, channels, and emojis to a JSON file.", WHITE)
            _ui_rule(bottom=True)

            source_id = input(_ui_prompt("Server (Guild) ID to Backup")).strip()
            if not source_id:
                log_action("ERROR", "Server ID is required.", RED)
                pause()
                continue

            print()
            data = cloner.export_server(source_id)
            if data:
                file_path = cloner.save_backup_file(data)
                log_action("SAVED", f"Backup saved successfully: {file_path}", GREEN)
            pause()

        elif choice in {"03", "3"}:
            clear()
            show_header()
            _ui_rule("RESTORE SERVER FROM BACKUP FILE")
            _ui_line("Recreate a server layout from a saved JSON backup.", WHITE)
            _ui_rule(bottom=True)

            BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            backups = list(BACKUPS_DIR.glob("*.json"))
            if not backups:
                log_action("INFO", f"No backup files found in {BACKUPS_DIR}", YELLOW)
                pause()
                continue

            for idx, f in enumerate(backups, 1):
                _ui_line(f"{idx:02d}  {f.name}", CYAN)
            _ui_rule(bottom=True)

            file_choice = input(_ui_prompt(f"Select backup file number (1-{len(backups)})")).strip()
            try:
                sel_idx = int(file_choice) - 1
                if 0 <= sel_idx < len(backups):
                    selected_file = backups[sel_idx]
                else:
                    log_action("ERROR", "Invalid file choice.", RED)
                    pause()
                    continue
            except ValueError:
                log_action("ERROR", "Please enter a valid number.", RED)
                pause()
                continue

            target_id = input(_ui_prompt("Target Server (Guild) ID to restore to")).strip()
            if not target_id:
                log_action("ERROR", "Target Server ID is required.", RED)
                pause()
                continue

            print()
            if answer_yes(f"Restore {selected_file.name} to server {target_id}?", default=True):
                try:
                    with open(selected_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cloner.clone_from_data(data, target_id)
                except Exception as e:
                    log_action("ERROR", f"Failed reading backup file: {e}", RED)
            pause()

        elif choice in {"04", "4"}:
            clear()
            show_header()
            _ui_rule("WIPE / CLEAN TARGET SERVER")
            _ui_line("CAUTION: This will delete channels and custom roles from the target server!", RED)
            _ui_rule(bottom=True)

            target_id = input(_ui_prompt("Target Server (Guild) ID to wipe")).strip()
            if not target_id:
                log_action("ERROR", "Server ID is required.", RED)
                pause()
                continue

            print()
            if answer_yes(f"Are you ABSOLUTELY sure you want to clean server {target_id}?", default=False):
                if answer_yes("Delete ALL channels?", default=True):
                    cloner.api.wipe_channels(target_id)
                if answer_yes("Delete ALL custom roles?", default=False):
                    cloner.api.wipe_roles(target_id)
                log_action("DONE", "Target server clean operation finished.", GREEN)
            else:
                log_action("CANCELLED", "Wipe operation aborted by user.", YELLOW)
            pause()

        elif choice in {"05", "5"}:
            handle_settings(config)
            api = DiscordAPI(config["token"], is_bot=config.get("is_bot", True), request_delay=config.get("request_delay", 0.4))
            cloner = ServerCloner(api, config)

        elif choice in {"06", "6"}:
            clear()
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

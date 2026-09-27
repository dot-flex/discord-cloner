# Dot Flex Cloner v1.0

**High-Performance Server Cloner, Backup & Template Manager for Discord**

![Python](https://img.shields.io/badge/Python-3.10%2B-00bcd4?style=flat-square&logo=python&logoColor=white)
![Discord API](https://img.shields.io/badge/Discord%20API-v10-5865F2?style=flat-square&logo=discord&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-44cc11?style=flat-square)
[![GitHub](https://img.shields.io/badge/GitHub-dot--flex%2Fdiscord--cloner-181717?style=flat-square&logo=github)](https://github.com/dot-flex/discord-cloner)
[![Visitors](https://hits.sh/github.com/dot-flex/discord-cloner.svg?style=flat-square&label=visitors&color=007ec6)](https://hits.sh/github.com/dot-flex/discord-cloner/)

## ✨ Features

- **Direct Server-to-Server Clone** — Copy complete Discord server architecture (channels, categories, roles, and emojis) directly between servers.
- **No Source Admin Required (Selfbot Mode)** — Clone public structures from any server where your user account is an ordinary member.
- **Role & Permission Mapping** — Accurately re-creates roles with colors, hoists, and permissions bitfields, seamlessly translating channel permission overwrites including `@everyone`.
- **Category & Channel Organization** — Replicates text, voice, announcement, stage, and forum channels while preserving categories, positioning, bitrate, user limits, topic descriptions, and slowmode timers.
- **Emoji Migration** — Downloads custom static and animated emojis from the source server and re-uploads them directly to the destination.
- **JSON Snapshot Backups** — Export and archive full server layouts into timestamped JSON files for easy backup and one-click template restoration.
- **Server Wipe & Cleaner** — Optional bulk removal of existing channels and custom roles prior to cloning.
- **Smart Rate-Limit Engine** — Automated retry mechanisms with backoff (`HTTP 429 Retry-After`) and customizable request delays to protect against secondary Discord rate limits.
- **Interactive Console UI** — Centered layout, framed boxes, ASCII art header, and real-time timestamped action logs adapted from the Dot Flex UI style.

## 📦 Dependencies

- **Python 3.10+**
- **requests** 
- **colorama** 


## 🚀 Getting Started

### 1. Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/dot-flex/discord-cloner.git
cd discord-cloner
pip install -r requirements.txt
```

### 2. Configuration

Set your token and preferences in `config.json` (or let the tool guide you interactively on the first launch):

```json
{
  "token": "YOUR_DISCORD_TOKEN",
  "is_bot": false,
  "request_delay": 0.4,
  "clone_settings": {
    "clone_roles": true,
    "clone_categories": true,
    "clone_channels": true,
    "clone_emojis": true,
    "clone_server_name": true,
    "clone_server_icon": true,
    "clear_target_channels": true,
    "clear_target_roles": false
  }
}
```

- Set `"is_bot": false` if using a **User Token** (Selfbot).
- Set `"is_bot": true` if using a **Discord Bot Token**.

### 3. Running

Start the tool with:

```bash
python cloner.py
```

---

## 📖 How to Use

### Step 1: Enable Discord Developer Mode
To copy Server IDs easily:
1. Open Discord and go to **User Settings** (cog icon) $\rightarrow$ **Advanced**.
2. Turn **Developer Mode** on.
3. You can now right-click any server icon in your server list and click **Copy Server ID**.

---

### Step 2: Choose Your Account Mode

#### Option A: User Account / Selfbot Mode (`is_bot: false`)
- **Source Server**: You only need to be an **ordinary member** on the server you wish to clone. No administrator rights or permissions are needed!
- **Target Server**: You must be the **Server Owner** or have **Administrator** permissions (simply create a new empty server in Discord).

#### Option B: Bot Token Mode (`is_bot: true`)
- Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
- Invite the bot to both the source and destination servers with the **Administrator** permission.

---

### Step 3: Cloning a Server

1. Run `python cloner.py`.
2. On the main menu, type `01` and press `Enter` to select **DIRECT SERVER CLONE**.
3. **Source Server ID**: Paste the ID of the server you want to clone from.
4. **Target Server ID**: Paste the ID of your destination server.
5. Confirm with `Y`. The cloner will:
   - Clear existing default channels on the target server (if enabled in settings).
   - Recreate server name and icon.
   - Recreate roles and map permissions.
   - Recreate categories and channels with matching permissions and parent relationships.
   - Download and upload all custom emojis.

---

### Step 4: Offline Backup & Restore

- **Save a Server Backup (`02 BACKUP SERVER TO FILE`)**:
  - Enter any server ID to archive its complete layout (roles, channels, categories, emojis) into a timestamped JSON file inside the `backups/` folder.
- **Restore from Backup (`03 RESTORE SERVER FROM BACKUP FILE`)**:
  - Recreates a full server layout onto any target server from any previously saved backup file without needing access to the original server again.

---

## 📷 Showcase

![Showcase 1](https://i.imgur.com/TcnW3u7.png)


## ⚠️ Notes & Disclaimer

- **Role Hierarchy**: On the destination server, make sure your role (or the bot's role) is at the very top of the role hierarchy so it has the authority to create and manage lower roles.
- **Discord Terms**: This software is intended for authorized server administration, backup management, and server template replication. Use responsibly and in accordance with Discord's Terms of Service.

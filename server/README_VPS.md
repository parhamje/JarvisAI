# JARVIS — Always-On VPS Brain (Phase 1)

A headless, 24/7 JARVIS you talk to over Telegram. It runs the JARVIS
personality, Gemini reasoning, your long-term memory, and a set of
**cloud-safe** tools — and it needs **no GUI, no microphone, and no PC**.

> ⚠️ **Read this first — what it can and can't do.**
> This server is the *brain*. It can chat, remember you, search the web, report
> weather, and send/read your Telegram messages — all while your PC is **off**.
> It **cannot** open apps, control the mouse/keyboard, capture your screen, or
> update games, because those physically need your PC to be awake. Those tools
> live on the PC client (a later phase).

---

## How you use it

In **any** Telegram chat (Saved Messages, a friend, a group), send a message that
**starts with `jarvis` or `جارویس`**:

```
jarvis what's the weather in Amsterdam tomorrow?
jarvis search the latest news about the dollar rate
جارویس به علی بگو که فردا میام
jarvis what unread messages do I have?
jarvis remember that I prefer tea over coffee
```

JARVIS replies in the same chat. Because it only ever reacts to **your own
outgoing messages**, nobody else can trigger it — it's secure by design.

---

## One-time setup on the VPS (Ubuntu 24.04)

### 1. Get the code onto the VPS
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git
git clone <your-repo-url> jarvis     # or scp the project folder over
cd jarvis
```

### 2. Create the config
The server reuses `config/api_keys.json`. It needs your Gemini key **and**
Telegram API credentials (get the latter from https://my.telegram.org → *API
development tools*):

```json
{
    "gemini_api_key": "AIza...",
    "os_system": "linux",
    "telegram_api_id": "1234567",
    "telegram_api_hash": "abcdef0123456789...",
    "telegram_phone": "+98XXXXXXXXXX"
}
```

### 3. Install the minimal dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements-vps.txt
```

### 4. Log in to Telegram once
Two options:

- **Copy the session from your PC (easiest):** copy `jarvis.session` from your
  PC's project folder to the VPS project root. Done — skip to step 5.
- **Log in fresh on the VPS:**
  ```bash
  python -m server.jarvis_vps --login
  ```
  Enter the code Telegram sends you (and your 2FA password if you have one).
  This creates `jarvis.session`.

### 5. Test it
```bash
python -m server.jarvis_vps
```
You should see `🟢 JARVIS online`. From your phone, send yourself
`jarvis say hello` in Saved Messages — you should get a reply. `Ctrl+C` to stop.

---

## Run it 24/7 with systemd

Create `/etc/systemd/system/jarvis.service` (adjust the paths/username):

```ini
[Unit]
Description=JARVIS VPS Brain
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/jarvis
ExecStart=/home/YOUR_USER/jarvis/.venv/bin/python -m server.jarvis_vps
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis
sudo systemctl status jarvis      # check it's running
journalctl -u jarvis -f           # live logs
```

It now starts on boot and restarts if it crashes.

---

## Notes & limits

- **Memory:** uses the JSON store at `memory/long_term.json` (light). ChromaDB /
  vector memory is intentionally **not** used here to stay within 1 GB RAM.
- **Two JARVIS instances:** if you also run the PC app, both use the **same**
  `jarvis.session`. Telethon usually tolerates this, but if you see session
  locks, give the VPS its own session file (change `SESSION_PATH` in
  `server/jarvis_vps.py`) and log in separately.
- **Cost:** every `jarvis ...` command makes Gemini API calls. Watch your usage.
- **Next phases:** (2) a PC client that connects to this server to run local
  tools when your PC is online; (3) voice-note replies + push notifications.
```

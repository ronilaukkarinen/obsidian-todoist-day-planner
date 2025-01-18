# Obsidian Todoist Day Planner

![python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Google Cloud](https://img.shields.io/badge/GoogleCloud-%234285F4.svg?style=for-the-badge&logo=google-cloud&logoColor=white) ![Obsidian](https://img.shields.io/badge/Obsidian-%23483699.svg?style=for-the-badge&logo=obsidian&logoColor=white) ![Todoist](https://img.shields.io/badge/todoist-badge?style=for-the-badge&logo=todoist&logoColor=%23ffffff&color=%23E44332)

## Automatically sync Google Calendar events and Todoist tasks as Obsidian daily note with tasks and backlog 🦾

> [!NOTE] 
> **Please note!** This project uses hardcoded Finnish language strings and is 100% meant for my personal use. The prompt is in Finnish, the tasks are in Finnish, and the output is in Finnish. If you want to use this, you need to modify the script to your own language and needs.

## Why does this project exist?

I already have [personal-assistant-cli](https://github.com/ronilaukkarinen/personal-assistant-cli), but its main focus was AI and Todoist, not really Obsidian.

- This project is from Obsidian's point of view
- I wanted to use Python instead of bash

## Features

- Creates daily notes in Obsidian with proper Finnish date formatting
- Imports today's tasks from Todoist (both active and completed)
- Maintains priority tags (p1-p4) from Todoist
- Shows task completion status with two-way sync:
  - Tasks completed in Todoist are marked complete in Obsidian
  - Tasks completed in Obsidian are marked complete in Todoist
- Preserves task times from Todoist
- Supports time rescheduling from Obsidian back to Todoist
- Shows task counts with proper Finnish pluralization
- Maintains task hierarchy (parent/child relationships)
- Preserves task durations when syncing times
- Supports markdown links and wiki-style links
- Handles HTML tags in task content

## Requirements

- Python 3.12.1 or newer
- Obsidian
- Todoist
- Debian-based Linux

## Installation

### Option 1: Using pyenv (recommended)

1. Install required dependencies first:
```bash
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
libffi-dev liblzma-dev
```

2. Install pyenv:
```bash
curl https://pyenv.run | bash
```

3. Add these to your shell configuration (~/.bashrc):
```bash
# Add these lines at the end of ~/.bashrc:
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

4. Restart your shell to apply changes:
```bash
exec "$SHELL"
```

5. Install Python 3.12.1 (or newer) with pyenv:
```bash
pyenv install 3.12.1
```

6. Set up the project:
```bash
cd obsidian-todoist-day-planner
pyenv local 3.12.1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

7. Create and configure your .env file:
```bash
cp .env.example .env
nano .env  # Edit with your settings
```

### Option 2: System Python with venv

1. Install Python 3.12 and venv:
```bash
sudo apt install python3-full python3-pip python3-venv
```

2. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Activate the virtual environment and run the script:
```bash
source .venv/bin/activate
python create-daily-note.py
```

This will:
- Create a daily note in your specified Obsidian folder
- Import all today's tasks from Todoist
- Format them with proper checkboxes and priority tags
- Include task times where available, for [Daily Planner](https://github.com/ivan-lednev/obsidian-day-planner)
- Include backlog of tasks from previous days

## How to make p1 and p2 tags look like diamonds

- Enable day-planner.css in Custom CSS settings
- Use Text Snippets plugin, make it use `shift + tab` shortcut and just type `p1 + shift + tab` or `p2 + shift + tab` to get the diamond icon

## Automation

### Recommended sync interval

The recommended sync interval is 5 minutes. This ensures your Obsidian notes stay up-to-date with your Todoist tasks without making too many API calls.

### Setting up automatic sync with cron

1. Make sure your virtual environment is set up correctly first.

2. Create a shell script to run the Python script (e.g., `sync-tasks.sh`):
```bash
#!/bin/bash
cd /path/to/obsidian-todoist-day-planner
source .venv/bin/activate
python create-daily-note.py >> /tmp/todoist-sync.log 2>&1
```

3. Make the script executable:
```bash
chmod +x sync-tasks.sh
```

4. Open your crontab:
```bash
crontab -e
```

5. Add this line to run the script every 5 minutes:
```bash
*/5 * * * * /path/to/sync-tasks.sh
```

### Troubleshooting cron

If your cron job isn't working:

1. Make sure all paths in the shell script are absolute paths
2. Check the cron logs:
```bash
grep CRON /var/log/syslog
```

3. Test the script manually:
```bash
./sync-tasks.sh
```

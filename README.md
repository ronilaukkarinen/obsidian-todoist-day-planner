# Obsidian Todoist Day Planner

![bash](https://img.shields.io/badge/bash-%23121011.svg?style=for-the-badge&color=%23222222&logo=gnu-bash&logoColor=white) ![Chagtgpt](https://img.shields.io/badge/OpenAI-74aa9c?style=for-the-badge&logo=openai&logoColor=white) ![Google Cloud](https://img.shields.io/badge/GoogleCloud-%234285F4.svg?style=for-the-badge&logo=google-cloud&logoColor=white) ![Obsidian](https://img.shields.io/badge/Obsidian-%23483699.svg?style=for-the-badge&logo=obsidian&logoColor=white) ![Todoist](https://img.shields.io/badge/todoist-badge?style=for-the-badge&logo=todoist&logoColor=%23ffffff&color=%23E44332)

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
- Shows task completion status
- Preserves task times from Todoist

## Installation

1. Clone this repository
2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```env
OBSIDIAN_DAILY_NOTES_PATH=/path/to/your/obsidian/daily/notes
TODOIST_API_KEY=your_todoist_api_key
```

## Usage

Run the script to create today's note:
```bash
python3 create-daily-note.py
```

This will:
- Create a daily note in your specified Obsidian folder
- Import all today's tasks from Todoist
- Format them with proper checkboxes and priority tags
- Include task times where available

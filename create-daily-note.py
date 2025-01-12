from datetime import datetime, timedelta
import os
from pathlib import Path
import locale
from dotenv import load_dotenv
import requests
from typing import List, Dict
import re
from termcolor import colored

# Load environment variables
load_dotenv()

# Set locale to Finnish
locale.setlocale(locale.LC_TIME, 'fi_FI.UTF-8')

# Add a configuration variable
INCLUDE_COMPLETION_DATE = False

def log_info(message: str):
  print(colored(f"ℹ️  {message}", 'cyan'))

def get_todoist_tasks() -> List[Dict]:
  api_key = os.getenv('TODOIST_API_KEY')
  if not api_key:
    raise ValueError("TODOIST_API_KEY not set in .env file")

  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    log_info("Fetching active tasks from Todoist...")
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "today"}
    )
    response.raise_for_status()
    active_tasks = response.json()

    # Get all tasks to find subtasks of today's tasks
    all_tasks_response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers
    )
    all_tasks_response.raise_for_status()
    all_tasks = all_tasks_response.json()

    # Get IDs of today's tasks
    today_task_ids = {task['id'] for task in active_tasks}

    # Add subtasks of today's tasks
    for task in all_tasks:
      if task.get('parent_id') in today_task_ids and task['id'] not in today_task_ids:
        active_tasks.append(task)

    for task in active_tasks:
      # Add time information for active tasks
      if task.get('due') and task['due'].get('datetime'):
        scheduled_time = datetime.fromisoformat(task['due']['datetime'].replace('Z', '+00:00'))
        time_str = scheduled_time.strftime('%H:%M')

        # Calculate end time if duration exists
        duration = task.get('duration')
        if duration:
          duration_minutes = duration.get('amount', 0) * {'minute': 1, 'hour': 60, 'day': 1440}.get(duration.get('unit', 'minute'), 0)
          end_time = scheduled_time + timedelta(minutes=duration_minutes)
          time_str = f"{time_str} - {end_time.strftime('%H:%M')}"

        task['due_string'] = time_str

    log_info("Fetching completed tasks...")
    try:
      response = requests.get(
        "https://api.todoist.com/sync/v9/completed/get_all",
        headers=headers,
        params={"limit": 30}
      )
      response.raise_for_status()
      completed_data = response.json()

      today = datetime.now().strftime("%Y-%m-%d")
      completed_tasks = []
      for item in completed_data.get("items", []):
        completed_at = item.get("completed_at", "")
        if completed_at.startswith(today):
          # Get the original task details
          task_id = item.get('task_id')
          if task_id:
            try:
              response = requests.get(
                f"https://api.todoist.com/rest/v2/tasks/{task_id}",
                headers=headers
              )
              task_details = response.json()
              print(f"\nTask details: {task_details}")

              # Get completion time (add 2 hours for timezone)
              completed_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
              completed_time = completed_time + timedelta(hours=2)
              completion_str = f"(Valmis {completed_time.strftime('%H:%M')})"

              # Get scheduled time and calculate end time using duration
              if task_details.get('due'):
                due_datetime = task_details['due'].get('datetime')
                if due_datetime:
                  scheduled_time = datetime.fromisoformat(due_datetime.replace('Z', '+00:00'))
                  scheduled_time = scheduled_time + timedelta(hours=2)  # Add 2 hours for timezone
                  time_str = scheduled_time.strftime('%H:%M')

                  # Calculate end time if duration exists
                  duration = task_details.get('duration')
                  if duration:
                    duration_minutes = duration.get('amount', 0) * {'minute': 1, 'hour': 60, 'day': 1440}.get(duration.get('unit', 'minute'), 0)
                    end_time = scheduled_time + timedelta(minutes=duration_minutes)
                    time_str = f"{time_str} - {end_time.strftime('%H:%M')}"

                  completed_tasks.append({
                    "content": item["content"],
                    "completed": True,
                    "priority": item.get("priority", 1),
                    "due_string": f"{time_str} {completion_str}"  # Changed order here
                  })
                  continue
            except requests.exceptions.RequestException:
              pass  # If we can't get task details, fall back to content parsing

          # Fall back to content parsing if no due date found
          time_pattern = r'(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)'
          time_match = re.search(time_pattern, item["content"])
          task_content = item["content"]

          if time_match:
            time_str = time_match.group(1)
            task_content = re.sub(time_pattern, '', task_content).strip()
            completed_tasks.append({
              "content": task_content,
              "completed": True,
              "priority": item.get("priority", 1),
              "due_string": f"{time_str} {completion_str}"  # Changed order here
            })
          else:
            completed_tasks.append({
              "content": task_content,
              "completed": True,
              "priority": item.get("priority", 1),
              "due_string": completion_str
            })

    except requests.exceptions.RequestException as e:
      print(colored(f"Error fetching completed tasks: {e}", 'red'))
      completed_tasks = []

    log_info(f"Found {len(active_tasks)} active and {len(completed_tasks)} completed tasks")
    return active_tasks + completed_tasks

  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching tasks from Todoist: {e}", 'red'))
    return []

def format_todoist_tasks(tasks: List[Dict]) -> str:
  task_lines = []
  for task in tasks:
    print(f"\nFormatting task: {task}")  # Keep debug line
    checkbox = "x" if task.get("completed", False) else " "
    priority = task.get("priority", 1)
    priority_tag = f'<i d="p{5-priority}">p{5-priority}</i> ' if priority > 1 else ""

    # Add time if available, otherwise just show the task
    time_str = task.get("due_string", "")
    content = task["content"]
    task_id = task.get("id", "")
    project_id = task.get("project_id", "")
    parent_id = task.get("parent_id", None)

    # Wrap content in span with task ID and project ID if available
    if task_id:
      content = f'<span data-id="{task_id}" data-project="{project_id}">{content}</span>'

    # Find parent task to check project
    parent_project = None
    if parent_id:
      parent = next((t for t in tasks if t.get('id') == parent_id), None)
      if parent:
        parent_project = parent.get('project_id')

    # Only indent if it's a subtask AND belongs to the same project as parent
    indent = "\t" if parent_id and parent_project == project_id else ""

    if "Valmis" in time_str:
      # Split time string into scheduled time and completion time
      parts = time_str.split(" (Valmis ", 1)
      if len(parts) == 2:
        scheduled_time = parts[0].strip()
        completion_time = f"(Valmis {parts[1]}"  # parts[1] already has the closing parenthesis
        if INCLUDE_COMPLETION_DATE:
          if scheduled_time:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{scheduled_time} {content} {completion_time}')
          else:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{content} {completion_time}')
        else:
          if scheduled_time:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{scheduled_time} {content}')
          else:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{content}')
      else:
        # Handle case where time_str is just the completion time
        if INCLUDE_COMPLETION_DATE:
          task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{content} {time_str}')
        else:
          task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{content}')
    else:
      if time_str:
        task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{time_str} {content}')
      else:
        task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{content}')

  return "\n".join(task_lines)

def read_existing_note(file_path: str) -> List[Dict]:
  if not os.path.exists(file_path):
    return []

  with open(file_path, 'r', encoding='utf-8') as f:
    content = f.readlines()

  tasks = []
  task_pattern = re.compile(r'- \[.\] <span data-id="(\d+)">(.*?)</span>')
  for line in content:
    match = task_pattern.search(line)
    if match:
      task_id = match.group(1)
      task_content = match.group(2)
      tasks.append({"id": task_id, "content": task_content, "line": line.strip()})

  return tasks

def sync_tasks_with_todoist(note_tasks: List[Dict], todoist_tasks: List[Dict]):
  for note_task in note_tasks:
    note_task_id = note_task.get("id")
    if not note_task_id:
      continue  # Skip tasks without an ID

    for todoist_task in todoist_tasks:
      todoist_task_id = todoist_task.get("id")
      if not todoist_task_id:
        continue  # Skip tasks without an ID

      if note_task_id == str(todoist_task_id):
        # Compare and sync changes
        if note_task["content"] != todoist_task["content"]:
          print(f"Updating Todoist task {todoist_task_id}: {note_task['content']}")  # Debug line
          update_todoist_task(todoist_task_id, note_task["content"])

def update_todoist_task(task_id: str, new_content: str):
  api_key = os.getenv('TODOIST_API_KEY')
  if not api_key:
    raise ValueError("TODOIST_API_KEY not set in .env file")

  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
  }
  data = {
    "content": new_content
  }
  response = requests.post(
    f"https://api.todoist.com/rest/v2/tasks/{task_id}",
    headers=headers,
    json=data
  )
  if response.status_code == 204:
    print(f"Task {task_id} updated successfully.")
  else:
    print(f"Failed to update task {task_id}: {response.status_code} {response.text}")
  response.raise_for_status()

def get_backlog_tasks() -> List[Dict]:
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    log_info("Fetching backlog tasks...")
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "overdue | no date"}
    )
    response.raise_for_status()
    backlog_tasks = response.json()

    # Get IDs of today's tasks to exclude their subtasks from backlog
    today_response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "today"}
    )
    today_response.raise_for_status()
    today_tasks = today_response.json()
    today_task_ids = {task['id'] for task in today_tasks}

    # Filter out subtasks of today's tasks from backlog
    backlog_tasks = [
      task for task in backlog_tasks
      if not task.get('parent_id') in today_task_ids
    ]

    # Sort by priority (higher number = higher priority)
    backlog_tasks.sort(key=lambda x: x.get('priority', 1), reverse=True)
    return backlog_tasks
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching backlog tasks: {e}", 'red'))
    return []

def create_daily_note():
  log_info("Creating daily note...")
  # Get current date
  now = datetime.now()

  # Format the path components
  year = now.strftime("%Y")
  month = now.strftime("%m")
  day = now.strftime("%-d.%-m.%Y")
  weekday = now.strftime("%A").lower()

  # Get base path from environment variable
  base_path = os.getenv('OBSIDIAN_DAILY_NOTES_PATH')
  if not base_path:
    raise ValueError("OBSIDIAN_DAILY_NOTES_PATH not set in .env file")

  full_path = f"{base_path}/{year}/{month}/{day}, {weekday}.md"

  # Check if note exists and read existing tasks
  existing_tasks = read_existing_note(full_path)

  # Get today's tasks (including completed)
  tasks = get_todoist_tasks()
  task_count = len(tasks)
  formatted_tasks = format_todoist_tasks(tasks)

  # Sync tasks with Todoist
  sync_tasks_with_todoist(existing_tasks, tasks)

  # Get backlog tasks
  try:
    log_info("Fetching backlog tasks...")
    headers = {
      "Authorization": f"Bearer {os.getenv('TODOIST_API_KEY')}"
    }
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "overdue | no date"}
    )
    response.raise_for_status()
    backlog_tasks = response.json()
    # Sort by priority (higher number = higher priority)
    backlog_tasks.sort(key=lambda x: x.get('priority', 1), reverse=True)
    formatted_backlog = format_todoist_tasks(backlog_tasks)
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching backlog tasks: {e}", 'red'))
    formatted_backlog = ""

  # Format weekday and month names for the header
  weekday_capitalized = weekday.capitalize()
  month_name = now.strftime("%B")

  # Create the content
  content = f"""# {weekday_capitalized}, {now.day}. {month_name}ta

Kello on päiväsuunnitelmapohjan tekohetkellä {now.strftime('%H:%M')}. Tehtäviä tänään: {task_count}.

> [!NOTE] Note to self: Ajo-ohje itselleni
> Tehtävät tulevat Todoistista, mutta niitä voi täällä aikatauluttaa kalenteriin kätevästi Day Plannerin avulla. Kirjoita päivän muistiinpanot myös alle.

## Päivän tehtävät

{formatted_tasks}

## Backlog

{formatted_backlog}"""

  # Write the content to file
  with open(full_path, 'w', encoding='utf-8') as f:
    f.write(content)

  print(f"Daily note created at: {full_path}")

if __name__ == "__main__":
  create_daily_note()

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import locale
from dotenv import load_dotenv
import requests
from typing import List, Dict
import re
from termcolor import colored
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import argparse
import uuid

# Load environment variables
load_dotenv()

# Set locale to Finnish
locale.setlocale(locale.LC_TIME, 'fi_FI.UTF-8')

# Add a configuration variable
INCLUDE_COMPLETION_DATE = False

def log_info(message: str):
  # Get current time in 24-hour format
  current_time = datetime.now().strftime('%H:%M')
  print(colored(f"ℹ️  {message}", 'cyan'))

def get_todoist_tasks() -> List[Dict]:
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}

  try:
    log_info("Fetching active tasks from Todoist...")
    # First get today's tasks
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "today"}
    )
    response.raise_for_status()
    today_tasks = response.json()

    # Get all tasks to find subtasks without dates
    all_response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers
    )
    all_response.raise_for_status()
    all_tasks = all_response.json()

    # Create a set of today's task IDs
    today_task_ids = {str(task['id']) for task in today_tasks}

    # Add subtasks of today's tasks even if they don't have dates
    tasks = today_tasks.copy()
    for task in all_tasks:
      parent_id = str(task.get('parent_id')) if task.get('parent_id') else None
      if parent_id and parent_id in today_task_ids and str(task['id']) not in today_task_ids:
        log_info(f"Adding dateless subtask: '{task['content']}' with parent ID: {parent_id}")
        tasks.append(task)

    # Time handling for tasks with dates
    for task in tasks:
      if task.get('due') and task['due'].get('datetime'):
        # Remove the special handling for Google Calendar tasks
        scheduled_time = datetime.fromisoformat(task['due']['datetime'].replace('Z', '+00:00'))
        task['due']['datetime'] = scheduled_time.isoformat()

        # Calculate end time based on duration if available
        if task.get('duration'):
          duration_minutes = task['duration'].get('amount', 0) if isinstance(task['duration'], dict) else int(task['duration'])
          end_time = scheduled_time + timedelta(minutes=duration_minutes)
          task['due']['end_datetime'] = end_time.isoformat()

        # Log adjusted time
        adjusted_time = datetime.fromisoformat(task['due']['datetime'].replace('Z', '+00:00'))
        log_info(f"  Adjusted time: {adjusted_time.strftime('%H:%M')}")

    # Create a dictionary to store parent-child relationships
    child_tasks = {}
    tasks_by_id = {str(task['id']): task for task in tasks}

    # Group child tasks by parent_id
    for task in tasks:
      parent_id = str(task.get('parent_id')) if task.get('parent_id') else None
      if parent_id:
        log_info(f"Found today's subtask: '{task['content']}' with parent ID: {parent_id}")
        if parent_id not in child_tasks:
          child_tasks[parent_id] = []
        child_tasks[parent_id].append(task)
        task['is_subtask'] = True
        log_info(f"  Added today's subtask to parent {parent_id}")

    # Create ordered list with proper hierarchy
    ordered_tasks = []

    # Add root tasks and their children in order
    for task in tasks:
      task_id = str(task['id'])
      if not task.get('parent_id'):  # If it's a root task
        ordered_tasks.append(task)
        # Add any children
        if task_id in child_tasks:
          log_info(f"Adding today's children for task: '{task['content']}'")
          # Safe sorting that handles tasks without due dates
          def sort_key(x):
            if not x.get('due'):
              return ''
            return x['due'].get('datetime', '')

          children = sorted(child_tasks[task_id], key=sort_key)
          for child in children:
            log_info(f"  Adding today's child: '{child['content']}'")
          ordered_tasks.extend(children)

    # Get completed tasks
    completed_tasks = get_completed_tasks(headers)

    log_info(f"Found {len(tasks)} active and {len(completed_tasks)} completed tasks")
    # Get completed tasks and add them to our list
    tasks.extend(get_completed_tasks(headers))
    return ordered_tasks + completed_tasks

  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching tasks from Todoist: {e}", 'red'))
    return []

def get_project_names() -> Dict[str, str]:
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    response = requests.get(
      "https://api.todoist.com/rest/v2/projects",
      headers=headers
    )
    response.raise_for_status()
    projects = response.json()
    return {str(project['id']): project['name'] for project in projects}
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching projects: {e}", 'red'))
    return {}

def content_to_classes(content: str) -> str:
  # Remove special characters and convert to lowercase
  # Keep only letters, numbers, and spaces
  cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', content)

  # Split into words and filter out empty strings
  words = [word.lower() for word in cleaned.split() if word]

  # Join words with spaces to create class string
  return ' '.join(words)

def create_class_string(content: str) -> str:
  """Create a class string from task content by converting to lowercase and removing special characters."""
  # Remove markdown links [[like this]]
  content = re.sub(r'\[\[.*?\]\]', '', content)

  # Remove any remaining special characters and convert to lowercase
  class_str = re.sub(r'[^a-zA-Z0-9\s]', '', content.lower())

  # Replace spaces with spaces (for readability in HTML)
  class_str = class_str.replace(' ', ' ')

  return class_str.strip()

def format_todoist_tasks(tasks: List[Dict], is_today: bool = False) -> str:
  # Get project names
  project_names = get_project_names()
  formatted_tasks = []
  today = datetime.now().strftime("%Y-%m-%d")

  # Count all tasks for today, including completed ones
  total_tasks = len(tasks)

  # Finnish pluralization for "tehtävä"
  task_text = "tehtävä" if total_tasks == 1 else "tehtävää"
  if is_today:
    formatted_tasks.append(f"{total_tasks} {task_text} tänään.\n")
  else:
    formatted_tasks.append(f"{total_tasks} {task_text}.\n")

  # Create a dictionary to store parent-child relationships
  child_tasks = {}
  tasks_by_id = {str(task['id']): task for task in tasks}

  # Remove duplicate tasks (keep the newest one based on task ID)
  unique_tasks = {}
  for task in tasks:
    content = task.get("content", "").replace(" @Google-kalenterin tapahtuma", "")
    parent_id = str(task.get('parent_id')) if task.get('parent_id') else None

    # Create a unique key that includes parent_id to differentiate subtasks
    unique_key = f"{content}_{parent_id}"

    # If we haven't seen this task before, or if this is a newer version
    if unique_key not in unique_tasks or int(task['id']) > int(unique_tasks[unique_key]['id']):
      unique_tasks[unique_key] = task
      log_info(f"Added/Updated task in unique_tasks: {content} (ID: {task['id']}, Parent: {parent_id})")

  # Use the deduplicated tasks list
  tasks = list(unique_tasks.values())
  log_info(f"After deduplication: {len(tasks)} tasks")

  # Group child tasks by parent_id
  for task in tasks:
    parent_id = str(task.get('parent_id')) if task.get('parent_id') else None
    if parent_id:
      if parent_id not in child_tasks:
        child_tasks[parent_id] = []
      child_tasks[parent_id].append(task)
      task['is_subtask'] = True
      log_info(f"Added child task: {task.get('content')} to parent {parent_id}")

  # Create ordered list with proper hierarchy
  ordered_tasks = []

  # Add root tasks and their children in order
  root_tasks = [task for task in tasks if not task.get('parent_id')]
  log_info(f"Found {len(root_tasks)} root tasks")

  def sort_key(task):
    # 1. Priority (negative so higher priority comes first)
    priority = -(task.get('priority', 1))

    # 2. Time (if scheduled)
    time_str = '999999'  # Default high value for unscheduled tasks
    if task.get('due') and task['due'].get('datetime'):
      dt = datetime.fromisoformat(task['due']['datetime'].replace('Z', '+00:00'))
      time_str = dt.strftime('%H%M%S')

    # 3. Creation date (task ID as proxy, negative so newer comes first)
    creation_order = -int(task['id'])

    # 4. Completed tasks at the bottom
    is_completed = 1 if task.get("completed", False) else 0

    return (is_completed, priority, time_str, creation_order)

  # Sort root tasks
  root_tasks.sort(key=sort_key)

  # Add root tasks and their children in order
  for task in root_tasks:
    task_id = str(task['id'])
    log_info(f"Processing root task: {task.get('content')} (ID: {task_id})")

    # Use the completion status from the task data
    checkbox = "x" if task.get("completed", False) else " "
    priority = task.get("priority", 1)
    priority_tag = f'<i d="p{5-priority}">p{5-priority}</i> ' if priority > 1 else ""

    # Get time information
    time_str = ""
    if task.get("due") and task["due"].get("datetime"):
      start_time = datetime.fromisoformat(task["due"]["datetime"].replace('Z', '+00:00'))
      task_date = start_time.strftime("%Y-%m-%d")
      if task_date == today:  # Only show times for today's tasks
        duration = 0
        if isinstance(task.get("duration"), dict):
          duration = task["duration"].get("amount", 0)
        elif isinstance(task.get("duration"), (int, str)):
          duration = int(task["duration"])

        if duration:
          end_time = start_time + timedelta(minutes=duration)
          start_local = start_time.astimezone().strftime("%H:%M")
          end_local = end_time.astimezone().strftime("%H:%M")
          time_str = f"{start_local} - {end_local} "

    # Format task line
    project_id = str(task.get("project_id")) if task.get("project_id") else None
    project_name = project_names.get(project_id, "")
    content = task.get("content", "").replace(" @Google-kalenterin tapahtuma", "")
    class_str = create_class_string(content)
    task_line = f"- [{checkbox}] {time_str}{priority_tag}<span data-id=\"{task['id']}\" data-project=\"{project_name}\" class=\"{class_str}\"></span>{content}"
    formatted_tasks.append(task_line)

    # Add any children
    if task_id in child_tasks:
      children = sorted(child_tasks[task_id], key=sort_key)
      for child in children:
        # Use the completion status from the child task data
        checkbox = "x" if child.get("completed", False) else " "
        priority = child.get("priority", 1)
        priority_tag = f'<i d="p{5-priority}">p{5-priority}</i> ' if priority > 1 else ""

        # Get time information for child task
        time_str = ""
        if child.get("due") and child["due"].get("datetime"):
          start_time = datetime.fromisoformat(child["due"]["datetime"].replace('Z', '+00:00'))
          task_date = start_time.strftime("%Y-%m-%d")
          if task_date == today:  # Only show times for today's tasks
            duration = 0
            if isinstance(child.get("duration"), dict):
              duration = child["duration"].get("amount", 0)
            elif isinstance(child.get("duration"), (int, str)):
              duration = int(child["duration"])

            if duration:
              end_time = start_time + timedelta(minutes=duration)
              start_local = start_time.astimezone().strftime("%H:%M")
              end_local = end_time.astimezone().strftime("%H:%M")
              time_str = f"{start_local} - {end_local} "

        content = child.get("content", "").replace(" @Google-kalenterin tapahtuma", "")
        class_str = create_class_string(content)
        child_line = f"\t- [{checkbox}] {time_str}{priority_tag}<span data-id=\"{child['id']}\" data-project=\"{project_name}\" class=\"{class_str}\"></span>{content}"
        formatted_tasks.append(child_line)

  return "\n".join(formatted_tasks)

def read_existing_note(file_path: str) -> List[Dict]:
  if not os.path.exists(file_path):
    return []

  with open(file_path, 'r', encoding='utf-8') as f:
    content = f.readlines()

  tasks = []
  # Updated regex to capture completion status and full line
  task_pattern = re.compile(r'- \[([ x])\] .*?<span data-id="(\d+)".*?>(.*?)</span>')
  for line in content:
    match = task_pattern.search(line)
    if match:
      completed = match.group(1) == 'x'
      task_id = match.group(2)
      task_content = match.group(3)
      tasks.append({
        "id": task_id,
        "content": task_content,
        "completed": completed,
        "line": line.strip()
      })

  return tasks

def sync_tasks_with_todoist(note_tasks: List[Dict], todoist_tasks: List[Dict], note_path: str):
  # Get completed tasks with timestamps
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}

  try:
    response = requests.get(
      "https://api.todoist.com/sync/v9/completed/get_all",
      headers=headers
    )
    response.raise_for_status()
    completed_data = response.json()

    # Create a map of task_id to completion time
    todoist_completion_times = {
      str(item["task_id"]): item["completed_at"]
      for item in completed_data.get("items", [])
    }

    # Get time update history
    time_response = requests.get(
      "https://api.todoist.com/sync/v9/activity/get",
      headers=headers,
      params={"limit": 100}
    )
    time_response.raise_for_status()
    activity_data = time_response.json()

    # Create a map of task_id to last time modification
    todoist_time_updates = {
      str(event["object_id"]): datetime.fromisoformat(event["event_date"].replace('Z', '+00:00'))
      for event in activity_data.get("events", [])
      if event.get("object_type") == "item"
      and event.get("event_type") == "updated"
      and "due_date" in str(event.get("extra_data", {}))
    }
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching data: {e}", 'red'))
    todoist_completion_times = {}
    todoist_time_updates = {}

  # Get note's last modification time and make it timezone-aware
  try:
    note_mtime = datetime.fromtimestamp(os.path.getmtime(note_path))
    # Convert to UTC timezone-aware datetime
    note_mtime = note_mtime.astimezone(timezone.utc)
  except OSError:
    note_mtime = None
    log_info("Could not get note modification time")

  for note_task in note_tasks:
    note_task_id = note_task.get("id")
    if not note_task_id:
      continue

    for todoist_task in todoist_tasks:
      todoist_task_id = todoist_task.get("id")
      if not todoist_task_id:
        continue

      if note_task_id == str(todoist_task_id):
        needs_update = False
        updates = {}

        # Handle time sync
        time_match = re.search(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', note_task.get('line', ''))
        if time_match:
          start_time = time_match.group(1)
          end_time = time_match.group(2)
          today = datetime.now().strftime("%Y-%m-%d")
          start_dt = datetime.strptime(f"{today} {start_time}", "%Y-%m-%d %H:%M")
          end_dt = datetime.strptime(f"{today} {end_time}", "%Y-%m-%d %H:%M")
          duration = int((end_dt - start_dt).total_seconds() / 60)

          if todoist_task.get('due') and todoist_task['due'].get('datetime'):
            todoist_datetime = datetime.fromisoformat(todoist_task['due']['datetime'].replace('Z', '+00:00'))
            todoist_time = todoist_datetime.strftime("%H:%M")
            todoist_date = todoist_datetime.strftime("%Y-%m-%d")

            if todoist_time != start_time:
              log_info(f"Time differs for task {note_task_id}:")
              log_info(f"  Note time: {start_time}")
              log_info(f"  Todoist time: {todoist_time}")

              # Get Todoist's last update time for this task
              todoist_update_time = todoist_time_updates.get(note_task_id)

              # Compare timezone-aware datetimes
              if note_mtime and (not todoist_update_time or note_mtime > todoist_update_time):
                log_info(f"Using Obsidian's time as note was modified at {note_mtime}")
                if todoist_task['due'].get('string'):
                  # For recurring tasks, preserve the full NLP string
                  due_string = todoist_task['due']['string']
                  # Extract everything except the time
                  recurrence_match = re.match(r'^(.*?)\b\d{1,2}:\d{2}\b(.*)$', due_string)
                  if recurrence_match:
                    before_time = recurrence_match.group(1)
                    after_time = recurrence_match.group(2)
                    updates["due_string"] = f"{before_time}{start_time}{after_time}"
                else:
                  # For non-recurring tasks, use due_datetime
                  updates["due_datetime"] = start_dt.isoformat()
                updates["duration"] = str(duration)
                updates["duration_unit"] = "minute"
                needs_update = True
              # If Todoist has a more recent update, use Todoist's time
              elif todoist_update_time:
                log_info(f"Using Todoist's time as it was updated at {todoist_update_time}")
                note_task['line'] = note_task['line'].replace(
                  f"{start_time} - {end_time}",
                  f"{todoist_time} - {(todoist_datetime + timedelta(minutes=duration)).strftime('%H:%M')}"
                )
              # If no timestamps available, use Obsidian's time
              else:
                log_info(f"Using Obsidian's time as no update times available")
                if todoist_task['due'].get('string'):
                  # For recurring tasks, update only the time in due_string
                  due_string = todoist_task['due']['string']
                  time_pattern = r'\b\d{1,2}:\d{2}\b'
                  updates["due_string"] = re.sub(time_pattern, start_time, due_string)
                else:
                  # For non-recurring tasks, use due_datetime
                  updates["due_datetime"] = start_dt.isoformat()
                updates["duration"] = str(duration)
                updates["duration_unit"] = "minute"
                needs_update = True

        # Handle completion sync
        note_completed = note_task.get("completed", False)
        todoist_completed = todoist_task.get("completed", False)

        if note_completed != todoist_completed:
          # If task has a completion time in Todoist, use Todoist's state
          if note_task_id in todoist_completion_times:
            if todoist_completed:
              log_info(f"Task {note_task_id} was completed in Todoist at {todoist_completion_times[note_task_id]}")
              note_task["completed"] = True
            else:
              log_info(f"Task {note_task_id} was uncompleted in Todoist")
              note_task["completed"] = False
          # If no completion time in Todoist, use Obsidian's state
          else:
            if note_completed:
              log_info(f"Completing task {note_task_id} in Todoist to match note")
              close_todoist_task(todoist_task_id)
            else:
              log_info(f"Reopening task {note_task_id} in Todoist to match note")
              reopen_todoist_task(todoist_task_id)

        # Update task if needed
        if needs_update and updates:
          update_todoist_task(todoist_task_id, updates)

def close_todoist_task(task_id: str):
  """Mark a Todoist task as completed."""
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}",
    "X-Request-Id": str(uuid.uuid4())
  }

  try:
    response = requests.post(
      f"https://api.todoist.com/rest/v2/tasks/{task_id}/close",
      headers=headers
    )
    if response.status_code == 204:
      log_info(f"Task {task_id} marked as completed")
    else:
      print(colored(f"Failed to complete task {task_id}: {response.status_code}", 'red'))
      if response.text:
        print(colored(f"Response: {response.text}", 'red'))
    response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(colored(f"Error completing task: {e}", 'red'))

def reopen_todoist_task(task_id: str):
  """Reopen a completed Todoist task."""
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}",
    "X-Request-Id": str(uuid.uuid4())
  }

  try:
    response = requests.post(
      f"https://api.todoist.com/rest/v2/tasks/{task_id}/reopen",
      headers=headers
    )
    if response.status_code == 204:
      log_info(f"Task {task_id} reopened")
    else:
      print(colored(f"Failed to reopen task {task_id}: {response.status_code}", 'red'))
      if response.text:
        print(colored(f"Response: {response.text}", 'red'))
    response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(colored(f"Error reopening task: {e}", 'red'))

def update_todoist_task(task_id: str, updates: Dict):
  """Update a Todoist task with the given updates."""
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "X-Request-Id": str(uuid.uuid4())
  }

  # Validate updates before sending
  if "content" in updates:
    updates["content"] = updates["content"].strip()
    if not updates["content"]:
      log_info(f"Skipping update for task {task_id} - empty content after stripping")
      return

  log_info(f"Sending update for task {task_id}:")
  log_info(f"  Updates: {updates}")

  try:
    response = requests.post(
      f"https://api.todoist.com/rest/v2/tasks/{task_id}",
      headers=headers,
      json=updates
    )
    if response.status_code in [200, 204]:
      log_info(f"Task {task_id} updated successfully")
    else:
      print(colored(f"Failed to update task {task_id}: {response.status_code}", 'red'))
      if response.text:
        print(colored(f"Response: {response.text}", 'red'))
    response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(colored(f"Error updating task: {e}", 'red'))

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

def get_future_tasks() -> List[Dict]:
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    log_info("Fetching future tasks...")
    # First get future tasks
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "due after: today"}
    )
    response.raise_for_status()
    future_tasks = response.json()

    # Get all tasks to find subtasks without dates
    all_response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers
    )
    all_response.raise_for_status()
    all_tasks = all_response.json()

    # Create a set of future task IDs
    future_task_ids = {str(task['id']) for task in future_tasks}

    # Add subtasks of future tasks even if they don't have dates
    tasks = future_tasks.copy()
    for task in all_tasks:
      parent_id = str(task.get('parent_id')) if task.get('parent_id') else None
      if parent_id and parent_id in future_task_ids and str(task['id']) not in future_task_ids:
        log_info(f"Adding dateless future subtask: '{task['content']}' with parent ID: {parent_id}")
        tasks.append(task)

    # Create a dictionary to store parent-child relationships
    child_tasks = {}
    tasks_by_id = {str(task['id']): task for task in tasks}

    # Group child tasks by parent_id
    for task in tasks:
      parent_id = str(task.get('parent_id')) if task.get('parent_id') else None
      if parent_id:
        log_info(f"Found future subtask: '{task['content']}' with parent ID: {parent_id}")
        if parent_id not in child_tasks:
          child_tasks[parent_id] = []
        child_tasks[parent_id].append(task)
        task['is_subtask'] = True
        log_info(f"  Added future subtask to parent {parent_id}")

    # Create ordered list with proper hierarchy
    ordered_tasks = []

    # Add root tasks and their children in order
    for task in tasks:
      task_id = str(task['id'])
      if not task.get('parent_id'):  # If it's a root task
        ordered_tasks.append(task)
        # Add any children
        if task_id in child_tasks:
          log_info(f"Adding future children for task: '{task['content']}'")
          # Safe sorting that handles tasks without due dates
          def sort_key(x):
            if not x.get('due'):
              return ''
            return x['due'].get('datetime', '')

          children = sorted(child_tasks[task_id], key=sort_key)
          for child in children:
            log_info(f"  Adding future child: '{child['content']}'")
          ordered_tasks.extend(children)

    # Sort by priority (higher number = higher priority)
    ordered_tasks.sort(key=lambda x: x.get('priority', 1), reverse=True)
    return ordered_tasks
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching future tasks: {e}", 'red'))
    return []

def refresh_google_token() -> str:
  """Refresh Google API token using refresh token."""
  response = requests.post(
    'https://accounts.google.com/o/oauth2/token',
    data={
      'client_id': os.getenv('GOOGLE_CLIENT_ID'),
      'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
      'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
      'grant_type': 'refresh_token'
    }
  )
  return response.json()['access_token']

def load_synced_events() -> Dict[str, List[Dict]]:
  """Load previously synced events from log file."""
  log_file = os.path.join(os.path.dirname(__file__), 'synced_events.log')
  try:
    if os.path.exists(log_file):
      with open(log_file, 'r', encoding='utf-8') as f:
        return {line.split('|')[0]: {
          'title': line.split('|')[1],
          'date': line.split('|')[2].strip()
        } for line in f if '|' in line}
    return {}
  except Exception as e:
    print(colored(f"Error loading synced events: {e}", 'red'))
    return {}

def save_synced_event(event_id: str, title: str, date: str):
  """Save synced event to log file."""
  log_file = os.path.join(os.path.dirname(__file__), 'synced_events.log')
  try:
    with open(log_file, 'a', encoding='utf-8') as f:
      f.write(f"{event_id}|{title}|{date}\n")
  except Exception as e:
    print(colored(f"Error saving synced event: {e}", 'red'))

def task_exists_in_todoist(event_id: str, event_title: str, event_date: str) -> bool:
  """Check if event was already synced using the log file."""
  synced_events = load_synced_events()
  if event_id in synced_events:
    event = synced_events[event_id]
    if event['date'] == event_date:
      log_info(f"Found matching synced event: {event_title} on {event_date}")
      return True
  return False

def create_todoist_task(event: Dict, project_id: str, dry_run: bool = False):
  """Create a task in Todoist from Google Calendar event."""
  start = event['start'].get('dateTime')
  end = event['end'].get('dateTime')

  if not start or not end:  # Skip full-day events
    return

  # Convert to datetime objects and explicitly handle timezone
  start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')) - timedelta(hours=2)
  end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')) - timedelta(hours=2)

  # Calculate duration in minutes
  duration = int((end_dt - start_dt).total_seconds() / 60)

  if dry_run:
    # Just save to log file without creating task
    event_date = start_dt.strftime('%Y-%m-%d')
    save_synced_event(event['id'], event['summary'], event_date)
    print(colored(f"[DRY RUN] Would create task: {event['summary']}", 'yellow'))
    return

  # Create actual task if not dry run
  response = requests.post(
    'https://api.todoist.com/rest/v2/tasks',
    headers={
      'Authorization': f"Bearer {os.getenv('TODOIST_API_KEY')}",
      'Content-Type': 'application/json'
    },
    json={
      'content': event['summary'],
      'due_datetime': start_dt.isoformat(),
      'project_id': project_id,
      'duration': duration,
      'duration_unit': 'minute',
      'labels': ['Google-kalenterin tapahtuma']
    }
  )

  if response.status_code == 200:
    # Save the event to our log file
    event_date = start_dt.strftime('%Y-%m-%d')
    save_synced_event(event['id'], event['summary'], event_date)
    print(colored(f"Created task: {event['summary']}", 'green'))
  else:
    print(colored(f"Failed to create task: {event['summary']}", 'red'))

def sync_google_calendar_to_todoist(days: int = None, start_date: str = None, dry_run: bool = False):
  """Sync Google Calendar events to Todoist."""
  log_info("Syncing Google Calendar events to Todoist...")

  # Get project IDs
  work_project_id = get_todoist_project_id(os.getenv('TODOIST_WORK_PROJECT', 'todo'))
  personal_project_id = get_todoist_project_id(os.getenv('TODOIST_PERSONAL_PROJECT', 'todo'))

  # Get sync days from env or use default
  if days is None:
    days = int(os.getenv('GOOGLE_CALENDAR_SYNC_DAYS', '1'))

  # Refresh Google token
  access_token = refresh_google_token()

  # Build Google Calendar service
  creds = Credentials(
    token=access_token,
    refresh_token=os.getenv('GOOGLE_REFRESH_TOKEN'),
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    token_uri='https://oauth2.googleapis.com/token'
  )
  service = build('calendar', 'v3', credentials=creds)

  # Set time range
  if not start_date:
    # Set to beginning of today (00:00)
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
  else:
    start_date = datetime.fromisoformat(start_date)

  end_date = start_date + timedelta(days=days)

  calendars = {
    os.getenv('WORK_CALENDAR_ID'): work_project_id,
    os.getenv('FAMILY_CALENDAR_ID'): personal_project_id
  }

  for calendar_id, project_id in calendars.items():
    events_result = service.events().list(
      calendarId=calendar_id,
      timeMin=start_date.isoformat() + 'Z',
      timeMax=end_date.isoformat() + 'Z',
      singleEvents=True,
      orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    log_info(f"Found {len(events)} events in calendar")

    for event in events:
      # Skip declined events
      attendees = event.get('attendees', [])
      if any(a.get('self', False) and a.get('responseStatus') == 'declined' for a in attendees):
        log_info(f"Skipping declined event: {event['summary']}")
        continue

      # Skip full-day events
      if 'date' in event['start']:
        log_info(f"Skipping full-day event: {event['summary']}")
        continue

      # Get event's actual date
      event_date = datetime.fromisoformat(
        event['start']['dateTime'].replace('Z', '+00:00')
      ).strftime('%Y-%m-%d')

      # Skip if event was already synced
      if task_exists_in_todoist(event['id'], event['summary'], event_date):
        log_info(f"Skipping already synced event: {event['summary']}")
        continue

      create_todoist_task(event, project_id, dry_run=dry_run)

def check_todoist_api() -> bool:
  """Check if Todoist API is responding correctly."""
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}

  try:
    log_info("Checking Todoist API status...")
    response = requests.get(
      "https://api.todoist.com/rest/v2/projects",
      headers=headers
    )
    response.raise_for_status()
    return True
  except requests.exceptions.RequestException as e:
    print(colored(f"Todoist API is not responding correctly: {e}", 'red'))
    return False

def create_daily_note(dry_run: bool = False):
  # First check if Todoist API is available
  if not check_todoist_api():
    print(colored("Aborting note creation due to Todoist API issues", 'red'))
    return

  try:
    sync_google_calendar_to_todoist(dry_run=dry_run)
  except Exception as e:
    print(colored(f"Error syncing calendar events: {e}", 'red'))

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

  # Sync tasks with Todoist and update our tasks list with any changes
  sync_tasks_with_todoist(existing_tasks, tasks, full_path)

  # Get fresh task list after sync to include completion status changes
  tasks = get_todoist_tasks()

  task_count = len(tasks)
  formatted_tasks = format_todoist_tasks(tasks, is_today=True)

  # Format tasks section
  tasks_section = ""
  if task_count > 0:
    tasks_section = f"\n## Tehtävät\n{formatted_tasks}\n"

  # Format backlog section
  backlog_tasks = get_backlog_tasks()
  backlog_count = len(backlog_tasks)
  backlog_section = ""
  if backlog_count > 0:
    formatted_backlog = format_todoist_tasks(backlog_tasks, is_today=False)
    backlog_section = f"\n## Backlog\n{formatted_backlog}\n"

  # Format future tasks section
  future_tasks = get_future_tasks()
  future_count = len(future_tasks)
  future_section = ""
  if future_count > 0:
    formatted_future = format_todoist_tasks(future_tasks, is_today=False)
    future_section = f"\n## Tulevat tehtävät\n{formatted_future}\n"

  # Format weekday and month names for the header
  weekday_capitalized = weekday.capitalize()
  month_name = now.strftime("%B")

  # Update sync time message to use 24-hour format
  sync_time = datetime.now().strftime('%H:%M')
  sync_message = f"Synkronoitu viimeksi klo {sync_time}."

  # Create the content
  content = f"""# {weekday_capitalized}, {now.day}. {month_name}ta

{sync_message}

> [!NOTE] Note to self: Ajo-ohje itselleni
> Tehtävät tulevat Todoistista, mutta niitä voi täällä aikatauluttaa kalenteriin kätevästi Day Plannerin avulla.

## Päivän tehtävät

{formatted_tasks}

## Myöhemmin

{formatted_future}

## Backlog

{formatted_backlog}"""

  # Write the content to file
  with open(full_path, 'w', encoding='utf-8') as f:
    f.write(content)

  print(f"Daily note created at: {full_path}")

def get_todoist_project_id(project_name: str) -> str:
  """Get Todoist project ID by name."""
  api_key = os.getenv('TODOIST_API_KEY')
  if not api_key:
    raise ValueError("TODOIST_API_KEY not set in .env file")

  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    response = requests.get(
      "https://api.todoist.com/rest/v2/projects",
      headers=headers
    )
    response.raise_for_status()
    projects = response.json()
    for project in projects:
      if project['name'] == project_name:
        return project['id']
    raise ValueError(f"Project {project_name} not found in Todoist")
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching projects: {e}", 'red'))
    return None

def get_completed_tasks(headers: Dict) -> List[Dict]:
  """Load previously completed tasks from today."""
  log_info("Fetching completed tasks...")
  try:
    # Get completed tasks from sync API
    response = requests.get(
      "https://api.todoist.com/sync/v9/completed/get_all",
      headers=headers
    )
    response.raise_for_status()
    completed_data = response.json()

    # Get today's date in YYYY-MM-DD format, considering local timezone
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    log_info(f"Checking for tasks completed on {today}")
    completed_tasks = []

    # Process each completed task
    for item in completed_data.get("items", []):
      # Convert completed_at to local timezone before comparing
      completed_at = datetime.fromisoformat(
        item.get("completed_at").replace('Z', '+00:00')
      ).astimezone().strftime("%Y-%m-%d")

      if completed_at == today:
        log_info(f"\nProcessing task ID {item['id']}: {item.get('content')}")
        log_info(f"  Completed at: {item.get('completed_at')} (local: {completed_at})")
        log_info("  Task details:")
        log_info(f"    ID: {item.get('id')}")
        log_info(f"    Content: {item.get('content')}")
        log_info(f"    Parent ID: {item.get('parent_id')}")

        # Mark task as completed and add it to the list
        item['completed'] = True
        completed_tasks.append(item)
        log_info(f"  ✅ Added to completed tasks list")

    log_info(f"\nFinal completed tasks list ({len(completed_tasks)} tasks):")
    for task in completed_tasks:
      log_info(f"  - {task.get('content')} (ID: {task.get('id')}, Parent: {task.get('parent_id')})")

    return completed_tasks
  except requests.exceptions.RequestException as e:
    print(colored(f"Error fetching completed tasks: {e}", 'red'))
    return []

def dummy_sync_google_calendar(days: int = 30):
  """Populate synced_events.log with existing events without creating Todoist tasks."""
  log_info("Starting dummy sync to populate synced_events.log...")

  # Refresh Google token
  access_token = refresh_google_token()

  # Build Google Calendar service
  creds = Credentials(
    token=access_token,
    refresh_token=os.getenv('GOOGLE_REFRESH_TOKEN'),
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    token_uri='https://oauth2.googleapis.com/token'
  )
  service = build('calendar', 'v3', credentials=creds)

  # Set time range (past 30 days by default)
  end_date = datetime.now()
  start_date = end_date - timedelta(days=days)

  calendars = {
    os.getenv('WORK_CALENDAR_ID'): os.getenv('TODOIST_WORK_PROJECT', 'todo'),
    os.getenv('FAMILY_CALENDAR_ID'): os.getenv('TODOIST_PERSONAL_PROJECT', 'todo')
  }

  total_events = 0
  for calendar_id, project_name in calendars.items():
    events_result = service.events().list(
      calendarId=calendar_id,
      timeMin=start_date.isoformat() + 'Z',
      timeMax=end_date.isoformat() + 'Z',
      singleEvents=True,
      orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    log_info(f"Found {len(events)} events in calendar {calendar_id}")

    for event in events:
      # Skip declined events
      attendees = event.get('attendees', [])
      if any(a.get('self', False) and a.get('responseStatus') == 'declined' for a in attendees):
        continue

      # Skip full-day events
      if 'date' in event['start']:
        continue

      # Get event's actual date
      event_date = datetime.fromisoformat(
        event['start']['dateTime'].replace('Z', '+00:00')
      ).strftime('%Y-%m-%d')

      # Save to log file without creating Todoist task
      save_synced_event(event['id'], event['summary'], event_date)
      total_events += 1

  log_info(f"Dummy sync complete. Added {total_events} events to synced_events.log")

if __name__ == "__main__":
  # Add command line argument handling
  parser = argparse.ArgumentParser()
  parser.add_argument("--dry-run", action="store_true", help="Don't create tasks in Todoist, just populate the log file")
  args = parser.parse_args()

  create_daily_note(dry_run=args.dry_run)

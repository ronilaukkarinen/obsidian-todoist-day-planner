from datetime import datetime, timedelta
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

def format_todoist_tasks(tasks: List[Dict]) -> str:
  # Get project names
  project_names = get_project_names()

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
    project_name = project_names.get(str(project_id), "")
    parent_id = task.get("parent_id", None)

    # Convert content to classes
    classes = content_to_classes(content)

    # Create empty span with task ID, project name, and content classes
    id_span = f'<span data-id="{task_id}" data-project="{project_name}" class="{classes}"></span>' if task_id else ""

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
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{scheduled_time} {id_span}{content} {completion_time}')
          else:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{id_span}{content} {completion_time}')
        else:
          if scheduled_time:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{scheduled_time} {id_span}{content}')
          else:
            task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{id_span}{content}')
      else:
        # Handle case where time_str is just the completion time
        if INCLUDE_COMPLETION_DATE:
          task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{id_span}{content} {time_str}')
        else:
          task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{id_span}{content}')
    else:
      if time_str:
        task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{time_str} {id_span}{content}')
      else:
        task_lines.append(f'{indent}- [{checkbox}] {priority_tag}{id_span}{content}')

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

def get_future_tasks() -> List[Dict]:
  api_key = os.getenv('TODOIST_API_KEY')
  headers = {
    "Authorization": f"Bearer {api_key}"
  }

  try:
    log_info("Fetching future tasks...")
    response = requests.get(
      "https://api.todoist.com/rest/v2/tasks",
      headers=headers,
      params={"filter": "due after: today"}
    )
    response.raise_for_status()
    future_tasks = response.json()

    # Sort by priority (higher number = higher priority)
    future_tasks.sort(key=lambda x: x.get('priority', 1), reverse=True)
    return future_tasks
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

def task_exists_in_todoist(project_id: str, event_title: str, current_day: str) -> bool:
  """Check if task already exists in Todoist."""
  # Check active tasks
  active_response = requests.get(
    f"https://api.todoist.com/rest/v2/tasks?project_id={project_id}",
    headers={'Authorization': f"Bearer {os.getenv('TODOIST_API_KEY')}"}
  )
  active_tasks = active_response.json()

  # Check completed tasks
  completed_response = requests.get(
    f"https://api.todoist.com/sync/v9/completed/get_all?project_id={project_id}",
    headers={'Authorization': f"Bearer {os.getenv('TODOIST_API_KEY')}"}
  )
  completed_tasks = completed_response.json().get('items', [])

  # Check active tasks
  for task in active_tasks:
    if task['content'] == event_title and task.get('due', {}).get('date') == current_day:
      return True

  # Check completed tasks
  for task in completed_tasks:
    if task['content'].startswith(event_title) and task['completed_at'].split('T')[0] == current_day:
      return True

  return False

def create_todoist_task(event: Dict, project_id: str):
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
    print(colored(f"Created task: {event['summary']}", 'green'))
  else:
    print(colored(f"Failed to create task: {event['summary']}", 'red'))

def sync_google_calendar_to_todoist(days: int = None, start_date: str = None):
  """Sync Google Calendar events to Todoist before creating daily note."""
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
  start_date = datetime.now() if not start_date else datetime.fromisoformat(start_date)
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

    for event in events:
      # Skip declined events
      attendees = event.get('attendees', [])
      if any(a.get('self', False) and a.get('responseStatus') == 'declined' for a in attendees):
        continue

      # Skip full-day events
      if 'date' in event['start']:
        continue

      # Skip if task already exists
      if task_exists_in_todoist(project_id, event['summary'], start_date.date().isoformat()):
        continue

      create_todoist_task(event, project_id)

def create_daily_note():
  # First sync calendar events to Todoist
  try:
    sync_google_calendar_to_todoist()
  except Exception as e:
    print(colored(f"Error syncing calendar events: {e}", 'red'))
    # Continue with note creation even if calendar sync fails

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

  # Get future tasks
  future_tasks = get_future_tasks()
  formatted_future = format_todoist_tasks(future_tasks)

  # Get backlog tasks
  backlog_tasks = get_backlog_tasks()
  formatted_backlog = format_todoist_tasks(backlog_tasks)

  # Sync tasks with Todoist
  sync_tasks_with_todoist(existing_tasks, tasks)

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

if __name__ == "__main__":
  create_daily_note()

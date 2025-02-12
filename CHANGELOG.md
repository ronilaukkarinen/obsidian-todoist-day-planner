### 1.1.1: 2025-02-10

* Prevent tasks being added to Todoist if they already exist (when Todoist tasks added to calendar via Sunsama or via other means)

### 1.1.0: 2025-02-03

* Disable date sync from Obsidian to Todoist as it causes issues

### 1.0.9: 2025-02-01

* Create directory structure if it doesn't exist

### 1.0.8: 2025-01-29

* Add sync stop message to the daily note, skip syncing if we have that in the note
* Fix some tasks being scheduled for one year in the future

### 1.0.7: 2025-01-20

* Fix times not visible in scheduled and completed Todoist tasks
* Fix completed subtasks not being added to the daily note

### 1.0.6: 2025-01-18

* Add colors for blocks via CSS
* Add checkbox styles
* Preserve custom sections in daily note
* Sort tasks in this order: 1. priority, 2. time, 3. creation date (newest first)
* Remove duplicate tasks from the daily note
* Sync completed tasks from Obsidian to Todoist
* Move amount of tasks under each heading
* Update feature list in README
* Sync times from Obsidian back to Todoist

### 1.0.5: 2025-01-16

* Make Google Calendar sync more reliable by adding a log file to compare with
* Add --dry-run option to not create tasks in Todoist

### 1.0.4: 2025-01-15

* Fix events containing emojis or special characters being added twice to Todoist

### 1.0.3: 2025-01-13

* Fix Google Calendar sync to not add two hours to the time
* Fix NoneType error when duration is not set
* Fix start date not being set to beginning of today
* Fix Google Calendar sync logic for dates that are not today
* Fix some events being added twice to Todoist
* Check Todoist API status before creating a note

### 1.0.2: 2025-01-12

* Add note about personal nature of the project
* Add backlog functionality
* Fix completion time not always being in the end
* Fix timezone is two hours behind
* Include p1 and p2 diamonds instructions
* Add data-id for tasks in Obsidian and prepare for two-day sync
* Disable completion time in brackets as it shows in Day Planner
* Add data-project to span for coloring Day Planner blocks
* Add indent subtask support
* Make span not to break the formatting
* Add "Later" section for tasks that are not due today
* Helper classes to task blocks for Day Planner for coloring blocks
* Sync Google Calendar to Todoist
* Add verbose logging for Google Calendar sync

### 1.0.0: 2025-01-12

- Initial release
- Add first version of the daily note script
- Add verbose logging with colored output
- Sync completed and active tasks from Todoist in the same list
- Add task completion status to the daily note

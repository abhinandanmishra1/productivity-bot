# Slack Productivity Bot Setup Guide

## Prerequisites
- Python 3.8+ installed
- A Slack workspace where you can create apps
- ngrok (for local development) or a server with public IP

## Step 1: Setup Python Environment

```bash
# Create virtual environment
python -m venv slack_bot_env
source slack_bot_env/bin/activate  # On Windows: slack_bot_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Run the FastAPI Server

```bash
# Run the server locally
python main.py
```

The server will start on `http://localhost:8000`. You can test it by visiting this URL in your browser.

## Step 3: Expose Local Server (for Development)

If you're testing locally, you need to expose your server to the internet so Slack can reach it.

### Option A: Using ngrok
1. Install ngrok: https://ngrok.com/download
2. Run: `ngrok http 8000`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Option B: Deploy to a Cloud Provider
- Deploy to Heroku, AWS, Google Cloud, or any cloud provider
- Make sure your server runs on the port specified by the environment

## Step 4: Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Enter App Name: "Productivity Bot"
4. Select your workspace

## Step 5: Configure Slash Command

1. In your Slack app settings, go to "Slash Commands"
2. Click "Create New Command"
3. Configure:
   - **Command**: `/task`
   - **Request URL**: `https://your-server-url.com/slack/command` (replace with your actual URL)
   - **Short Description**: "Manage your tasks with natural language"
   - **Usage Hint**: `create <task description> | list | show <id> | update <id> <status>`

## Step 6: Install App to Workspace

1. Go to "Install App" in the left sidebar
2. Click "Install to Workspace"
3. Authorize the app

## Step 7: Test Your Bot

In any Slack channel, try these commands:

```
/task
/task create Review project proposal by tomorrow
/task create Set up meeting with client next week
/task list
/task show abc123
/task update abc123 completed
/task delete abc123
```

## Available Commands

### Create Tasks
- `/task create Buy groceries` - Simple task
- `/task create Review documents by Friday` - Task with deadline
- `/task create Project meeting tomorrow at 2pm` - Task with specific time
- `/task create Quarterly report due next week` - Task with relative deadline

### Manage Tasks
- `/task list` - Show all your tasks
- `/task show <task_id>` - Show detailed task info
- `/task update <task_id> pending` - Change status to pending
- `/task update <task_id> in_progress` - Mark as in progress
- `/task update <task_id> completed` - Mark as completed
- `/task delete <task_id>` - Delete a task

## Natural Language Processing Features

The bot can understand various deadline formats:
- "by tomorrow" / "by today"
- "next week" / "next month"
- "in 3 days"
- Specific dates: "12/25/2024" or "12/25"
- Day names: "monday", "friday"

## Production Considerations

### 1. Database
Currently uses in-memory storage. For production, replace with:
- PostgreSQL
- MongoDB
- SQLite for smaller deployments

### 2. Authentication
Add Slack signature verification:
```python
# Add this to validate requests are from Slack
def verify_slack_signature(request_body: str, timestamp: str, signature: str):
    slack_signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
    # Implementation for signature verification
```

### 3. Environment Variables
```bash
# Add these environment variables
SLACK_SIGNING_SECRET=your_slack_signing_secret
DATABASE_URL=your_database_url
PORT=8000
```

### 4. Error Handling & Logging
- Add proper logging
- Implement error tracking (Sentry)
- Add retry mechanisms for external API calls

### 5. Rate Limiting
Implement rate limiting to prevent abuse

## Extending the Bot

### Add Subtasks
Modify the Task model to support hierarchical tasks:
```python
class Task(BaseModel):
    # ... existing fields ...
    parent_task_id: Optional[str] = None
    subtasks: List[str] = []
```

### Add Due Date Reminders
- Integrate with Slack's scheduled messages API
- Set up cron jobs to send reminders

### Add Team Features
- Assign tasks to other users
- Share tasks across channels
- Team dashboards

### Add Integration
- Calendar integration (Google Calendar, Outlook)
- Project management tools (Jira, Trello)
- Time tracking

## Troubleshooting

### Common Issues:

1. **"Command not found"**
   - Make sure the slash command is properly configured
   - Check that the app is installed in your workspace

2. **"Request failed"**
   - Verify your server is running and accessible
   - Check ngrok tunnel is active
   - Ensure the Request URL in Slack matches your server

3. **"Task not found"**
   - Task IDs are case-sensitive
   - Use `/task list` to see available task IDs

4. **Server errors**
   - Check server logs
   - Verify all dependencies are installed
   - Make sure Python version is 3.8+

## API Endpoints

- `GET /` - Health check
- `POST /slack/command` - Handle Slack slash commands
- `GET /tasks` - Get all tasks (debugging)

The server provides a clean API that you can extend with additional endpoints for web interfaces or mobile apps.
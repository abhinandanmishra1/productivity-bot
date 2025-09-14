from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import re
from datetime import datetime, timedelta
import hashlib
import hmac
import os
from dateutil import parser
import uvicorn

app = FastAPI(title="Slack Productivity Bot", version="1.0.0")

# Data models
class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed
    created_at: datetime
    subtasks: List[str] = []  # List of subtask IDs

class SlackMessage(BaseModel):
    token: str
    team_id: str
    team_domain: str
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str
    command: str
    text: str
    response_url: str

# In-memory storage (use database in production)
tasks_db: Dict[str, Task] = {}
user_tasks: Dict[str, List[str]] = {}  # user_id -> task_ids

def generate_task_id() -> str:
    """Generate a unique task ID"""
    import uuid
    return str(uuid.uuid4())[:8]

def parse_natural_language(text: str) -> Dict[str, Any]:
    """Parse natural language input to extract task details"""
    
    # Extract deadline patterns
    deadline_patterns = [
        r"(by|due|deadline|until)\s+(.+?)(?:\s+|$)",
        r"(tomorrow|today|next week|next month)",
        r"(\d{1,2}/\d{1,2}/\d{4})",
        r"(\d{1,2}/\d{1,2})",
        r"(in\s+\d+\s+days?)",
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
    ]
    
    deadline = None
    deadline_text = ""
    
    for pattern in deadline_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            deadline_text = match.group(0)
            try:
                # Try to parse the deadline
                if "tomorrow" in deadline_text.lower():
                    deadline = datetime.now() + timedelta(days=1)
                elif "today" in deadline_text.lower():
                    deadline = datetime.now().replace(hour=23, minute=59)
                elif "next week" in deadline_text.lower():
                    deadline = datetime.now() + timedelta(weeks=1)
                elif "next month" in deadline_text.lower():
                    deadline = datetime.now() + timedelta(days=30)
                elif "in" in deadline_text.lower() and "day" in deadline_text.lower():
                    days = int(re.search(r'\d+', deadline_text).group())
                    deadline = datetime.now() + timedelta(days=days)
                else:
                    # Try to parse as date
                    deadline = parser.parse(deadline_text)
            except:
                deadline = None
            break
    
    # Remove deadline text from the main text
    if deadline_text:
        text = text.replace(deadline_text, "").strip()
    
    # Extract task title (first line or sentence)
    lines = text.split('\n')
    title = lines[0].strip()
    
    # Extract description (remaining text)
    description = None
    if len(lines) > 1 or len(text.split('.')) > 1:
        if len(lines) > 1:
            description = '\n'.join(lines[1:]).strip()
        else:
            sentences = text.split('.')
            if len(sentences) > 1:
                title = sentences[0].strip()
                description = '.'.join(sentences[1:]).strip()
    
    return {
        "title": title if title else text,
        "description": description,
        "deadline": deadline
    }

def create_task(user_id: str, task_data: Dict[str, Any]) -> Task:
    """Create a new task"""
    task_id = generate_task_id()
    task = Task(
        id=task_id,
        title=task_data["title"],
        description=task_data.get("description"),
        deadline=task_data.get("deadline"),
        created_at=datetime.now()
    )
    
    tasks_db[task_id] = task
    
    if user_id not in user_tasks:
        user_tasks[user_id] = []
    user_tasks[user_id].append(task_id)
    
    return task

def format_task_response(task: Task) -> str:
    """Format task as Slack message"""
    response = f"✅ **Task Created:** {task.title}\n"
    response += f"📝 **ID:** {task.id}\n"
    
    if task.description:
        response += f"📋 **Description:** {task.description}\n"
    
    if task.deadline:
        response += f"⏰ **Deadline:** {task.deadline.strftime('%Y-%m-%d %H:%M')}\n"
    
    response += f"📊 **Status:** {task.status.replace('_', ' ').title()}\n"
    response += f"🕐 **Created:** {task.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    return response

def list_user_tasks(user_id: str) -> str:
    """List all tasks for a user"""
    if user_id not in user_tasks or not user_tasks[user_id]:
        return "📭 You don't have any tasks yet! Use `/task create <task description>` to create one."
    
    response = f"📋 **Your Tasks ({len(user_tasks[user_id])}):**\n\n"
    
    for task_id in user_tasks[user_id]:
        if task_id in tasks_db:
            task = tasks_db[task_id]
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅"
            }.get(task.status, "❓")
            
            response += f"{status_emoji} **{task.id}** - {task.title}"
            if task.deadline:
                response += f" (Due: {task.deadline.strftime('%m/%d')})"
            response += "\n"
    
    response += "\n💡 Use `/task show <task_id>` to see details or `/task update <task_id> <status>` to update status."
    return response

@app.post("/slack/command")
async def handle_slack_command(request: Request):
    """Handle Slack slash commands"""
    
    # Parse form data
    form_data = await request.form()
    
    # Extract command parameters
    user_id = form_data.get("user_id")
    text = form_data.get("text", "").strip()
    
    if not text:
        return {
            "response_type": "ephemeral",
            "text": "🤖 **Slack Productivity Bot Help**\n\n"
                   "**Commands:**\n"
                   "• `/task create <description>` - Create a new task\n"
                   "• `/task list` - List all your tasks\n"
                   "• `/task show <task_id>` - Show task details\n"
                   "• `/task update <task_id> <status>` - Update task status (pending/in_progress/completed)\n"
                   "• `/task delete <task_id>` - Delete a task\n\n"
                   "**Examples:**\n"
                   "• `/task create Review project proposal by tomorrow`\n"
                   "• `/task create Set up meeting with client next week`\n"
                   "• `/task update abc123 completed`"
        }
    
    parts = text.split(None, 2)  # Split into max 3 parts
    action = parts[0].lower() if parts else ""
    
    try:
        if action == "create":
            if len(parts) < 2:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Please provide a task description. Example: `/task create Review documents by Friday`"
                }
            
            task_input = " ".join(parts[1:])
            parsed_data = parse_natural_language(task_input)
            task = create_task(user_id, parsed_data)
            
            return {
                "response_type": "in_channel",
                "text": format_task_response(task)
            }
        
        elif action == "list":
            return {
                "response_type": "ephemeral",
                "text": list_user_tasks(user_id)
            }
        
        elif action == "show":
            if len(parts) < 2:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Please provide a task ID. Example: `/task show abc123`"
                }
            
            task_id = parts[1]
            if task_id not in tasks_db:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Task '{task_id}' not found."
                }
            
            task = tasks_db[task_id]
            return {
                "response_type": "ephemeral",
                "text": format_task_response(task)
            }
        
        elif action == "update":
            if len(parts) < 3:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Please provide task ID and status. Example: `/task update abc123 completed`"
                }
            
            task_id = parts[1]
            new_status = parts[2].lower()
            
            if task_id not in tasks_db:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Task '{task_id}' not found."
                }
            
            if new_status not in ["pending", "in_progress", "completed"]:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Status must be one of: pending, in_progress, completed"
                }
            
            tasks_db[task_id].status = new_status
            
            status_messages = {
                "pending": "⏳ Task moved to pending",
                "in_progress": "🔄 Task is now in progress",
                "completed": "🎉 Task completed!"
            }
            
            return {
                "response_type": "in_channel",
                "text": f"{status_messages[new_status]}\n{format_task_response(tasks_db[task_id])}"
            }
        
        elif action == "delete":
            if len(parts) < 2:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Please provide a task ID. Example: `/task delete abc123`"
                }
            
            task_id = parts[1]
            if task_id not in tasks_db:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Task '{task_id}' not found."
                }
            
            # Remove from user's task list
            if user_id in user_tasks and task_id in user_tasks[user_id]:
                user_tasks[user_id].remove(task_id)
            
            # Remove from tasks database
            deleted_task = tasks_db.pop(task_id)
            
            return {
                "response_type": "ephemeral",
                "text": f"🗑️ Task '{deleted_task.title}' has been deleted."
            }
        
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown action '{action}'. Use `/task` without parameters to see help."
            }
    
    except Exception as e:
        return {
            "response_type": "ephemeral",
            "text": f"❌ An error occurred: {str(e)}"
        }

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Slack Productivity Bot API is running!",
        "total_tasks": len(tasks_db),
        "total_users": len(user_tasks)
    }

@app.get("/tasks")
async def get_all_tasks():
    """Get all tasks (for debugging/admin)"""
    return {
        "tasks": list(tasks_db.values()),
        "user_tasks": user_tasks
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Task


def get_tasks(db: Session) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.due_date)).all())


def complete_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise LookupError("Task not found")
    task.status = "completed"
    return task

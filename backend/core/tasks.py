from celery import shared_task

@shared_task
def ping() -> str:
    """Task uji untuk memastikan worker bisa menjangkau broker."""
    return "pong"
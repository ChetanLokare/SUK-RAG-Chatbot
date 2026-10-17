from celery import Celery

celery_app = Celery(
    "suk_rag",
    broker="redis://localhost:6379/0",
)

@celery_app.task
def ingest_source_task(source_id):
    # fetch source from DB
    # call correct ingestion function
    pass

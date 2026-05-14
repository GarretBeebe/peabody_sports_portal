from apscheduler.schedulers.background import BackgroundScheduler


def init_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: _run(app),
        trigger="cron",
        hour=app.config["SCHEDULER_HOUR"],
        minute=0,
        id="daily_email_job",
        replace_existing=True,
    )
    scheduler.start()


def _run(app):
    with app.app_context():
        from app.email.pipeline import run_daily_job
        run_daily_job()

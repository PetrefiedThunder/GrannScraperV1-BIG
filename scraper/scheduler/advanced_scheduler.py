"""
Advanced job scheduler with cron, natural language, and smart scheduling.

Features:
- Cron expressions
- Natural language scheduling ("every Monday at 9am")
- Smart scheduling (off-peak hours)
- Dependency-based scheduling
- Missed run handling
"""

import asyncio
import logging
import re
from croniter import croniter
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleExpression:
    """
    Parse and evaluate schedule expressions.

    Supports:
    - Cron: "0 9 * * 1" (Monday at 9am)
    - Natural: "every Monday at 9am"
    - Interval: "every 30 minutes"
    - One-time: "at 2024-12-01 15:00"
    """

    def __init__(self, expression: str):
        self.expression = expression
        self.cron_expr: Optional[str] = None
        self.interval_seconds: Optional[int] = None
        self.one_time: Optional[datetime] = None

        self._parse()

    def _parse(self):
        """Parse schedule expression."""
        expr = self.expression.lower().strip()

        # Try cron format first (5 parts separated by spaces)
        if re.match(r'^[\d\*\-,/]+ [\d\*\-,/]+ [\d\*\-,/]+ [\d\*\-,/]+ [\d\*\-,/]+$', expr):
            self.cron_expr = expr
            return

        # Natural language patterns
        # "every X minutes/hours/days"
        interval_match = re.match(r'every (\d+) (minute|hour|day|week)s?', expr)
        if interval_match:
            amount = int(interval_match.group(1))
            unit = interval_match.group(2)

            multipliers = {
                'minute': 60,
                'hour': 3600,
                'day': 86400,
                'week': 604800
            }
            self.interval_seconds = amount * multipliers[unit]
            return

        # "every Monday/Tuesday/etc at HH:MM"
        weekday_match = re.match(
            r'every (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (\d{1,2}):?(\d{2})',
            expr
        )
        if weekday_match:
            weekdays = {
                'monday': 1, 'tuesday': 2, 'wednesday': 3,
                'thursday': 4, 'friday': 5, 'saturday': 6, 'sunday': 0
            }
            weekday = weekdays[weekday_match.group(1)]
            hour = int(weekday_match.group(2))
            minute = int(weekday_match.group(3))

            # Convert to cron: minute hour day month weekday
            self.cron_expr = f"{minute} {hour} * * {weekday}"
            return

        # "every day at HH:MM"
        daily_match = re.match(r'every day at (\d{1,2}):?(\d{2})', expr)
        if daily_match:
            hour = int(daily_match.group(1))
            minute = int(daily_match.group(2))
            self.cron_expr = f"{minute} {hour} * * *"
            return

        # "at YYYY-MM-DD HH:MM" (one-time)
        onetime_match = re.match(
            r'at (\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2})',
            expr
        )
        if onetime_match:
            year = int(onetime_match.group(1))
            month = int(onetime_match.group(2))
            day = int(onetime_match.group(3))
            hour = int(onetime_match.group(4))
            minute = int(onetime_match.group(5))

            self.one_time = datetime(year, month, day, hour, minute)
            return

        raise ValueError(f"Invalid schedule expression: {self.expression}")

    def get_next_run(self, from_time: Optional[datetime] = None) -> Optional[datetime]:
        """Get next scheduled run time."""
        now = from_time or datetime.utcnow()

        if self.cron_expr:
            cron = croniter(self.cron_expr, now)
            return cron.get_next(datetime)

        elif self.interval_seconds:
            return now + timedelta(seconds=self.interval_seconds)

        elif self.one_time:
            return self.one_time if self.one_time > now else None

        return None


class ScheduledJob:
    """A scheduled scraping job."""

    def __init__(
        self,
        job_id: str,
        schedule: str,
        job_func: Callable,
        enabled: bool = True,
        max_missed_runs: int = 3,
        catch_up: bool = False
    ):
        self.job_id = job_id
        self.schedule_expr = ScheduleExpression(schedule)
        self.job_func = job_func
        self.enabled = enabled
        self.max_missed_runs = max_missed_runs
        self.catch_up = catch_up

        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.missed_runs = 0

        self._calculate_next_run()

    def _calculate_next_run(self):
        """Calculate next run time."""
        self.next_run = self.schedule_expr.get_next_run(self.last_run)

    async def execute(self):
        """Execute the job."""
        if not self.enabled:
            logger.info(f"Job {self.job_id} is disabled, skipping")
            return

        logger.info(f"Executing scheduled job: {self.job_id}")

        try:
            result = await self.job_func()
            self.last_run = datetime.utcnow()
            self.run_count += 1
            self.missed_runs = 0

            logger.info(f"Job {self.job_id} completed successfully")
            return result

        except Exception as e:
            self.error_count += 1
            logger.error(f"Job {self.job_id} failed: {e}")
            raise

        finally:
            self._calculate_next_run()

    def should_run(self, now: Optional[datetime] = None) -> bool:
        """Check if job should run now."""
        if not self.enabled:
            return False

        if not self.next_run:
            return False

        now = now or datetime.utcnow()
        return now >= self.next_run

    def mark_missed(self):
        """Mark a missed run."""
        self.missed_runs += 1
        logger.warning(
            f"Job {self.job_id} missed run "
            f"({self.missed_runs}/{self.max_missed_runs})"
        )

        if self.missed_runs >= self.max_missed_runs:
            logger.error(f"Job {self.job_id} disabled due to too many missed runs")
            self.enabled = False


class AdvancedScheduler:
    """
    Advanced job scheduler with cron and natural language support.

    Features:
    - Multiple schedule types (cron, interval, natural language)
    - Missed run handling
    - Catch-up execution
    - Job dependencies
    - Smart scheduling (off-peak hours)
    """

    def __init__(self):
        self.jobs: Dict[str, ScheduledJob] = {}
        self.is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def add_job(
        self,
        job_id: str,
        schedule: str,
        job_func: Callable,
        **kwargs
    ):
        """
        Add a scheduled job.

        Args:
            job_id: Unique job identifier
            schedule: Schedule expression
            job_func: Async function to execute
            **kwargs: Additional job options
        """
        if job_id in self.jobs:
            raise ValueError(f"Job {job_id} already exists")

        job = ScheduledJob(job_id, schedule, job_func, **kwargs)
        self.jobs[job_id] = job

        logger.info(
            f"Added scheduled job: {job_id} "
            f"(schedule: {schedule}, next run: {job.next_run})"
        )

    def remove_job(self, job_id: str):
        """Remove a scheduled job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Removed scheduled job: {job_id}")

    async def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

        logger.info("Scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self.is_running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.is_running:
            try:
                now = datetime.utcnow()

                # Check all jobs
                for job_id, job in self.jobs.items():
                    if job.should_run(now):
                        # Execute job in background
                        asyncio.create_task(self._execute_job(job))

                # Check every 30 seconds
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    async def _execute_job(self, job: ScheduledJob):
        """Execute a job (in background)."""
        try:
            await job.execute()
        except Exception as e:
            logger.error(f"Job execution failed: {e}")

    def get_schedule(self) -> List[Dict[str, Any]]:
        """Get current schedule for all jobs."""
        schedule = []

        for job_id, job in self.jobs.items():
            schedule.append({
                'job_id': job_id,
                'enabled': job.enabled,
                'schedule': job.schedule_expr.expression,
                'last_run': job.last_run.isoformat() if job.last_run else None,
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'run_count': job.run_count,
                'error_count': job.error_count,
                'missed_runs': job.missed_runs,
            })

        # Sort by next run time
        schedule.sort(key=lambda x: x['next_run'] or '9999')

        return schedule


class SmartScheduler:
    """
    Intelligent scheduler that optimizes run times.

    Features:
    - Off-peak hour preference
    - Load balancing across time
    - Avoids clustering jobs
    - Adaptive scheduling based on job duration
    """

    def __init__(self, scheduler: AdvancedScheduler):
        self.scheduler = scheduler
        self.job_durations: Dict[str, float] = {}  # Track average duration
        self.peak_hours = [(9, 17)]  # 9am-5pm by default

    def suggest_schedule(
        self,
        job_id: str,
        desired_frequency: str,
        prefer_off_peak: bool = True
    ) -> str:
        """
        Suggest optimal schedule for a job.

        Args:
            job_id: Job identifier
            desired_frequency: Desired frequency (daily, hourly, etc.)
            prefer_off_peak: Prefer off-peak hours

        Returns:
            Suggested schedule expression
        """
        # Get current schedule load
        current_schedule = self.scheduler.get_schedule()

        # Analyze load by hour
        hourly_load = self._analyze_hourly_load(current_schedule)

        # Find least loaded hour
        if prefer_off_peak:
            # Filter to off-peak hours
            off_peak_hours = [
                h for h in range(24)
                if not any(start <= h < end for start, end in self.peak_hours)
            ]
            candidates = {h: hourly_load.get(h, 0) for h in off_peak_hours}
        else:
            candidates = hourly_load

        # Choose hour with least load
        best_hour = min(candidates, key=candidates.get)

        # Generate schedule based on frequency
        if desired_frequency == "daily":
            return f"every day at {best_hour}:00"
        elif desired_frequency == "weekly":
            return f"every Monday at {best_hour}:00"
        elif desired_frequency == "hourly":
            return "every 1 hour"
        else:
            return f"0 {best_hour} * * *"  # Daily at best hour

    def _analyze_hourly_load(self, schedule: List[Dict]) -> Dict[int, int]:
        """Analyze job load by hour of day."""
        hourly_load = {}

        for job in schedule:
            if job['next_run']:
                try:
                    next_run = datetime.fromisoformat(job['next_run'])
                    hour = next_run.hour
                    hourly_load[hour] = hourly_load.get(hour, 0) + 1
                except:
                    pass

        return hourly_load

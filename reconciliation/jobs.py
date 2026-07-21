from datetime import timedelta
from secrets import token_hex
from typing import Any
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Organization, Job, JobEvent, ReconciliationVersion
from .provider import explain


@transaction.atomic
def enqueue(org_id: int, version_id: int) -> Job:
    Organization.objects.select_for_update().get(pk=org_id)
    version = ReconciliationVersion.objects.filter(pk=version_id, invoice__org_id=org_id).first()
    if not version:
        raise ValueError("Version not found")
    if version.exceptions.count() > 100:
        raise ValueError("At most 100 exception facts per explanation")
    if Job.objects.filter(org_id=org_id, status__in=["queued", "running"]).count() >= 10:
        raise ValueError("Organization queue cap is ten active jobs")
    job = Job.objects.create(
        org_id=org_id,
        version=version,
        deadline=timezone.now() + timedelta(minutes=2),
        usage={"known": False},
    )
    JobEvent.objects.create(job=job, kind="queued")
    return job


def claim() -> Job | None:
    candidate = (
        Job.objects.filter(
            Q(status="queued") | Q(status="running", lease_until__lte=timezone.now())
        )
        .order_by("id")
        .first()
    )
    if not candidate:
        return None
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=candidate.org_id)
        job = Job.objects.select_for_update().get(pk=candidate.id)
        now = timezone.now()
        if job.status not in {"queued", "running"} or (
            job.status == "running" and job.lease_until and job.lease_until > now
        ):
            return None
        if job.deadline <= now:
            job.status = "expired"
            job.save(update_fields=["status"])
            JobEvent.objects.create(job=job, kind="expired")
            return None
        job.status = "running"
        job.token = token_hex(24)
        job.lease_until = now + timedelta(seconds=30)
        job.save(update_fields=["status", "token", "lease_until"])
        JobEvent.objects.create(job=job, kind="claimed")
        return job


def publish(
    job_id: int, token: str, result: dict[str, Any] | None, usage: dict[str, Any], error: str = ""
) -> bool:
    candidate = Job.objects.get(pk=job_id)
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=candidate.org_id)
        job = Job.objects.select_for_update().get(pk=job_id)
        now = timezone.now()
        if (
            job.status != "running"
            or job.token != token
            or not job.lease_until
            or job.lease_until <= now
            or job.deadline <= now
        ):
            return False
        job.status = "failed" if error else "complete"
        job.result = result
        job.usage = usage
        job.save(update_fields=["status", "result", "usage"])
        JobEvent.objects.create(job=job, kind=job.status, detail=error[:500])
        return True


@transaction.atomic
def cancel(org_id: int, job_id: int) -> None:
    Organization.objects.select_for_update().get(pk=org_id)
    job = Job.objects.select_for_update().filter(pk=job_id, org_id=org_id).first()
    if not job:
        raise ValueError("Job not found")
    if job.status in {"queued", "running"}:
        job.status = "cancelled"
        job.token = ""
        job.save(update_fields=["status", "token"])
        JobEvent.objects.create(job=job, kind="cancelled")


def work_once(mode: str = "normal") -> bool:
    job = claim()
    if not job:
        return False
    facts = [
        {"id": e.id, "code": e.code, "line": e.line, "facts": e.facts}
        for e in job.version.exceptions.order_by("id")
    ]
    try:
        result = explain(facts, mode)
        publish(job.id, job.token, result, result["usage"])
    except (ValueError, OSError) as exc:
        publish(job.id, job.token, None, {"known": False}, str(exc))
    return True

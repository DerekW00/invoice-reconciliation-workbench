from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Membership, Invoice, ImportBatch, Job
from .forms import ImportForm, ResolutionForm
from .imports import import_csv
from .engine import reconcile
from .reviews import resolve, approve
from .exports import export_approved
from .jobs import enqueue, cancel


def organization(request: HttpRequest):
    if request.user.pk is None:
        raise Http404("Authentication required")
    membership = Membership.objects.select_related("org").filter(user_id=request.user.pk).first()
    if not membership:
        raise Http404("No active organization")
    return membership.org


def scoped(request: HttpRequest, invoice_id: int):
    org = organization(request)
    return org, get_object_or_404(Invoice, pk=invoice_id, org=org)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    org = organization(request)
    form = ImportForm(request.POST or None, request.FILES or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            uploaded = form.cleaned_data["file"]
            result = import_csv(org.id, form.cleaned_data["kind"], uploaded.read(262145))
            if result.invoice_ids:
                return redirect("detail", invoice_id=result.invoice_ids[0])
            return redirect("dashboard")
        except ValueError as exc:
            error = str(exc)
    invoices = Invoice.objects.filter(org=org).order_by("-id")
    return render(
        request,
        "reconciliation/dashboard.html",
        {
            "org": org,
            "form": form,
            "error": error,
            "invoices": invoices,
            "batches": ImportBatch.objects.filter(org=org).order_by("-id")[:8],
            "review_count": invoices.filter(status="review").count(),
            "approved_count": invoices.filter(status="approved").count(),
        },
    )


@login_required
def detail(request: HttpRequest, invoice_id: int) -> HttpResponse:
    org, invoice = scoped(request, invoice_id)
    version = reconcile(org.id, invoice.id)
    return render(
        request,
        "reconciliation/detail.html",
        {
            "org": org,
            "invoice": invoice,
            "version": version,
            "form": ResolutionForm(initial={"revision": version.revision}),
            "jobs": Job.objects.filter(org=org, version__invoice=invoice).order_by("-id")[:5],
            "poll": 0,
            "next_poll": 1,
            "active_jobs": Job.objects.filter(
                org=org, version__invoice=invoice, status__in=["queued", "running"]
            ).exists(),
        },
    )


@login_required
@require_POST
def review_action(request: HttpRequest, invoice_id: int, action: str) -> HttpResponse:
    org, invoice = scoped(request, invoice_id)
    try:
        revision = int(request.POST.get("revision", "0"))
        if action == "resolve":
            resolve(
                org.id,
                invoice.id,
                expected_revision=revision,
                note=request.POST.get("note", ""),
                actor_id=request.user.pk,
            )
        elif action == "approve":
            approve(org.id, invoice.id, expected_revision=revision, actor_id=request.user.pk)
        else:
            raise Http404
    except ValueError as exc:
        return render(
            request,
            "reconciliation/conflict.html",
            {"org": org, "invoice": invoice, "error": str(exc)},
            status=409,
        )
    return redirect("detail", invoice_id=invoice.id)


@login_required
def export(request: HttpRequest, invoice_id: int) -> HttpResponse:
    org, invoice = scoped(request, invoice_id)
    try:
        data = export_approved(org.id, invoice.id)
    except ValueError as exc:
        return HttpResponse(str(exc), status=409)
    response = HttpResponse(data, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="approved-ledger-{invoice.id}.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def explain_action(request: HttpRequest, invoice_id: int) -> HttpResponse:
    org, invoice = scoped(request, invoice_id)
    try:
        enqueue(org.id, reconcile(org.id, invoice.id).id)
    except ValueError as exc:
        return HttpResponse(str(exc), status=409)
    return redirect("detail", invoice_id=invoice.id)


@login_required
@require_POST
def cancel_action(request: HttpRequest, job_id: int) -> HttpResponse:
    org = organization(request)
    job = get_object_or_404(Job, pk=job_id, org=org)
    cancel(org.id, job.id)
    return redirect("detail", invoice_id=job.version.invoice_id)


@login_required
def activity(request: HttpRequest, invoice_id: int) -> HttpResponse:
    org, invoice = scoped(request, invoice_id)
    try:
        poll = min(max(int(request.GET.get("poll", "0")), 0), 24)
    except ValueError:
        return HttpResponse("Invalid poll counter", status=400)
    jobs = Job.objects.filter(org=org, version__invoice=invoice)
    return render(
        request,
        "reconciliation/activity.html",
        {
            "invoice": invoice,
            "jobs": jobs.order_by("-id")[:5],
            "poll": poll,
            "next_poll": poll + 1,
            "active_jobs": jobs.filter(status__in=["queued", "running"]).exists(),
        },
    )

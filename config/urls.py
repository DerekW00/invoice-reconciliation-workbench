from django.contrib.auth import views as auth
from django.urls import path
from reconciliation import views

urlpatterns = [
    path("login/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth.LogoutView.as_view(next_page="/login/"), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("invoices/<int:invoice_id>/", views.detail, name="detail"),
    path(
        "invoices/<int:invoice_id>/resolve/",
        views.review_action,
        {"action": "resolve"},
        name="resolve",
    ),
    path(
        "invoices/<int:invoice_id>/approve/",
        views.review_action,
        {"action": "approve"},
        name="approve",
    ),
    path("invoices/<int:invoice_id>/export/", views.export, name="export"),
    path("invoices/<int:invoice_id>/explain/", views.explain_action, name="explain"),
    path("invoices/<int:invoice_id>/activity/", views.activity, name="activity"),
    path("jobs/<int:job_id>/cancel/", views.cancel_action, name="cancel"),
]

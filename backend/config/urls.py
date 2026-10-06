from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.telemetry.urls")),
    path("admin/", admin.site.urls),
    path("api/v1/health/", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.projects.urls")),
]

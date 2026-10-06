import uuid

from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="uniq_project_slug_per_organization",
            )
        ]
        ordering = ["organization_id", "name", "id"]

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import QuerySet

from .models import Project


def projects_for_user(user: User | AnonymousUser) -> QuerySet[Project]:
    if isinstance(user, AnonymousUser):
        return Project.objects.none()
    return Project.objects.filter(organization__memberships__user=user).distinct()

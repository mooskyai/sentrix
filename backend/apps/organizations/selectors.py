from django.contrib.auth.models import AnonymousUser, User
from django.db.models import QuerySet

from .models import Organization, OrganizationMembership

WRITE_ROLES = {
    OrganizationMembership.Role.OWNER,
    OrganizationMembership.Role.ADMIN,
    OrganizationMembership.Role.EDITOR,
}
ADMIN_ROLES = {
    OrganizationMembership.Role.OWNER,
    OrganizationMembership.Role.ADMIN,
}


def organizations_for_user(user: User | AnonymousUser) -> QuerySet[Organization]:
    if isinstance(user, AnonymousUser):
        return Organization.objects.none()
    return Organization.objects.filter(memberships__user=user).distinct()


def membership_for_user(
    *, user: User | AnonymousUser, organization: Organization
) -> OrganizationMembership | None:
    if isinstance(user, AnonymousUser):
        return None
    return OrganizationMembership.objects.filter(organization=organization, user=user).first()

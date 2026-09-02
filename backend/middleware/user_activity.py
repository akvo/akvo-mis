from django.utils import timezone

# from rest_framework.response import Response
# from rest_framework import status
from api.v1.v1_users.models import SystemUser


class UserActivity(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            # get user detail
            if (
                getattr(request, "user", None)
                and request.user.is_authenticated
            ):
                user = SystemUser.objects.filter(pk=request.user.pk).first()
                if user:
                    # update last login here
                    user.last_login = timezone.now()
                    user.save(update_fields=["last_login"])
            return response
        except Exception:
            return response

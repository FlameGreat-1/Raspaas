from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class MultiFieldAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            # Try to find user by username, email, or employee_code
            user = User.objects.get(
                Q(username__iexact=username)
                | Q(email__iexact=username)
                | Q(employee_code__iexact=username)
            )

            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            return None

        return None

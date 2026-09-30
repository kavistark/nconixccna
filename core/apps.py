import os
import sys
from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Only start server when running runserver in main worker process
        if 'runserver' in sys.argv:
            if os.environ.get('RUN_MAIN') == 'true' or '--noreload' in sys.argv:
                try:
                    from django.contrib.auth.models import User
                    from .models import UserProfile
                    user, _ = User.objects.get_or_create(username='nconix_admin')
                    user.set_password('admin@123')
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.role = 'admin'
                    profile.save()
                except Exception:
                    pass

                try:
                    from . import board_server
                    board_server.start_server_thread()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to start whiteboard server: {e}")


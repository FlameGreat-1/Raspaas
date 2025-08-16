from django.core.management.base import BaseCommand
from accounts.models import SystemConfiguration


class Command(BaseCommand):
    help = "List all system configuration keys"

    def handle(self, *args, **options):
        configs = SystemConfiguration.objects.all().values("key", "setting_type")

        self.stdout.write("Current configuration keys and types:")
        self.stdout.write("-" * 50)

        for config in configs:
            self.stdout.write(f"{config['key']} -> {config['setting_type']}")

        self.stdout.write("-" * 50)
        self.stdout.write(f"Total configurations: {len(configs)}")

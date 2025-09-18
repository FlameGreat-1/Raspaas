from django.core.management.base import BaseCommand
import os
from django.conf import settings
import hashlib


class Command(BaseCommand):
    help = "Removes duplicate static files based on content hash"

    def handle(self, *args, **options):
        # Get all static directories
        static_dirs = []

        # Add STATICFILES_DIRS
        for static_dir in settings.STATICFILES_DIRS:
            if os.path.exists(static_dir):
                static_dirs.append(static_dir)

        # Track files by their content hash
        file_hashes = {}
        duplicates = []

        # Find duplicates
        for static_dir in static_dirs:
            for root, dirs, files in os.walk(static_dir):
                for file in files:
                    if "apexcharts" in file:
                        file_path = os.path.join(root, file)
                        with open(file_path, "rb") as f:
                            content = f.read()
                            file_hash = hashlib.md5(content).hexdigest()

                            if file_hash in file_hashes:
                                # This is a duplicate
                                duplicates.append(file_path)
                                self.stdout.write(f"Found duplicate: {file_path}")
                            else:
                                file_hashes[file_hash] = file_path

        # Delete duplicates
        if duplicates:
            self.stdout.write(f"Found {len(duplicates)} duplicates")
            for dup in duplicates:
                os.remove(dup)
                self.stdout.write(f"Deleted: {dup}")
            self.stdout.write(
                self.style.SUCCESS("Successfully removed duplicate files")
            )
        else:
            self.stdout.write("No duplicates found")

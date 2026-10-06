from django.core.management.base import BaseCommand

from listings.backup import create_backup, sqlite_path


class Command(BaseCommand):
    help = "Create a consistent SQLite backup in BACKUP_DIR and prune old ones."

    def add_arguments(self, parser):
        parser.add_argument("--label", default="manual")

    def handle(self, *args, **options):
        source = sqlite_path()
        if source is None or not source.exists():
            self.stdout.write("No SQLite database found yet; backup skipped.")
            return
        target = create_backup(options["label"])
        self.stdout.write(self.style.SUCCESS(f"Backup created: {target}"))

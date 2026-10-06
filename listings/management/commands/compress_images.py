from django.core.management.base import BaseCommand
from django.db.models import Q

from listings.images import optimize_stored
from listings.models import PropertyImage


class Command(BaseCommand):
    help = "Convert stored property images to WebP and create card thumbnails (idempotent)."

    def handle(self, *args, **options):
        pending = PropertyImage.objects.filter(
            ~Q(image__iendswith=".webp") | Q(thumbnail="") | Q(thumbnail__isnull=True)
        )
        changed = 0
        for item in pending.iterator():
            if optimize_stored(item):
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"Optimized {changed} image(s)."))

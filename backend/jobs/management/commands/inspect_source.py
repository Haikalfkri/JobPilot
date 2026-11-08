import json

from django.core.management.base import BaseCommand, CommandError

from jobs.normalization import normalize
from jobs.sources.base import SourceError
from jobs.sources.registry import REGISTRY, get_adapter


class Command(BaseCommand):
    help = "Fetch ONE listing from a source and show its raw fields and how JobPilot reads them (one request)."

    def add_arguments(self, parser):
        parser.add_argument("source_key", choices=sorted(REGISTRY))
        parser.add_argument("--keyword", default=None)

    def handle(self, *args, **options):
        adapter = get_adapter(options["source_key"])
        criteria = {"keywords": [options["keyword"]] if options["keyword"] else []}
        try:
            raw = next(iter(adapter.search(criteria)), None)
        except SourceError as exc:
            raise CommandError(f"{exc.code}: {exc.message}") from exc
        if raw is None:
            self.stdout.write("The source returned no listings.")
            return
        self.stdout.write("Raw fields: " + ", ".join(sorted(raw)))
        fields = dict(normalize(adapter.parse(raw)).job_fields)
        fields["description"] = fields["description"][:120] + "..."
        self.stdout.write(json.dumps(fields, indent=2, default=str))
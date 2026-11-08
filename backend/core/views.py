from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from .services import run_all_checks

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def health(request):
    """200 kalau API hidup dan database terjangkau, 503 kalau tidak."""
    checks = run_all_checks()
    healthy = checks["database"]["status"] == "ok"
    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return Response({"status": overall, "checks": checks}, status=200 if healthy else 503)
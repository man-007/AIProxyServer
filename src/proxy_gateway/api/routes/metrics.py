from fastapi import APIRouter, Response

from proxy_gateway.metrics import metrics_endpoint

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    return metrics_endpoint()

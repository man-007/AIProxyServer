# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from fastapi import APIRouter

from proxy_gateway.api.routes import config, health, messages, metrics, models

"""
API route aggregator for the proxy gateway.

Contributor: @man-007
"""
router = APIRouter()
router.include_router(health.router)
router.include_router(models.router)
router.include_router(messages.router)
router.include_router(metrics.router)
router.include_router(config.router)

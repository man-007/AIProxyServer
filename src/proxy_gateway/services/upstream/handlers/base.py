# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from abc import ABC, abstractmethod

from proxy_gateway.services.upstream.transports.base import UpstreamTransport
from proxy_gateway.diagnostics import get_logger

logger = get_logger("upstream_handler")


"""
UpstreamHandler is the base contract for upstream model handlers.

Contributor: @man-007
"""
class UpstreamHandler(ABC):
    """Base handler for model selection in the upstream chain."""

    def __init__(self, transport: UpstreamTransport):
        logger.debug(
            "UpstreamHandler::__init__ initialized",
            extra={"transport_type": type(transport).__name__},
        )
        self.transport = transport
        self.next_handler: UpstreamHandler | None = None

    def set_next(self, handler: UpstreamHandler) -> UpstreamHandler:
        logger.debug(
            "UpstreamHandler::set_next linked handler",
            extra={"next_handler_type": type(handler).__name__},
        )
        self.next_handler = handler
        return handler

    def handle(self, model: str) -> UpstreamTransport | None:
        logger.debug(
            "UpstreamHandler::handle evaluating model",
            extra={"model": model, "handler_type": self.__class__.__name__},
        )
        if self.can_handle(model):
            logger.debug(
                "UpstreamHandler::handle handler accepted model",
                extra={"model": model, "handler_type": self.__class__.__name__},
            )
            result = self.client()
            logger.debug(
                "UpstreamHandler::handle returning transport",
                extra={"transport_type": type(result).__name__ if result else None},
            )
            return result
        if self.next_handler is not None:
            logger.debug(
                "UpstreamHandler::handle delegating to next handler",
                extra={"model": model, "current_handler": self.__class__.__name__, "next_handler": self.next_handler.__class__.__name__},
            )
            return self.next_handler.handle(model)
        logger.debug(
            "UpstreamHandler::handle no handler accepted model",
            extra={"model": model, "handler_type": self.__class__.__name__},
        )
        return None

    def client(self) -> UpstreamTransport:
        logger.debug(
            "UpstreamHandler::client returning transport",
            extra={"transport_type": type(self.transport).__name__},
        )
        return self.transport

    @abstractmethod
    def can_handle(self, model: str) -> bool:
        """Return whether this handler owns the model."""
"""Handlers package - all Telegram UI handlers."""

from bot.handlers.add_target import add_target_router, AddTargetStates
from bot.handlers.auth import auth_router, AuthStates
from bot.handlers.available import available_router
from bot.handlers.list_targets import list_targets_router
from bot.handlers.menu import menu_router
from bot.handlers.remove_target import remove_target_router

__all__ = [
    "menu_router",
    "add_target_router",
    "AddTargetStates",
    "remove_target_router",
    "list_targets_router",
    "auth_router",
    "AuthStates",
    "available_router",
]

"""Database package — v3.0."""

from bot.db.models import (
    init_db,
    add_target,
    remove_target,
    get_targets,
    count_targets,
    get_all_chat_ids,
    is_item_sent,
    mark_item_sent,
    get_tt_post_index,
    update_tt_post_index,
    is_in_cooldown,
    get_error_count,
    set_error_cooldown,
    clear_error_cooldown,
)

__all__ = [
    "init_db",
    "add_target",
    "remove_target",
    "get_targets",
    "count_targets",
    "get_all_chat_ids",
    "is_item_sent",
    "mark_item_sent",
    "get_tt_post_index",
    "update_tt_post_index",
    "is_in_cooldown",
    "get_error_count",
    "set_error_cooldown",
    "clear_error_cooldown",
]
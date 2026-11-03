from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from app.config import settings


class IsAdminFilter(BaseFilter):
    """Enforces administrator role verification on commands and callbacks."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        if not user:
            return False
        return user.id in settings.admin_ids

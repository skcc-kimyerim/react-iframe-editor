from contextvars import ContextVar
from typing import Optional

user_info_ctx: ContextVar[Optional[object]] = ContextVar(
    "user_info", default=None
)  # UserInfo -> object로 임시 변경
transaction_id_ctx: ContextVar[str] = ContextVar("transaction_id", default="")


def get_current_user_info() -> object:  # UserInfo -> object로 임시 변경
    if user_info_ctx.get() is None:
        return object()  # UserInfo(user_id="") -> object()로 임시 변경
    else:
        return user_info_ctx.get()


def get_transaction_id() -> str:
    return transaction_id_ctx.get()

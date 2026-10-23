import functools
import inspect
from typing import Any, Callable

from valutatrade_hub.logging_config import setup_logging


def log_action(action: str, verbose: bool = False) -> Callable:
    def decorator(func: Callable) -> Callable:
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = setup_logging(verbose=verbose)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments

            username = _extract_username(arguments)
            currency_code = arguments.get("currency_code")
            amount = arguments.get("amount")

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _write_log(
                    logger,
                    action=action,
                    username=username,
                    currency_code=currency_code,
                    amount=amount,
                    rate=None,
                    base=None,
                    result="ERROR",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                raise

            message, log_extra = _unpack_result(result)
            _write_log(
                logger,
                action=action,
                username=username,
                currency_code=currency_code,
                amount=amount,
                rate=log_extra.get("rate"),
                base=log_extra.get("base"),
                result="OK",
                verbose_context=log_extra if verbose else None,
            )
            return message

        return wrapper

    return decorator


def _extract_username(arguments: dict) -> str | None:
    if "username" in arguments:
        return arguments["username"]
    session = arguments.get("session")
    if session is not None and getattr(session, "current_user", None) is not None:
        return session.current_user.username
    return None


def _unpack_result(result: Any) -> tuple[Any, dict]:
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result
    return result, {}


def _write_log(
    logger: Any,
    *,
    action: str,
    username: str | None,
    currency_code: str | None,
    amount: float | None,
    rate: float | None,
    base: str | None,
    result: str,
    error_type: str | None = None,
    error_message: str | None = None,
    verbose_context: dict | None = None,
) -> None:
    parts = [action, f"user='{username}'"]

    if currency_code is not None:
        parts.append(f"currency='{currency_code}'")
    if amount is not None:
        parts.append(f"amount={amount:.4f}")
    if rate is not None:
        parts.append(f"rate={rate:.2f}")
    if base is not None:
        parts.append(f"base='{base}'")

    parts.append(f"result={result}")

    if error_type is not None:
        parts.append(f"error_type='{error_type}'")
    if error_message is not None:
        parts.append(f"error_message='{error_message}'")

    if verbose_context:
        extra_items = {
            key: value
            for key, value in verbose_context.items()
            if key not in ("rate", "base")
        }
        for key, value in extra_items.items():
            parts.append(f"{key}={value}")

    logger.info(" ".join(parts))
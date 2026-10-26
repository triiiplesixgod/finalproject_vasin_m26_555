from datetime import datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.config import ParserConfig


class AuthSession:
    """Хранит состояние текущей авторизации в рамках запуска CLI."""

    def __init__(self) -> None:
        self._current_user: User | None = None

    @property
    def current_user(self) -> User | None:
        return self._current_user

    @property
    def is_authenticated(self) -> bool:
        return self._current_user is not None

    def login(self, user: User) -> None:
        self._current_user = user

    def logout(self) -> None:
        self._current_user = None

    def require_login(self) -> User:
        """Возвращает текущего пользователя или выбрасывает ошибку, если он не вошёл."""
        if self._current_user is None:
            raise PermissionError("Сначала выполните login")
        return self._current_user


def load_users() -> list[User]:
    raw_users = DatabaseManager().load_users()
    return [User.from_dict(item) for item in raw_users]


def save_users(users: list[User]) -> None:
    DatabaseManager().save_users([user.to_dict() for user in users])


def find_user_by_username(users: list[User], username: str) -> User | None:
    for user in users:
        if user.username == username:
            return user
    return None


def load_portfolios() -> list[Portfolio]:
    raw_portfolios = DatabaseManager().load_portfolios()
    return [Portfolio.from_dict(item) for item in raw_portfolios]


def save_portfolios(portfolios: list[Portfolio]) -> None:
    DatabaseManager().save_portfolios([portfolio.to_dict() for portfolio in portfolios])


def find_portfolio_by_user_id(
    portfolios: list[Portfolio], user_id: int
) -> Portfolio | None:
    for portfolio in portfolios:
        if portfolio.user == user_id:
            return portfolio
    return None


# Команда register


@log_action("REGISTER")
def register_user(username: str, password: str) -> str:
    """Регистрирует нового пользователя и создаёт для него пустой портфель."""
    users = load_users()

    if find_user_by_username(users, username) is not None:
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    next_id = max((user.user_id for user in users), default=0) + 1

    new_user = User.create_new(user_id=next_id, username=username, password=password)
    users.append(new_user)
    save_users(users)

    portfolios = load_portfolios()
    portfolios.append(Portfolio(user_id=new_user.user_id))
    save_portfolios(portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован (id={new_user.user_id}). "
        f"Войдите: login --username {username} --password ****"
    )


# Команда login


@log_action("LOGIN")
def login_user(session: AuthSession, username: str, password: str) -> str:
    """Выполняет вход пользователя и фиксирует его в сессии."""
    users = load_users()
    user = find_user_by_username(users, username)

    if user is None:
        raise LookupError(f"Пользователь '{username}' не найден")

    if not user.verify_password(password):
        raise ValueError("Неверный пароль")

    session.login(user)
    return f"Вы вошли как '{username}'"


# Курсы валют


def _get_usd_quote(pairs: dict, code: str) -> dict | None:
    """Возвращает сырую котировку CODE_USD из снимка Parser Service"""
    if code == "USD":
        return {"rate": 1.0, "updated_at": None, "source": None}
    return pairs.get(f"{code}_USD")


def _usd_price(code: str, quote: dict, config: ParserConfig) -> float:
    """Приводит сохранённую котировку к единому базису "USD за 1 CODE"."""
    if code == "USD":
        return 1.0
    if code in config.CRYPTO_CURRENCIES:
        return quote["rate"]
    if code in config.FIAT_CURRENCIES:
        return 1.0 / quote["rate"]
    raise ApiRequestError(
        reason=f"неизвестна конвенция хранения курса для валюты '{code}'"
    )


def _compute_fallback_rate(
    from_currency: str, to_currency: str
) -> tuple[float, str | None, str]:
    """Строит курс from_currency->to_currency по снимку Parser Service"""
    config = ParserConfig()
    storage = RatesStorage()
    snapshot = storage.load_rates_snapshot()
    pairs = snapshot["pairs"]

    from_quote = _get_usd_quote(pairs, from_currency)
    to_quote = _get_usd_quote(pairs, to_currency)

    if from_quote is None or to_quote is None:
        missing = from_currency if from_quote is None else to_currency
        raise ApiRequestError(
            reason=(
                f"нет данных о курсе для '{missing}' в кэше Parser Service "
                "(data/rates.json). Выполните команду update-rates"
            )
        )

    from_usd = _usd_price(from_currency, from_quote, config)
    to_usd = _usd_price(to_currency, to_quote, config)
    rate = from_usd / to_usd

    timestamps = [
        q["updated_at"] for q in (from_quote, to_quote) if q["updated_at"] is not None
    ]
    updated_at = min(timestamps) if timestamps else None

    sources = {
        q["source"] for q in (from_quote, to_quote) if q.get("source") is not None
    }
    source = ", ".join(sorted(sources)) if sources else "ParserService"

    return rate, updated_at, source


def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    from_currency = utils.validate_currency_code(from_currency)
    to_currency = utils.validate_currency_code(to_currency)

    get_currency(from_currency)
    get_currency(to_currency)

    if from_currency == to_currency:
        return 1.0, datetime.now()

    rate, updated_at_raw, _source = _compute_fallback_rate(from_currency, to_currency)

    if updated_at_raw is not None:
        updated_at = datetime.strptime(updated_at_raw, "%Y-%m-%dT%H:%M:%SZ")
    else:
        updated_at = datetime.now()

    return rate, updated_at

def _format_rate(value: float) -> str:
    if value >= 1:
        return f"{value:.2f}"
    return f"{value:.8f}"


def get_rate_command(from_currency: str, to_currency: str) -> str:
    from_currency = utils.validate_currency_code(from_currency)
    to_currency = utils.validate_currency_code(to_currency)

    rate, updated_at = get_exchange_rate(from_currency, to_currency)
    reverse_rate, _ = get_exchange_rate(to_currency, from_currency)

    timestamp = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"Курс {from_currency}->{to_currency}: {_format_rate(rate)} "
        f"(обновлено: {timestamp})\n"
        f"Обратный курс {to_currency}->{from_currency}: {_format_rate(reverse_rate)}"
    )


# Команда show-portfolio


def show_portfolio(session: AuthSession, base_currency: str = "USD") -> str:
    user = session.require_login()
    base_currency = utils.validate_currency_code(base_currency)
    get_currency(base_currency)

    portfolios = load_portfolios()
    portfolio = find_portfolio_by_user_id(portfolios, user.user_id)

    if portfolio is None or not portfolio.wallets:
        return f"У пользователя '{user.username}' пока нет кошельков."

    lines = [f"Портфель пользователя '{user.username}' (база: {base_currency}):"]
    for code, wallet in sorted(portfolio.wallets.items()):
        rate_to_base = (
            Portfolio.exchange_rates[code] / Portfolio.exchange_rates[base_currency]
        )
        value_in_base = wallet.balance * rate_to_base
        lines.append(
            f"- {code}: {wallet.balance:.4f}  -> {value_in_base:.2f} {base_currency}"
        )

    total = portfolio.get_total_value(base_currency)
    lines.append("-" * 35)
    lines.append(f"ИТОГО: {total:,.2f} {base_currency}")

    return "\n".join(lines)


# Команда buy


@log_action("BUY")
def buy_currency(
    session: AuthSession, currency_code: str, amount: float
) -> tuple[str, dict]:
    """Покупает валюту currency_code за USD."""
    user = session.require_login()
    currency_code = utils.validate_currency_code(currency_code)
    amount = utils.validate_amount(amount)

    if currency_code == "USD":
        raise ValueError("Нельзя купить USD за USD")

    get_currency(currency_code)

    portfolios = load_portfolios()
    portfolio = find_portfolio_by_user_id(portfolios, user.user_id)
    if portfolio is None:
        portfolio = Portfolio(user_id=user.user_id)
        portfolios.append(portfolio)

    rate, _ = get_exchange_rate(currency_code, "USD")
    cost = amount * rate

    try:
        usd_wallet = portfolio.get_wallet("USD")
    except LookupError:
        usd_wallet = portfolio.add_currency("USD")

    # withdraw бросит InsufficientFundsError, если средств не хватает
    usd_wallet.withdraw(cost)

    try:
        target_wallet = portfolio.get_wallet(currency_code)
    except LookupError:
        target_wallet = portfolio.add_currency(currency_code)

    old_balance = target_wallet.balance
    target_wallet.deposit(amount)

    save_portfolios(portfolios)

    message = (
        f"Покупка выполнена: {amount:.4f} {currency_code} по курсу "
        f"{rate:.2f} USD/{currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {old_balance:.4f} "
        f"-> стало {target_wallet.balance:.4f}\n"
        f"- USD: списано {cost:,.2f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} USD"
    )
    log_extra = {
        "rate": rate,
        "base": "USD",
        "old_balance": old_balance,
        "new_balance": target_wallet.balance,
    }
    return message, log_extra


# Команда sell


@log_action("SELL")
def sell_currency(
    session: AuthSession, currency_code: str, amount: float
) -> tuple[str, dict]:
    """Продаёт валюту currency_code за USD."""
    user = session.require_login()
    currency_code = utils.validate_currency_code(currency_code)
    amount = utils.validate_amount(amount)

    if currency_code == "USD":
        raise ValueError("Нельзя продать USD за USD")

    get_currency(currency_code)

    portfolios = load_portfolios()
    portfolio = find_portfolio_by_user_id(portfolios, user.user_id)

    not_found_message = (
        f"У вас нет кошелька '{currency_code}'. Добавьте валюту: она создаётся "
        "автоматически при первой покупке."
    )
    if portfolio is None:
        raise LookupError(not_found_message)

    try:
        wallet = portfolio.get_wallet(currency_code)
    except LookupError as e:
        raise LookupError(not_found_message) from e

    rate, _ = get_exchange_rate(currency_code, "USD")

    old_balance = wallet.balance
    # withdraw бросит InsufficientFundsError, если средств недостаточно
    wallet.withdraw(amount)

    revenue = amount * rate
    try:
        usd_wallet = portfolio.get_wallet("USD")
    except LookupError:
        usd_wallet = portfolio.add_currency("USD")
    usd_wallet.deposit(revenue)

    save_portfolios(portfolios)

    message = (
        f"Продажа выполнена: {amount:.4f} {currency_code} по курсу "
        f"{rate:.2f} USD/{currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {old_balance:.4f} -> стало {wallet.balance:.4f}\n"
        f"- USD: зачислено {revenue:,.2f}\n"
        f"Оценочная выручка: {revenue:,.2f} USD"
    )
    log_extra = {
        "rate": rate,
        "base": "USD",
        "old_balance": old_balance,
        "new_balance": wallet.balance,
    }
    return message, log_extra

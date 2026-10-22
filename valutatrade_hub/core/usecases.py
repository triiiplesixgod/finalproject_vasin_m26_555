from datetime import datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.models import Portfolio, User


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
    raw_users = utils.load_json(utils.USERS_FILE, default=[])
    return [User.from_dict(item) for item in raw_users]


def save_users(users: list[User]) -> None:
    utils.save_json(utils.USERS_FILE, [user.to_dict() for user in users])


def find_user_by_username(users: list[User], username: str) -> User | None:
    for user in users:
        if user.username == username:
            return user
    return None



def load_portfolios() -> list[Portfolio]:
    raw_portfolios = utils.load_json(utils.PORTFOLIOS_FILE, default=[])
    return [Portfolio.from_dict(item) for item in raw_portfolios]


def save_portfolios(portfolios: list[Portfolio]) -> None:
    utils.save_json(
        utils.PORTFOLIOS_FILE, [portfolio.to_dict() for portfolio in portfolios]
    )


def find_portfolio_by_user_id(
    portfolios: list[Portfolio], user_id: int
) -> Portfolio | None:
    for portfolio in portfolios:
        if portfolio.user == user_id:
            return portfolio
    return None


#Команда register 

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


#Команда login


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



#Курсы валют

def _compute_fallback_rate(from_currency: str, to_currency: str) -> float:
    """Вычисляет курс через фиксированные курсы к USD."""
    rates_to_usd = Portfolio.exchange_rates
    if from_currency not in rates_to_usd or to_currency not in rates_to_usd:
        raise LookupError(f"Не удалось получить курс для {from_currency}->{to_currency}")
    return rates_to_usd[from_currency] / rates_to_usd[to_currency]


def get_exchange_rate(from_currency: str, to_currency: str) -> tuple[float, datetime]:
    """Возвращает курс валютной пары и время последнего обновления."""
    from_currency = utils.validate_currency_code(from_currency)
    to_currency = utils.validate_currency_code(to_currency)

    if from_currency == to_currency:
        return 1.0, datetime.now()

    rates_data = utils.load_json(utils.RATES_FILE, default={})
    pair_key = f"{from_currency}_{to_currency}"

    cached = rates_data.get(pair_key)
    if cached is not None and utils.is_rate_fresh(cached["updated_at"]):
        return cached["rate"], datetime.fromisoformat(cached["updated_at"])

    rate = _compute_fallback_rate(from_currency, to_currency)
    now = datetime.now()

    rates_data[pair_key] = {"rate": rate, "updated_at": now.isoformat()}
    rates_data["source"] = "ParserService"
    rates_data["last_refresh"] = now.isoformat()
    utils.save_json(utils.RATES_FILE, rates_data)

    return rate, now


def _format_rate(value: float) -> str:
    """Форматирует курс: крупные числа - с двумя знаками, мелкие - с восемью."""
    if value >= 1:
        return f"{value:.2f}"
    return f"{value:.8f}"


def get_rate_command(from_currency: str, to_currency: str) -> str:
    from_currency = utils.validate_currency_code(from_currency)
    to_currency = utils.validate_currency_code(to_currency)

    try:
        rate, updated_at = get_exchange_rate(from_currency, to_currency)
        reverse_rate, _ = get_exchange_rate(to_currency, from_currency)
    except LookupError as e:
        raise LookupError(
            f"Курс {from_currency}->{to_currency} недоступен. Повторите попытку позже."
        ) from e

    timestamp = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"Курс {from_currency}->{to_currency}: {_format_rate(rate)} "
        f"(обновлено: {timestamp})\n"
        f"Обратный курс {to_currency}->{from_currency}: {_format_rate(reverse_rate)}"
    )



#Команда show-portfolio

def show_portfolio(session: AuthSession, base_currency: str = "USD") -> str:
    user = session.require_login()
    base_currency = utils.validate_currency_code(base_currency)

    if base_currency not in Portfolio.exchange_rates:
        raise ValueError(f"Неизвестная базовая валюта '{base_currency}'")

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
        lines.append(f"- {code}: {wallet.balance:.4f}  -> {value_in_base:.2f} {base_currency}")

    total = portfolio.get_total_value(base_currency)
    lines.append("-" * 35)
    lines.append(f"ИТОГО: {total:,.2f} {base_currency}")

    return "\n".join(lines)



#Команда buy

def buy_currency(session: AuthSession, currency_code: str, amount: float) -> str:
    """Покупает валюту currency_code за USD."""
    user = session.require_login()
    currency_code = utils.validate_currency_code(currency_code)
    amount = utils.validate_amount(amount)

    if currency_code == "USD":
        raise ValueError("Нельзя купить USD за USD")

    portfolios = load_portfolios()
    portfolio = find_portfolio_by_user_id(portfolios, user.user_id)
    if portfolio is None:
        portfolio = Portfolio(user_id=user.user_id)
        portfolios.append(portfolio)

    try:
        rate, _ = get_exchange_rate(currency_code, "USD")
    except LookupError as e:
        raise LookupError(f"Не удалось получить курс для {currency_code}->USD") from e

    cost = amount * rate

    try:
        usd_wallet = portfolio.get_wallet("USD")
    except KeyError:
        usd_wallet = portfolio.add_currency("USD")

    usd_wallet.withdraw(cost)  # выбросит ValueError, если средств не хватает

    try:
        target_wallet = portfolio.get_wallet(currency_code)
    except KeyError:
        target_wallet = portfolio.add_currency(currency_code)

    old_balance = target_wallet.balance
    target_wallet.deposit(amount)

    save_portfolios(portfolios)

    return (
        f"Покупка выполнена: {amount:.4f} {currency_code} по курсу "
        f"{rate:.2f} USD/{currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {old_balance:.4f} -> стало {target_wallet.balance:.4f}\n"
        f"- USD: списано {cost:,.2f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} USD"
    )



#Команда sell

def sell_currency(session: AuthSession, currency_code: str, amount: float) -> str:
    """Продаёт валюту currency_code за USD."""
    user = session.require_login()
    currency_code = utils.validate_currency_code(currency_code)
    amount = utils.validate_amount(amount)

    if currency_code == "USD":
        raise ValueError("Нельзя продать USD за USD")

    portfolios = load_portfolios()
    portfolio = find_portfolio_by_user_id(portfolios, user.user_id)

    not_found_message = (
        f"У вас нет кошелька '{currency_code}'. Добавьте валюту: она создаётся "
        "автоматически при первой покупке."
    )
    if portfolio is None:
        raise KeyError(not_found_message)

    try:
        wallet = portfolio.get_wallet(currency_code)
    except KeyError as e:
        raise KeyError(not_found_message) from e

    try:
        rate, _ = get_exchange_rate(currency_code, "USD")
    except LookupError as e:
        raise LookupError(f"Не удалось получить курс для {currency_code}->USD") from e

    old_balance = wallet.balance
    wallet.withdraw(amount)  # выбросит ValueError, если средств недостаточно

    revenue = amount * rate
    try:
        usd_wallet = portfolio.get_wallet("USD")
    except KeyError:
        usd_wallet = portfolio.add_currency("USD")
    usd_wallet.deposit(revenue)

    save_portfolios(portfolios)

    return (
        f"Продажа выполнена: {amount:.4f} {currency_code} по курсу "
        f"{rate:.2f} USD/{currency_code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {old_balance:.4f} -> стало {wallet.balance:.4f}\n"
        f"- USD: зачислено {revenue:,.2f}\n"
        f"Оценочная выручка: {revenue:,.2f} USD"
    )
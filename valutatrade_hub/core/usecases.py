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
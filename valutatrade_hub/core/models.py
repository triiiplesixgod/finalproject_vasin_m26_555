import hashlib
import secrets
from datetime import datetime


class User:
    """Пользователь системы."""

    MIN_PASSWORD_LENGTH = 4

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime | None = None,
    ) -> None:
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date or datetime.now()

    @classmethod
    def create_new(cls, user_id: int, username: str, password: str) -> "User":
        """Создаёт нового пользователя из обычного (нехешированного) пароля."""
        cls._validate_password(password)
        salt = cls._generate_salt()
        hashed_password = cls._hash_password(password, salt)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hashed_password,
            salt=salt,
            registration_date=datetime.now(),
        )

  
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    @staticmethod
    def _generate_salt() -> str:
        """Генерирует случайную соль для хеширования пароля."""
        return secrets.token_hex(8)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Псевдо-хеш пароля: sha256(password + salt)."""
        raw = (password + salt).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < User.MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Пароль должен быть не короче {User.MIN_PASSWORD_LENGTH} символов"
            )


    def get_user_info(self) -> str:
        """Выводит информацию о пользователе (без пароля)."""
        info = (
            f"ID: {self._user_id}\n"
            f"Имя пользователя: {self._username}\n"
            f"Дата регистрации: {self._registration_date.isoformat()}"
        )
        print(info)
        return info

    def change_password(self, new_password: str) -> None:
        """Меняет пароль пользователя, генерируя новую соль и хеш."""
        self._validate_password(new_password)
        self._salt = self._generate_salt()
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли введённый пароль с сохранённым хешем."""
        return self._hash_password(password, self._salt) == self._hashed_password


    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = self._validate_currency_code(currency_code)
        self._balance = 0.0
        self.balance = balance  


    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)


    @staticmethod
    def _validate_currency_code(currency_code: str) -> str:
        if not currency_code or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        return currency_code.upper()

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError("'amount' должен быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")


    def deposit(self, amount: float) -> None:
        """Пополняет баланс на указанную сумму."""
        self._validate_amount(amount)
        self.balance = self._balance + amount

    def withdraw(self, amount: float) -> None:
        """Снимает указанную сумму с баланса, если средств достаточно."""
        self._validate_amount(amount)
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} {self.currency_code}"
            )
        self.balance = self._balance - amount

    def get_balance_info(self) -> str:
        """Выводит информацию о текущем балансе."""
        info = f"{self.currency_code}: {self._balance:.4f}"
        print(info)
        return info


    def to_dict(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"],
        )
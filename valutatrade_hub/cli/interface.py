import shlex

from valutatrade_hub.core.currencies import list_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import (
    AuthSession,
    buy_currency,
    get_exchange_rate,
    get_rate_command,
    list_rates,
    login_user,
    register_user,
    sell_currency,
    show_portfolio,
)
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

WELCOME_MESSAGE = (
    "ValutaTrade Hub — симулятор валютной торговли.\n"
    "Доступные команды: register, login, logout, show-portfolio, "
    "buy, sell, get-rate, update-rates, show-rates, help, exit\n"
)

SOURCE_MAP = {
    "coingecko": CoinGeckoClient,
    "exchangerate": ExchangeRateApiClient,
}


def parse_command(raw_input: str) -> tuple[str, dict[str, str]]:
    tokens = shlex.split(raw_input)
    if not tokens:
        return "", {}

    command = tokens[0]
    args: dict[str, str] = {}

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                args[key] = tokens[i + 1]
                i += 2
            else:
                raise ValueError(f"Отсутствует значение для аргумента '--{key}'")
        else:
            raise ValueError(f"Неожиданный аргумент: '{token}'")
        continue

    return command, args


def require_args(args: dict[str, str], *names: str) -> None:
    missing = [name for name in names if name not in args]
    if missing:
        missing_formatted = ", ".join(f"--{m}" for m in missing)
        raise ValueError(f"Отсутствуют обязательные аргументы: {missing_formatted}")


class CommandLineInterface:
    """Обрабатывает пользовательский ввод и вызывает соответствующие usecases."""

    def __init__(self) -> None:
        self.session = AuthSession()
        self.handlers = {
            "register": self.handle_register,
            "login": self.handle_login,
            "logout": self.handle_logout,
            "show-portfolio": self.handle_show_portfolio,
            "buy": self.handle_buy,
            "sell": self.handle_sell,
            "get-rate": self.handle_get_rate,
            "update-rates": self.handle_update_rates,
            "show-rates": self.handle_show_rates,
            "help": self.handle_help,
        }

    def handle_register(self, args: dict[str, str]) -> str:
        require_args(args, "username", "password")
        return register_user(args["username"], args["password"])

    def handle_login(self, args: dict[str, str]) -> str:
        require_args(args, "username", "password")
        return login_user(self.session, args["username"], args["password"])

    def handle_logout(self, args: dict[str, str]) -> str:
        self.session.logout()
        return "Вы вышли из системы"

    def handle_show_portfolio(self, args: dict[str, str]) -> str:
        base = args.get("base", "USD")
        return show_portfolio(self.session, base_currency=base)

    def handle_buy(self, args: dict[str, str]) -> str:
        require_args(args, "currency", "amount")
        amount = self._parse_float(args["amount"])
        return buy_currency(self.session, args["currency"], amount)

    def handle_sell(self, args: dict[str, str]) -> str:
        require_args(args, "currency", "amount")
        amount = self._parse_float(args["amount"])
        return sell_currency(self.session, args["currency"], amount)

    def handle_get_rate(self, args: dict[str, str]) -> str:
        require_args(args, "from", "to")
        return get_rate_command(args["from"], args["to"])

    def handle_update_rates(self, args: dict[str, str]) -> str:
        clients = self._build_clients(args.get("source"))
        updater = RatesUpdater(clients=clients, storage=RatesStorage())
        summary = updater.run_update()
        return self._format_update_summary(summary)

    def handle_show_rates(self, args: dict[str, str]) -> str:
        base = args.get("base", "USD")

        currency = args.get("currency")
        if currency is not None:
            rate, updated_at = get_exchange_rate(currency, base)
            timestamp = updated_at.strftime("%Y-%m-%d %H:%M:%S")
            return (
                f"{currency.upper()} -> {base.upper()}: "
                f"{self._format_rate_value(rate)} (обновлено: {timestamp})"
            )

        rates = list_rates(base)
        if not rates:
            return (
                "Кэш курсов пуст. Выполните команду 'update-rates', чтобы "
                "получить актуальные данные."
            )

        rates.sort(key=lambda item: item["rate"], reverse=True)

        top_raw = args.get("top")
        if top_raw is not None:
            top_n = self._parse_int(top_raw)
            rates = rates[:top_n]

        lines = [f"Курсы валют (база: {base.upper()}):"]
        for item in rates:
            timestamp = item["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                f"- {item['currency']}: {self._format_rate_value(item['rate'])} "
                f"(обновлено: {timestamp})"
            )
        return "\n".join(lines)

    def handle_help(self, args: dict[str, str]) -> str:
        return WELCOME_MESSAGE

    @staticmethod
    def _build_clients(source: str | None) -> list:
        if source is None:
            return [CoinGeckoClient(), ExchangeRateApiClient()]

        client_cls = SOURCE_MAP.get(source.lower())
        if client_cls is None:
            valid = ", ".join(sorted(SOURCE_MAP))
            raise ValueError(
                f"Неизвестный источник '{source}'. Допустимые значения: {valid}"
            )
        return [client_cls()]

    @staticmethod
    def _format_update_summary(summary: dict) -> str:
        updated = summary["updated_pairs"]
        added = summary["new_history_records"]
        succeeded = summary["succeeded_sources"]
        failed = summary["failed_sources"]

        if updated == 0:
            failed_text = ", ".join(failed) if failed else "нет"
            return (
                "Не удалось обновить курсы: ни один источник не ответил "
                f"успешно. Недоступные источники: {failed_text}"
            )

        lines = [
            f"Курсы обновлены: {updated} пар(ы) в кэше, "
            f"{added} новых записей в истории.",
            f"Успешные источники: {', '.join(succeeded) if succeeded else 'нет'}.",
        ]
        if failed:
            lines.append(f"Недоступные источники: {', '.join(failed)}.")
        return "\n".join(lines)

    @staticmethod
    def _format_rate_value(value: float) -> str:
        """Форматирует курс: крупные числа - с двумя знаками, мелкие - с восемью."""
        if value >= 1:
            return f"{value:.2f}"
        return f"{value:.8f}"

    @staticmethod
    def _parse_float(value: str) -> float:
        try:
            return float(value)
        except ValueError as e:
            raise ValueError(f"'{value}' не является корректным числом") from e

    @staticmethod
    def _parse_int(value: str) -> int:
        try:
            return int(value)
        except ValueError as e:
            raise ValueError(f"'{value}' не является корректным целым числом") from e

    def run(self) -> None:
        print(WELCOME_MESSAGE)
        while True:
            try:
                raw_input_str = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nВыход из приложения.")
                break

            if not raw_input_str:
                continue

            if raw_input_str in ("exit", "quit"):
                print("Выход из приложения.")
                break

            try:
                command, args = parse_command(raw_input_str)
                handler = self.handlers.get(command)
                if handler is None:
                    print(
                        f"Неизвестная команда: '{command}'. Введите 'help' для справки."
                    )
                    continue
                result = handler(args)
                print(result)
            except InsufficientFundsError as e:
                print(f"Ошибка: {e}")
            except CurrencyNotFoundError as e:
                supported = ", ".join(list_supported_codes())
                print(
                    f"Ошибка: {e}\n"
                    "Подсказка: посмотрите пример использования — "
                    "'help' (раздел get-rate), либо список поддерживаемых "
                    f"кодов валют: {supported}"
                )
            except ApiRequestError as e:
                print(
                    f"Ошибка: {e}\n"
                    "Попробуйте повторить запрос позже или проверьте "
                    "подключение к сети."
                )
            except (
                ValueError,
                KeyError,
                LookupError,
                PermissionError,
                TypeError,
            ) as e:
                print(f"Ошибка: {e}")


def main() -> None:
    """Точка входа для запуска CLI."""
    cli = CommandLineInterface()
    cli.run()


if __name__ == "__main__":
    main()

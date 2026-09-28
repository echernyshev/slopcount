import pytest

from slopcount import i18n


@pytest.fixture(autouse=True)
def _english_by_default():
    """Переводы дошли до детекторов и каталогов правил, поэтому глобальное
    состояние i18n должно быть детерминированным: тест не наследует --lang
    от предыдущего (напр. test_i18n оставляет ru активным)."""
    i18n.setup("en")
    yield


@pytest.fixture(scope="session")
def scc_ready():
    """e2e-тесты гоняют настоящий конвейер → нужен бинарник scc.
    Ленивая установка (при сети) — часть проверяемого поведения; оффлайн — skip."""
    from slopcount import scc as scc_mod

    try:
        scc_mod.ensure_binary()
        return True
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")

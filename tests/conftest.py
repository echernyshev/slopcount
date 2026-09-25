import pytest

from slopcount import i18n


@pytest.fixture(autouse=True)
def _english_by_default():
    """Переводы дошли до детекторов и каталогов правил, поэтому глобальное
    состояние i18n должно быть детерминированным: тест не наследует --lang
    от предыдущего (напр. test_i18n оставляет ru активным)."""
    i18n.setup("en")
    yield

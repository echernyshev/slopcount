import re

# Общий эмодзи-класс для детекторов (docs_bloat: заголовки, code_style: комментарии)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-⟿⬀-⯿]")

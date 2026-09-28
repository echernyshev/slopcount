"""Разовая загрузка локальной копии gpt2 (~500 МБ) для --perplexity.

Запуск: python -m slopcount.download_model
"""

MODEL_NAME = "gpt2"


def main() -> None:
    print(f"Downloading {MODEL_NAME} (~500 MB) for --perplexity ...")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    AutoTokenizer.from_pretrained(MODEL_NAME)
    AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    print("Done. Re-run slopcount with --perplexity.")


if __name__ == "__main__":
    main()

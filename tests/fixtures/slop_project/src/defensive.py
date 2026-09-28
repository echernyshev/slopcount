def load(path):
    """Loads the file.

    Args:
        path: the path

    Returns:
        data
    """
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return None

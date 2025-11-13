def register_handlers():
    # импорт самих модулей достаточно, чтобы декораторы отработали
    from . import start  # noqa: F401
    from . import wallets  # noqa: F401
    from . import state  # noqa: F401

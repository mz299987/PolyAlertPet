from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def language_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru")],
        ]
    )


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ru":
        keyboard = [
            [
                KeyboardButton(text="➕ Мой кошелёк"),
                KeyboardButton(text="➕ Кит"),
            ],
            [
                KeyboardButton(text="📊 Мои кошельки"),
                KeyboardButton(text="📈 Состояние"),
            ],
            [KeyboardButton(text="⬅ Назад")],
        ]
    else:
        keyboard = [
            [
                KeyboardButton(text="➕ My wallet"),
                KeyboardButton(text="➕ Whale"),
            ],
            [
                KeyboardButton(text="📊 My wallets"),
                KeyboardButton(text="📈 Status"),
            ],
            [KeyboardButton(text="⬅ Back")],
        ]
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)


def get_main_text(lang: str) -> str:
    if lang == "ru":
        return (
            "Привет! Я трекаю твой Polymarket профиль 🧠\n\n"
            "Что я умею:\n"
            "• слать алерты при движении позиций на ±5%\n"
            "• отслеживать китов и их новые сделки\n"
            "• показывать текущее состояние кошелька/китов\n\n"
            "Кнопки внизу:\n"
            "• «➕ Мой кошелёк» — добавить свой профиль Polymarket\n"
            "• «➕ Кит» — добавить кошелёк кита\n"
            "• «📊 Мои кошельки» — список всех\n"
            "• «📈 Состояние» — подробное состояние кошельков\n"
        )
    else:
        return (
            "Hi! I track your Polymarket profile 🧠\n\n"
            "What I can do:\n"
            "• send alerts when your positions move ±5%\n"
            "• track whales and their new trades\n"
            "• show current status of your wallets\n\n"
            "Buttons below:\n"
            "• “➕ My wallet” — add your Polymarket profile\n"
            "• “➕ Whale” — add whale wallet\n"
            "• “📊 My wallets” — list of wallets\n"
            "• “📈 Status” — detailed status of wallets\n"
        )

from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)


class Keyboards:
    """Класс для создания клавиатур"""
    
    @staticmethod
    def get_main_menu(language: str = "ru") -> ReplyKeyboardMarkup:
        """Главное меню"""
        if language == "ru":
            buttons = [
                [KeyboardButton(text="➕ Мой кошелёк"), KeyboardButton(text="➕ Кит")],
                [KeyboardButton(text="📊 Мои кошельки"), KeyboardButton(text="📈 Состояние")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="➕ My Wallet"), KeyboardButton(text="➕ Whale")],
                [KeyboardButton(text="📊 My Wallets"), KeyboardButton(text="📈 Status")]
            ]
        
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Выберите действие" if language == "ru" else "Choose action"
        )
    
    @staticmethod
    def get_language_selection() -> InlineKeyboardMarkup:
        """Выбор языка"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
            ]
        ])
    
    @staticmethod
    def get_wallet_selection(wallets: list, current_index: int, language: str = "ru") -> InlineKeyboardMarkup:
        """Клавиатура для выбора кошельков"""
        total_wallets = len(wallets)
        
        buttons = []
        
        # Кнопки навигации
        if total_wallets > 1:
            prev_index = (current_index - 1) % total_wallets
            next_index = (current_index + 1) % total_wallets
            
            buttons.append([
                InlineKeyboardButton(text="◀", callback_data=f"wallet_{prev_index}"),
                InlineKeyboardButton(text=f"{current_index + 1}/{total_wallets}", callback_data="page_info"),
                InlineKeyboardButton(text="▶", callback_data=f"wallet_{next_index}")
            ])
        
        # Кнопка выбора кошелька
        change_text = "📋 Сменить кошелек" if language == "ru" else "📋 Change Wallet"
        buttons.append([InlineKeyboardButton(text=change_text, callback_data="change_wallet")])
        
        # Кнопка назад
        back_text = "⬅️ Назад" if language == "ru" else "⬅️ Back"
        buttons.append([InlineKeyboardButton(text=back_text, callback_data="back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_wallet_list(wallets: list, language: str = "ru") -> InlineKeyboardMarkup:
        """Список кошельков для выбора"""
        buttons = []
        
        for i, wallet in enumerate(wallets):
            address = wallet["address"]
            name = wallet["name"] or f"{address[:6]}...{address[-4:]}"
            icon = "🐳" if wallet["is_whale"] else "👤"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"{icon} {name}",
                    callback_data=f"select_wallet_{i}"
                )
            ])
        
        # Кнопка назад
        back_text = "⬅️ Назад" if language == "ru" else "⬅️ Back"
        buttons.append([InlineKeyboardButton(text=back_text, callback_data="back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
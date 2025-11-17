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
                [KeyboardButton(text="📊 Мои кошельки"), KeyboardButton(text="📈 Состояние")],
                [KeyboardButton(text="📊 Аналитика"), KeyboardButton(text="🔍 Поиск")],
                [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="ℹ️ Помощь")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="➕ My Wallet"), KeyboardButton(text="➕ Whale")],
                [KeyboardButton(text="📊 My Wallets"), KeyboardButton(text="📈 Status")],
                [KeyboardButton(text="📊 Analytics"), KeyboardButton(text="🔍 Search")],
                [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="ℹ️ Help")]
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
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
            ]
        ])
    
    @staticmethod
    def get_analytics_menu(language: str = "ru") -> InlineKeyboardMarkup:
        """Меню аналитики"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="📊 Распределение портфеля", callback_data="portfolio_distribution")],
                [InlineKeyboardButton(text="🔥 Топ рынков", callback_data="top_markets")],
                [InlineKeyboardButton(text="📈 Анализ волатильности", callback_data="volatility_analysis")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="📊 Portfolio Distribution", callback_data="portfolio_distribution")],
                [InlineKeyboardButton(text="🔥 Top Markets", callback_data="top_markets")],
                [InlineKeyboardButton(text="📈 Volatility Analysis", callback_data="volatility_analysis")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_settings_menu(language: str = "ru") -> InlineKeyboardMarkup:
        """Меню настроек"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="🔔 Уведомления", callback_data="notification_settings")],
                [InlineKeyboardButton(text="🌐 Язык", callback_data="language_settings")],
                [InlineKeyboardButton(text="🛡️ Безопасность", callback_data="security_settings")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="🔔 Notifications", callback_data="notification_settings")],
                [InlineKeyboardButton(text="🌐 Language", callback_data="language_settings")],
                [InlineKeyboardButton(text="🛡️ Security", callback_data="security_settings")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_notification_settings(language: str = "ru") -> InlineKeyboardMarkup:
        """Настройки уведомлений"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="📈 Изменения портфеля ✅", callback_data="toggle_notification_portfolio")],
                [InlineKeyboardButton(text="🐳 Сделки китов ✅", callback_data="toggle_notification_whale")],
                [InlineKeyboardButton(text="🔥 Новые события ✅", callback_data="toggle_notification_events")],
                [InlineKeyboardButton(text="⚠️ Важные обновления ✅", callback_data="toggle_notification_updates")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="📈 Portfolio Changes ✅", callback_data="toggle_notification_portfolio")],
                [InlineKeyboardButton(text="🐳 Whale Trades ✅", callback_data="toggle_notification_whale")],
                [InlineKeyboardButton(text="🔥 New Events ✅", callback_data="toggle_notification_events")],
                [InlineKeyboardButton(text="⚠️ Important Updates ✅", callback_data="toggle_notification_updates")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_settings")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
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
        
        # Кнопка аналитики
        analytics_text = "📊 Аналитика" if language == "ru" else "📊 Analytics"
        buttons.append([InlineKeyboardButton(text=analytics_text, callback_data="analytics_menu")])
        
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
    
    @staticmethod
    def get_back_button(language: str = "ru") -> InlineKeyboardMarkup:
        """Кнопка возврата"""
        if language == "ru":
            button = [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_analytics")]
        else:
            button = [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_analytics")]
        
        return InlineKeyboardMarkup(inline_keyboard=[button])
    
    @staticmethod
    def get_quick_actions(language: str = "ru") -> ReplyKeyboardMarkup:
        """Быстрые действия"""
        if language == "ru":
            buttons = [
                [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="⚙️ Настройки")],
                [KeyboardButton(text="⬅️ Главная")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="🔄 Refresh"), KeyboardButton(text="📊 Status")],
                [KeyboardButton(text="🔍 Search"), KeyboardButton(text="⚙️ Settings")],
                [KeyboardButton(text="⬅️ Main")]
            ]
        
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Быстрые действия" if language == "ru" else "Quick actions"
        )

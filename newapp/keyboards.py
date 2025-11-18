from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)


class Keyboards:
    """Класс для создания клавиатур"""
    
    @staticmethod
    def get_language_selection_start() -> InlineKeyboardMarkup:
        """Выбор языка при старте"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_start_ru"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_start_en")
            ]
        ])
    
    @staticmethod
    def get_main_menu(language: str = "en") -> ReplyKeyboardMarkup:
        """Главное меню"""
        if language == "ru":
            buttons = [
                [KeyboardButton(text="💰 Ставки"), KeyboardButton(text="👛 Кошельки")],
                [KeyboardButton(text="📊 Отчеты"), KeyboardButton(text="🔍 Поиск")],
                [KeyboardButton(text="⚙️ Настройки")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="💰 Betting"), KeyboardButton(text="👛 Wallets")],
                [KeyboardButton(text="📊 Reports"), KeyboardButton(text="🔍 Search")],
                [KeyboardButton(text="⚙️ Settings")]
            ]
        
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Выберите действие" if language == "ru" else "Choose action"
        )
    
    @staticmethod
    def get_language_selection() -> InlineKeyboardMarkup:
        """Выбор языка из настроек"""
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
    def get_analytics_menu(language: str = "en") -> InlineKeyboardMarkup:
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
    def get_settings_menu(language: str = "en") -> InlineKeyboardMarkup:
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
    def get_notification_settings(language: str = "en") -> InlineKeyboardMarkup:
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
    def get_wallet_selection(wallets: list, current_index: int, language: str = "en") -> InlineKeyboardMarkup:
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
    def get_wallet_list(wallets: list, language: str = "en") -> InlineKeyboardMarkup:
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
    def get_back_button(language: str = "en") -> InlineKeyboardMarkup:
        """Кнопка возврата"""
        if language == "ru":
            button = [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_analytics")]
        else:
            button = [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_analytics")]
        
        return InlineKeyboardMarkup(inline_keyboard=[button])
    
    @staticmethod
    def get_back_to_settings(language: str = "en") -> InlineKeyboardMarkup:
        """Кнопка возврата в настройки"""
        if language == "ru":
            button = [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
        else:
            button = [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_settings")]
        
        return InlineKeyboardMarkup(inline_keyboard=[button])
    
    @staticmethod
    def get_quick_actions(language: str = "en") -> ReplyKeyboardMarkup:
        """Быстрые действия"""
        if language == "ru":
            buttons = [
                [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="💰 Ставки"), KeyboardButton(text="🎯 Мои ставки")],
                [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="⚙️ Настройки")],
                [KeyboardButton(text="⬅️ Главная")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="🔄 Refresh"), KeyboardButton(text="📊 Status")],
                [KeyboardButton(text="💰 Betting"), KeyboardButton(text="🎯 My Bets")],
                [KeyboardButton(text="🔍 Search"), KeyboardButton(text="⚙️ Settings")],
                [KeyboardButton(text="⬅️ Main")]
            ]
        
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Быстрые действия" if language == "ru" else "Quick actions"
        )
    
    @staticmethod
    def get_betting_menu(language: str = "en") -> InlineKeyboardMarkup:
        """Меню ставок"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="🎯 Сделать ставку", callback_data="place_bet")],
                [InlineKeyboardButton(text="📊 Доступные рынки", callback_data="available_markets")],
                [InlineKeyboardButton(text="📋 История ставок", callback_data="bet_history")],
                [InlineKeyboardButton(text="🛡️ Мой Safe кошелек", callback_data="my_safe_wallet")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="🎯 Place Bet", callback_data="place_bet")],
                [InlineKeyboardButton(text="📊 Available Markets", callback_data="available_markets")],
                [InlineKeyboardButton(text="📋 Bet History", callback_data="bet_history")],
                [InlineKeyboardButton(text="🛡️ My Safe Wallet", callback_data="my_safe_wallet")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_bet_confirmation(language: str = "en") -> InlineKeyboardMarkup:
        """Подтверждение ставки"""
        if language == "ru":
            buttons = [
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_bet"),
                    InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_bet")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_betting")]
            ]
        else:
            buttons = [
                [
                    InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_bet"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_bet")
                ],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_betting")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_wallets_menu(language: str = "en") -> InlineKeyboardMarkup:
        """Меню кошельков"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="👤 Мой кошелек", callback_data="my_wallet")],
                [InlineKeyboardButton(text="🐳 Киты", callback_data="whales")],
                [InlineKeyboardButton(text="➕ Добавить кошелек", callback_data="add_wallet")],
                [InlineKeyboardButton(text="🗑️ Удалить кошелек", callback_data="delete_wallet")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="👤 My Wallet", callback_data="my_wallet")],
                [InlineKeyboardButton(text="🐳 Whales", callback_data="whales")],
                [InlineKeyboardButton(text="➕ Add Wallet", callback_data="add_wallet")],
                [InlineKeyboardButton(text="🗑️ Delete Wallet", callback_data="delete_wallet")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_reports_menu(language: str = "en") -> InlineKeyboardMarkup:
        """Меню отчетов (состояние + аналитика)"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="📈 Общее состояние", callback_data="overall_status")],
                [InlineKeyboardButton(text="📊 Детальная аналитика", callback_data="detailed_analytics")],
                [InlineKeyboardButton(text="🔥 Топ рынки", callback_data="top_markets")],
                [InlineKeyboardButton(text="📉 Волатильность", callback_data="volatility")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="📈 Overall Status", callback_data="overall_status")],
                [InlineKeyboardButton(text="📊 Detailed Analytics", callback_data="detailed_analytics")],
                [InlineKeyboardButton(text="🔥 Top Markets", callback_data="top_markets")],
                [InlineKeyboardButton(text="📉 Volatility", callback_data="volatility")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_settings_menu_updated(language: str = "en") -> InlineKeyboardMarkup:
        """Обновленное меню настроек"""
        if language == "ru":
            buttons = [
                [InlineKeyboardButton(text="🔔 Уведомления", callback_data="notification_settings")],
                [InlineKeyboardButton(text="🌐 Язык", callback_data="language_settings")],
                [InlineKeyboardButton(text="🛡️ Безопасность", callback_data="security_settings")],
                [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="🔔 Notifications", callback_data="notification_settings")],
                [InlineKeyboardButton(text="🌐 Language", callback_data="language_settings")],
                [InlineKeyboardButton(text="🛡️ Security", callback_data="security_settings")],
                [InlineKeyboardButton(text="ℹ️ Help", callback_data="help")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_menu")]
            ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)

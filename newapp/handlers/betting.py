from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Dict, Any
import logging

from newapp.builder_api import PolymarketBuilderAPI, BettingManager


class BettingStates(StatesGroup):
    """Состояния для процесса ставок"""
    waiting_for_market = State()
    waiting_for_outcome = State()
    waiting_for_amount = State()
    confirming_bet = State()


class BettingHandler:
    """Обработчик команд для ставок"""
    
    def __init__(self):
        self.router = Router()
        self.logger = logging.getLogger(__name__)
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        
        @self.router.message(Command("bet"))
        async def start_betting(message: Message, state: FSMContext, db, polymarket: PolymarketBuilderAPI):
            """Начало процесса ставки"""
            user_id = message.from_user.id
            
            # Проверяем, есть ли у пользователя кошельки
            wallets = await db.get_user_wallets(user_id)
            if not wallets:
                await message.answer(
                    "❌ У вас нет добавленных кошельков.\n"
                    "Сначала добавьте кошелек командой /add_wallet"
                )
                return
            
            # Создаем менеджер ставок
            betting_manager = BettingManager(polymarket, db)
            
            # Инициализируем систему ставок для первого кошелька
            wallet_address = wallets[0]['address']
            safe_address = await betting_manager.initialize_user_betting(user_id, wallet_address)
            
            if not safe_address:
                await message.answer(
                    "❌ Не удалось инициализировать систему ставок.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
                return
            
            await state.update_data({
                'safe_address': safe_address,
                'wallet_address': wallet_address
            })
            
            await message.answer(
                f"🎯 <b>Размещение ставки</b>\n\n"
                f"🛡️ Ваш Safe кошелек: <code>{safe_address}</code>\n\n"
                f"📝 Введите ID рынка (market ID) для ставки:\n"
                f"<i>Пример: 0x1234...5678</i>"
            )
            await state.set_state(BettingStates.waiting_for_market)
        
        @self.router.message(BettingStates.waiting_for_market)
        async def process_market_id(message: Message, state: FSMContext):
            """Обработка ID рынка"""
            market_id = message.text.strip()
            
            # Базовая валидация market ID
            if not market_id.startswith("0x") or len(market_id) != 42:
                await message.answer(
                    "❌ Неверный формат Market ID.\n"
                    "Должен быть в формате 0x... (42 символа)\n\n"
                    "Попробуйте еще раз:"
                )
                return
            
            # Получаем информацию о рынке
            # Временная заглушка - нужно интегрировать с реальным API
            market_info = {
                "title": "Sample Market",
                "outcomes": ["Да", "Нет"]
            }
            
            await state.update_data({
                'market_id': market_id,
                'market_title': market_info['title'],
                'outcomes': market_info['outcomes']
            })
            
            outcomes_text = "\n".join([f"{i+1}. {outcome}" for i, outcome in enumerate(market_info['outcomes'])])
            
            await message.answer(
                f"📊 <b>Рынок:</b> {market_info['title']}\n\n"
                f"🎯 <b>Выберите исход:</b>\n"
                f"{outcomes_text}\n\n"
                f"Введите номер исхода (1-{len(market_info['outcomes'])}):"
            )
            await state.set_state(BettingStates.waiting_for_outcome)
        
        @self.router.message(BettingStates.waiting_for_outcome)
        async def process_outcome(message: Message, state: FSMContext):
            """Обработка выбора исхода"""
            try:
                outcome_num = int(message.text.strip())
                data = await state.get_data()
                outcomes = data.get('outcomes', [])
                
                if outcome_num < 1 or outcome_num > len(outcomes):
                    await message.answer(
                        f"❌ Неверный номер исхода.\n"
                        f"Введите число от 1 до {len(outcomes)}:"
                    )
                    return
                
                outcome_index = outcome_num - 1
                selected_outcome = outcomes[outcome_index]
                
                await state.update_data({
                    'outcome': outcome_index,
                    'selected_outcome': selected_outcome
                })
                
                await message.answer(
                    f"✅ <b>Выбран исход:</b> {selected_outcome}\n\n"
                    f"💵 <b>Введите сумму ставки в USDC:</b>\n"
                    f"<i>Пример: 10.5</i>"
                )
                await state.set_state(BettingStates.waiting_for_amount)
                
            except ValueError:
                await message.answer(
                    "❌ Пожалуйста, введите число.\n"
                    "Попробуйте еще раз:"
                )
        
        @self.router.message(BettingStates.waiting_for_amount)
        async def process_amount(message: Message, state: FSMContext):
            """Обработка суммы ставки"""
            try:
                amount = float(message.text.strip())
                
                if amount <= 0:
                    await message.answer(
                        "❌ Сумма должна быть больше 0.\n"
                        "Попробуйте еще раз:"
                    )
                    return
                
                if amount > 1000:  # Лимит на ставку
                    await message.answer(
                        "❌ Максимальная сумма ставки - 1000 USDC.\n"
                        "Попробуйте еще раз:"
                    )
                    return
                
                data = await state.get_data()
                
                await state.update_data({
                    'amount': amount
                })
                
                bet_summary = (
                    f"🎯 <b>Сводка ставки</b>\n\n"
                    f"📊 <b>Рынок:</b> {data['market_title']}\n"
                    f"🎯 <b>Исход:</b> {data['selected_outcome']}\n"
                    f"💵 <b>Сумма:</b> {amount} USDC\n"
                    f"🛡️ <b>Кошелек:</b> <code>{data['safe_address'][:10]}...{data['safe_address'][-8:]}</code>\n\n"
                    f"✅ <b>Подтвердить ставку?</b>\n"
                    f"Отправьте 'да' для подтверждения или 'нет' для отмены."
                )
                
                await message.answer(bet_summary)
                await state.set_state(BettingStates.confirming_bet)
                
            except ValueError:
                await message.answer(
                    "❌ Пожалуйста, введите число.\n"
                    "Попробуйте еще раз:"
                )
        
        @self.router.message(BettingStates.confirming_bet)
        async def confirm_bet(message: Message, state: FSMContext, db, polymarket: PolymarketBuilderAPI):
            """Подтверждение ставки"""
            user_id = message.from_user.id
            confirmation = message.text.strip().lower()
            
            if confirmation not in ['да', 'нет', 'yes', 'no']:
                await message.answer(
                    "❌ Пожалуйста, ответьте 'да' или 'нет'.\n"
                    "Подтвердите ставку:"
                )
                return
            
            if confirmation in ['нет', 'no']:
                await message.answer("❌ Ставка отменена.")
                await state.clear()
                return
            
            # Размещаем ставку
            data = await state.get_data()
            betting_manager = BettingManager(polymarket, db)
            
            await message.answer("⏳ Размещаем ставку...")
            
            tx_hash = await betting_manager.place_bet_for_user(
                user_id, 
                data['market_id'], 
                data['outcome'], 
                data['amount']
            )
            
            if tx_hash:
                await message.answer(
                    f"✅ <b>Ставка размещена!</b>\n\n"
                    f"📊 <b>Рынок:</b> {data['market_title']}\n"
                    f"🎯 <b>Исход:</b> {data['selected_outcome']}\n"
                    f"💵 <b>Сумма:</b> {data['amount']} USDC\n"
                    f"🔗 <b>Транзакция:</b> <code>{tx_hash}</code>\n\n"
                    f"Можете отслеживать статус в истории ставок /my_bets"
                )
            else:
                await message.answer(
                    "❌ <b>Ошибка при размещении ставки</b>\n\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
            
            await state.clear()
        
        @self.router.message(Command("my_bets"))
        async def show_bet_history(message: Message, db):
            """Показывает историю ставок пользователя"""
            user_id = message.from_user.id
            
            bets = await db.get_user_bets(user_id, limit=10)
            
            if not bets:
                await message.answer("📭 У вас еще нет ставок.")
                return
            
            bets_text = "📋 <b>Ваши последние ставки:</b>\n\n"
            
            for i, bet in enumerate(bets, 1):
                status_emoji = "✅" if bet['status'] == 'confirmed' else "⏳"
                bets_text += (
                    f"{i}. {status_emoji} <b>{bet['market_id'][:10]}...</b>\n"
                    f"   Исход: {bet['outcome']} | Сумма: {bet['amount']} USDC\n"
                    f"   Статус: {bet['status']}\n\n"
                )
            
            await message.answer(bets_text)
        
        @self.router.message(Command("markets"))
        async def show_available_markets(message: Message, polymarket: PolymarketBuilderAPI):
            """Показывает доступные рынки"""
            # Временная заглушка - нужно интегрировать с реальным API
            sample_markets = [
                {
                    "id": "0x1234567890abcdef1234567890abcdef12345678",
                    "title": "Будет ли цена BTC выше $50,000 к концу года?",
                    "liquidity": 15000.0
                },
                {
                    "id": "0xabcdef1234567890abcdef1234567890abcdef12", 
                    "title": "Выиграет ли Team A в следующем матче?",
                    "liquidity": 8000.0
                }
            ]
            
            markets_text = "📊 <b>Доступные рынки:</b>\n\n"
            
            for market in sample_markets:
                markets_text += (
                    f"🔹 <b>{market['title']}</b>\n"
                    f"   ID: <code>{market['id']}</code>\n"
                    f"   Ликвидность: {market['liquidity']} USDC\n\n"
                )
            
            markets_text += "💡 Для ставки используйте команду /bet"
            
            await message.answer(markets_text)


# Создаем экземпляр роутера
betting_handler = BettingHandler()
router = betting_handler.router

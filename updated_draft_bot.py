import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

# ВСТАВЬ СЮДА ТОКЕН ОТ BOTFATHER
BOT_TOKEN = "8334419911:AAEX8AtvIBRqTny-eoNEhwCaThwO2fGp7LQ"

# ---------- ПЕРЕМЕННЫЕ СТАТА ----------
players_list = []       # список игроков, который админ вручную вводит (имена, не юзернеймы)
captains = []           # список капитанов (строки вида "@username")
teams = {}              # {captain: [игроки]}
turn_index = 0
draft_started = False

# ---------- КЛАВИАТУРЫ ----------
def remaining_players_keyboard():
    kb = []
    for p in players_list:
        if not any(p in lst for lst in teams.values()):
            kb.append([InlineKeyboardButton(text=p, callback_data=f"pick:{p}")])
    if not kb:
        # пустая клавиатура, когда никого нет
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def players_preview_text():
    if not players_list:
        return "Список игроков пуст. Введи его с помощью команды /set_players"
    return "Список игроков (в порядке введения):\n" + "\n".join(f"• {p}" for p in players_list)

# ---------- КОМАНДЫ ----------
async def cmd_set_players(msg: Message):
    """
    /set_players имя1, имя2, имя3
    или
    /set_players
    имя1
    имя2
    имя3
    """
    global players_list, draft_started, teams, turn_index

    text = msg.text[len("/set_players"):].strip()
    if not text:
        await msg.answer("Отправь команду в формате:\n`/set_players Имя1, Имя2, Имя3`\nили\n`/set_players` и далее в том же сообщении вставь список по строкам.",
                         parse_mode="Markdown")
        return

    # Разделяем по запятым или по переносам строки
    parts = [p.strip() for p in (text.replace(",", "\n").splitlines()) if p.strip()]
    players_list = parts
    # сброс состояния драфта — админ вводит список заново
    draft_started = False
    teams = {}
    turn_index = 0
    await msg.answer("✅ Список игроков обновлён.\n" + players_preview_text())

async def cmd_set_captains(msg: Message):
    global captains, teams, turn_index, draft_started
    parts = msg.text.split()[1:]
    if not parts:
        await msg.answer("Укажи капитанов, например:\n`/set_captains @cap1 @cap2 @cap3`", parse_mode="Markdown")
        return
    # простая валидация: должны начинаться с @
    caps = [p if p.startswith("@") else f"@{p}" for p in parts]
    captains = caps
    teams = {cap: [] for cap in captains}
    turn_index = 0
    draft_started = False
    await msg.answer(f"🧢 Капитаны назначены: {', '.join(captains)}\n\nТеперь вызови /start_draft чтобы начать выбор.")

async def cmd_start_draft(msg: Message):
    global draft_started, turn_index, teams
    if not players_list:
        await msg.answer("Сначала задай список игроков командой /set_players")
        return
    if not captains:
        await msg.answer("Сначала назначь капитанов командой /set_captains")
        return
    teams = {cap: [] for cap in captains}  # сброс команд при старте
    turn_index = 0
    draft_started = True
    first = captains[turn_index]
    await msg.answer(f"🏁 Драфт начат! Первый ход: {first}\n\n{players_preview_text()}",
                     reply_markup=remaining_players_keyboard())

async def cmd_status(msg: Message):
    text = "📋 Текущий статус:\n\n"
    text += players_preview_text() + "\n\n"
    if not captains:
        text += "Капитаны: не назначены\n"
    else:
        for cap in captains:
            members = teams.get(cap, [])
            text += f"{cap}: " + (", ".join(members) if members else "—") + "\n"
        if draft_started:
            text += f"\nСейчас ход {captains[turn_index]}"
    await msg.answer(text)

async def cmd_reset(msg: Message):
    global players_list, captains, teams, turn_index, draft_started
    players_list = []
    captains = []
    teams = {}
    turn_index = 0
    draft_started = False
    await msg.answer("🔄 Все данные сброшены. /set_players чтобы задать список заново.")

# ---------- CALLBACKS (выбор игрока) ----------
async def pick_player(cb: CallbackQuery):
    global turn_index, draft_started
    if not draft_started:
        await cb.answer("Драфт ещё не начат. Вызовите /start_draft.", show_alert=True)
        return
    captain = captains[turn_index]
    user = f"@{cb.from_user.username}" if cb.from_user.username else cb.from_user.full_name
    if user != captain:
        await cb.answer("Сейчас не твой ход (только назначенный капитан может выбирать).", show_alert=True)
        return
    player = cb.data.split(":", 1)[1]
    if any(player in lst for lst in teams.values()):
        await cb.answer("Этот игрок уже выбран.", show_alert=True)
        return
    teams[captain].append(player)
    # переход хода
    turn_index = (turn_index + 1) % len(captains)
    remaining = [p for p in players_list if not any(p in lst for lst in teams.values())]
    if not remaining:
        txt = "🏁 Драфт завершён!\n\n"
        for cap, members in teams.items():
            txt += f"{cap}:\n" + ("\n".join(f"• {m}" for m in members) if members else "• —") + "\n\n"
        await cb.message.edit_text(txt)
        await cb.answer("Готово ✅")
        draft_started = False
        return
    next_cap = captains[turn_index]
    await cb.message.edit_text(
        f"✅ {captain} выбрал *{player}*.\nТеперь ход {next_cap}.\n\nОставшиеся:\n" + "\n".join(f"• {p}" for p in remaining),
        parse_mode="Markdown",
        reply_markup=remaining_players_keyboard()
    )
    await cb.answer()

# ---------- ЗАПУСК ----------
async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_set_players, Command("set_players"))
    dp.message.register(cmd_set_captains, Command("set_captains"))
    dp.message.register(cmd_start_draft, Command("start_draft"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_reset, Command("reset_draft"))
    dp.callback_query.register(pick_player, F.data.startswith("pick:"))

    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

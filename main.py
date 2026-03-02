import os
from openai import OpenAI
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TEACHER_STYLE = os.environ.get("TEACHER_STYLE", "Вежливо, коротко, понятно.")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты — AI-ассистент учителя. "
    "Главная цель: экономить время учителя, предлагая готовые ответы и тексты. "
    "Пиши по-русски."
)

# Небольшая библиотека типовых заготовок (можем расширить потом)
TEMPLATES = {
    "перенос": "Здравствуйте! Давайте перенесём занятие. Мне подойдут варианты: {slots}. Какой вам удобнее?",
    "оплата": "Здравствуйте! Напоминаю про оплату занятий. Подскажите, пожалуйста, когда будет удобно оплатить?",
    "домашка": "Здравствуйте! Напоминаю про домашнее задание: {hw}. Если есть вопросы — напишите, помогу.",
    "отмена": "Здравствуйте! Сегодня, к сожалению, занятие отменяется. Можем выбрать другое время на этой неделе. Вам какие дни подходят?",
    "опоздание": "Здравствуйте! Я немного задерживаюсь на {mins} минут. Если вам неудобно — можем сдвинуть/перенести занятие."
}

def make_buttons():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Подходит", callback_data="ok"),
        InlineKeyboardButton("🔁 Другой вариант", callback_data="alt")
    )
    return kb

# Храним последний запрос пользователя для кнопки "другой вариант"
LAST_USER_PROMPT = {}

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Привет! Я AI-ассистент учителя 🤖\n\n"
        "Команды:\n"
        "• /ask <текст> — общий запрос к ассистенту\n"
        "• /reply <текст или тема> — подготовить ответ родителю/ученику\n"
        "• /templates — список быстрых шаблонов\n\n"
        "Пример:\n"
        "/reply Родитель просит перенести занятие с сегодня на завтра."
    )

@bot.message_handler(commands=["templates"])
def templates(message):
    keys = ", ".join(TEMPLATES.keys())
    bot.reply_to(message, f"Доступные шаблоны: {keys}\n\nПример:\n/reply перенос")

@bot.message_handler(commands=["ask"])
def ask(message):
    user_text = message.text.replace("/ask", "", 1).strip()
    if not user_text:
        bot.reply_to(message, "Напиши запрос после /ask.")
        return

    bot.send_chat_action(message.chat.id, "typing")

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        bot.reply_to(message, resp.output_text.strip() or "Пустой ответ. Попробуй иначе.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при обращении к AI: {e}")

def generate_reply(user_prompt: str) -> str:
    style = TEACHER_STYLE.strip()

    prompt = (
        "Сгенерируй 2 коротких варианта ответа (A и B) для учителя.\n"
        f"Стиль учителя: {style}\n"
        "Требования:\n"
        "- 2 варианта: A и B\n"
        "- каждый 1–4 предложения\n"
        "- без лишних объяснений\n"
        "- если нужно уточнение — задай 1 вопрос в конце\n\n"
        f"Сообщение/ситуация:\n{user_prompt}"
    )

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.output_text.strip()

@bot.message_handler(commands=["reply"])
def reply_cmd(message):
    text = message.text.replace("/reply", "", 1).strip()

    if not text:
        bot.reply_to(message, "Напиши тему или вставь сообщение после /reply.\nПример:\n/reply перенос")
        return

    # 1) Если это название шаблона — выдаём шаблон
    if text.lower() in TEMPLATES:
        bot.reply_to(message, f"Шаблон «{text.lower()}»:\n\n{TEMPLATES[text.lower()]}\n\n(Если хочешь — я могу адаптировать под конкретную ситуацию через /reply <сообщение>)")
        return

    # 2) Иначе — генерируем AI-ответ
    bot.send_chat_action(message.chat.id, "typing")

    try:
        chat_id = message.chat.id
        LAST_USER_PROMPT[chat_id] = text

        answer = generate_reply(text)
        bot.send_message(chat_id, answer, reply_markup=make_buttons())
    except Exception as e:
        bot.reply_to(message, f"Ошибка при генерации ответа: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    chat_id = call.message.chat.id

    if call.data == "ok":
        bot.answer_callback_query(call.id, "Отлично ✅")
        bot.send_message(chat_id, "Принято. Можешь скопировать текст и отправить.")
        return

    if call.data == "alt":
        bot.answer_callback_query(call.id, "Генерирую другой вариант…")
        bot.send_chat_action(chat_id, "typing")

        user_prompt = LAST_USER_PROMPT.get(chat_id)
        if not user_prompt:
            bot.send_message(chat_id, "Не нашёл предыдущий запрос. Введи заново командой /reply ...")
            return

        try:
            # Добавим просьбу сделать ИНОЙ вариант
            answer = generate_reply(user_prompt + "\n\nСделай варианты более отличающимися от предыдущих.")
            bot.send_message(chat_id, answer, reply_markup=make_buttons())
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {e}")

bot.polling()

import os
from openai import OpenAI
import telebot

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты — AI-ассистент учителя. "
    "Помогай экономить время: формулируй короткие, вежливые и понятные ответы ученикам и родителям. "
    "Если не хватает данных — задай 1 уточняющий вопрос."
)

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Привет! Я AI-ассистент учителя 🤖\n\n"
        "Команды:\n"
        "• /ask <текст> — задать вопрос ассистенту\n\n"
        "Пример:\n"
        "/ask Составь вежливый ответ родителю о переносе занятия."
    )

@bot.message_handler(commands=["ask"])
def ask(message):
    user_text = message.text.replace("/ask", "", 1).strip()
    if not user_text:
        bot.reply_to(message, "Напиши запрос после /ask. Например:\n/ask Составь сообщение ученику с напоминанием.")
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
        answer = resp.output_text.strip()
        bot.reply_to(message, answer if answer else "Не получилось сформировать ответ. Попробуй переформулировать.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при обращении к AI: {e}")

bot.polling()

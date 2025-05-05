import PyPDF2

import subprocess

from telegram import Update

from telegram.ext import (

    Application, CommandHandler, MessageHandler,

    filters, CallbackContext, ConversationHandler

)

from apscheduler.schedulers.background import BackgroundScheduler

import os

import json
 
# === HR Document Extraction ===

def extract_text_from_pdf(pdf_path):

    with open(pdf_path, "rb") as file:

        reader = PyPDF2.PdfReader(file)

        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

    return text
 
hr_pdf_path = "sample_hr_policy.pdf"

hr_policies = extract_text_from_pdf('/home/pipl-84/HR_chatbot/sample_hr_policy.pdf')
 
# === Memory Store ===

memory_file = "user_memory.json"
 
def load_memory():

    if os.path.exists(memory_file):

        with open(memory_file, "r") as f:

            return json.load(f)

    return {}
 
def save_memory(memory):

    with open(memory_file, "w") as f:

        json.dump(memory, f)
 
user_memory = load_memory()
 
# === Authorized Telegram Users ===

AUTHORIZED_USERS = []  # Replace with real Telegram user IDs
 
# === Llama Prompt Function ===

def ask_llama(user_id, question):

    history = "\n".join(user_memory.get(str(user_id), []))

    prompt = f"HR Policies:\n{hr_policies}\n\nChat History:\n{history}\n\nUser Question: {question}\nAnswer:"

    try:

        result = subprocess.run(["ollama", "run", "llama3:8B", prompt], capture_output=True, text=True, timeout=30)

        response = result.stdout.strip()

        if not response:

            response = "Sorry, I couldn't find an answer. Please try rephrasing your question."

    except subprocess.TimeoutExpired:

        response = "The AI is taking too long to respond. Please try again."

    except Exception as e:

        response = f"An error occurred: {str(e)}"
 
    # Save to memory

    user_memory.setdefault(str(user_id), []).append(f"User: {question}\nBot: {response}")

    save_memory(user_memory)
 
    return response
 
# === Telegram Bot Setup ===

TELEGRAM_BOT_TOKEN = ""
 
# Feedback state

FEEDBACK = range(1)
 
# === Start Command Handler ===

async def start(update: Update, context: CallbackContext) -> None:

    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:

        await update.message.reply_text(" Access denied. You are not authorized to use this HR bot.")

        return

    await update.message.reply_text("Hi! I'm your HR chatbot. Ask me any HR-related question.")
 
# === Message Handler ===

async def handle_message(update: Update, context: CallbackContext) -> int:

    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:

        await update.message.reply_text(" Access denied. You are not authorized to use this HR bot.")

        return ConversationHandler.END
 
    user_message = update.message.text

    response = ask_llama(user_id, user_message)

    context.user_data['last_response'] = response

    context.user_data['last_question'] = user_message
 
    await update.message.reply_text(response)

    await update.message.reply_text("Was this helpful? (Yes/No)")

    return FEEDBACK
 
# === Feedback Handler ===

async def handle_feedback(update: Update, context: CallbackContext) -> int:

    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:

        await update.message.reply_text("Access denied.")

        return ConversationHandler.END
 
    feedback = update.message.text.lower()

    question = context.user_data.get("last_question", "")

    response = context.user_data.get("last_response", "")
 
    feedback_log = f"Feedback from {user_id} — Q: {question} | A: {response} | Helpful: {feedback}"

    print(feedback_log)  # You can write to a log file if needed
 
    await update.message.reply_text("Thanks for the feedback! You can continue asking.")

    return ConversationHandler.END
 
# === Proactive Reminders ===

def send_reminders(app: Application):

    async def notify_users():

        for user_id in AUTHORIZED_USERS:

            try:

                await app.bot.send_message(chat_id=int(user_id), text="Reminder: Don’t forget to complete your HR documents.")

            except Exception as e:

                print(f"Failed to notify {user_id}: {e}")

    return notify_users
 
# === Initialize Bot ===

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
 
# Conversation handler for feedback loop

conv_handler = ConversationHandler(

    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],

    states={FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)]},

    fallbacks=[]

)
 
app.add_handler(CommandHandler("start", start))

app.add_handler(conv_handler)
 
# === Start Scheduler ===

scheduler = BackgroundScheduler()

scheduler.add_job(send_reminders(app), 'interval', hours=24)  # Set to daily reminders

scheduler.start()
 
print("HR Bot is running...")

app.run_polling()

 
import os
import asyncio
from telegram import Update, bot
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

from lens import Lens
from dotenv import load_dotenv

load_dotenv()


class TelegramLens:

    def handle_chat(self, update: Update, _: CallbackContext):
        user_message = update.message.text

        # if user_message.startswith("/"):
            
        lens = Lens(private_key=os.environ.get('PK'))
        message = asyncio.run(lens.post(user_message))

        update.message.reply_text(message)

    def start(self):
        updater = Updater(os.environ.get('TELEGRAM_TOKEN'))
        dispatcher = updater.dispatcher
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, self.handle_chat))

        updater.start_polling()
        updater.idle()


if __name__ == '__main__':
    chatbot = TelegramLens()
    chatbot.start()

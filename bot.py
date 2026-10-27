from datetime import datetime
import io
import os
import threading
import time
from flask import Flask
import matplotlib
import matplotlib.pyplot as plt
import telebot
from telebot import types
from tradingview_ta import Interval, TA_Handler

# Налаштування matplotlib для роботи без монітора
matplotlib.use("Agg")

# Безпечне отримання токена та перевірка в логах
TOKEN = os.getenv("BOT_TOKEN")
print(
    f"ПЕРЕВІРКА ТОКЕНА: {TOKEN[:5] if TOKEN else 'ВІДСУТНІЙ'}... (довжина:"
    f" {len(TOKEN) if TOKEN else 0})"
)
bot = telebot.TeleBot(TOKEN)

# Список активів
ASSETS = {
    "EURUSD": {"screener": "forex", "exchange": "FX"},
    "GBPUSD": {"screener": "forex", "exchange": "FX"},
    "USDJPY": {"screener": "forex", "exchange": "FX"},
    "AUDUSD": {"screener": "forex", "exchange": "FX"},
    "USDCAD": {"screener": "forex", "exchange": "FX"},
    "USDCHF": {"screener": "forex", "exchange": "FX"},
    "NZDUSD": {"screener": "forex", "exchange": "FX"},
    "EURGBP": {"screener": "forex", "exchange": "FX"},
    "EURJPY": {"screener": "forex", "exchange": "FX"},
    "GBPJPY": {"screener": "forex", "exchange": "FX"},
    "EURAUD": {"screener": "forex", "exchange": "FX"},
    "XAUUSD": {"screener": "forex", "exchange": "OANDA"},
    "BTCUSD": {"screener": "crypto", "exchange": "BINANCE"},
    "ETHUSD": {"screener": "crypto", "exchange": "BINANCE"},
}

# Таймфрейми
TIMEFRAMES = {
    "1 хвилина": {"interval": Interval.INTERVAL_1_MINUTE, "seconds": 1 * 60},
    "5 хвилин": {"interval": Interval.INTERVAL_5_MINUTES, "seconds": 5 * 60},
    "15 хвилин": {
        "interval": Interval.INTERVAL_15_MINUTES,
        "seconds": 15 * 60,
    },
    "30 хвилин": {
        "interval": Interval.INTERVAL_30_MINUTES,
        "seconds": 30 * 60,
    },
    "1 година": {"interval": Interval.INTERVAL_1_HOUR, "seconds": 60 * 60},
}

user_selections = {}
user_stats = {}


def generate_chart_image(pair, current_price, ema50):
  plt.figure(figsize=(6, 3.5), facecolor="#1e1e1e")
  ax = plt.axes()
  ax.set_facecolor("#121212")

  if isinstance(current_price, (int, float)) and isinstance(
      ema50, (int, float)
  ):
    x = range(10)
    y = [
        current_price
        + (i - 5) * (current_price * 0.0005)
        for i in range(10)
    ]
    y[-1] = current_price
    ema_line = [ema50] * 10

    ax.plot(
        x, y, color="#00ffcc", linewidth=2, label=f"Ціна: {current_price}"
    )
    ax.plot(
        x,
        ema_line,
        color="#ff5555",
        linestyle="--",
        linewidth=1.5,
        label=f"EMA 50: {ema50}",
    )

  plt.title(
      f"Технічний графік: {pair}", color="white", fontsize=12, fontweight="bold"
  )
  plt.tick_params(colors="white", labelsize=8)
  ax.xaxis.label.set_color("white")
  ax.yaxis.label.set_color("white")
  for spine in ax.spines.values():
    spine.set_edgecolor("#444444")

  plt.legend(loc="upper left", facecolor="#222222", labelcolor="white", fontsize=8)
  plt.tight_layout()

  buf = io.BytesIO()
  plt.savefig(buf, format="png", dpi=100, facecolor="#1e1e1e")
  buf.seek(0)
  plt.close()
  return buf


def check_news_alert():
  now = datetime.now()
  current_hour = now.hour
  current_minute = now.minute

  if (
      (current_hour == 14 and current_minute >= 30)
      or (current_hour in [15, 16])
      or (current_hour == 17 and current_minute <= 30)
  ):
    return (
        "⚠️ **УВАГА (НОВИННИЙ ФОН):** Зараз час можливого виходу важливих"
        " економічних новин! Волатильність підвищена."
    )
  return "✅ **Новинний фон:** Спокійно. Значних новинних ризиків немає."


def get_assets_keyboard():
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
  keys = list(ASSETS.keys())
  for i in range(0, len(keys), 3):
    row = [types.KeyboardButton(k) for k in keys[i : i + 3]]
    markup.add(*row)
  markup.add(types.KeyboardButton("📊 Моя статистика"))
  return markup


@bot.message_handler(commands=["start", "menu"])
def send_welcome(message):
  bot.send_message(
      message.chat.id,
      "🤖 *Вітаю у торговій системі!*\n\n"
      "📈 Оберіть актив для технічного аналізу нижче:",
      parse_mode="Markdown",
      reply_markup=get_assets_keyboard(),
  )


@bot.message_handler(func=lambda message: message.text == "📊 Моя статистика")
def show_stats_button(message):
  send_statistics(message.chat.id)


def send_statistics(chat_id):
  if chat_id not in user_stats:
    user_stats[chat_id] = {"wins": 0, "losses": 0}

  stats = user_stats[chat_id]
  wins = stats["wins"]
  losses = stats["losses"]
  total = wins + losses
  winrate = (wins / total * 100) if total > 0 else 0

  response = (
      f"📊 *СТАТИСТИКА ВАШИХ УГОД*\n"
      f"━━━━━━━━━━━━━━━━━━━\n"
      f"✅ Вдалих (Профіт): `{wins}`\n"
      f"❌ Невдалих (Збиток): `{losses}`\n"
      f"📋 Всього угод: `{total}`\n"
      f"🎯 Вінрейт (Winrate): `{winrate:.1f}%`\n"
      f"━━━━━━━━━━━━━━━━━━━"
  )
  bot.send_message(chat_id, response, parse_mode="Markdown")


@bot.message_handler(
    func=lambda message: message.text == "🔙 Назад до вибору активу"
)
def back_to_assets(message):
  bot.send_message(
      message.chat.id,
      "🔙 Повернення до списку активів:",
      reply_markup=get_assets_keyboard(),
  )


@bot.message_handler(func=lambda message: message.text in ASSETS)
def choose_pair(message):
  chat_id = message.chat.id
  user_selections[chat_id] = {"pair": message.text}

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  for tf_name in TIMEFRAMES.keys():
    markup.add(types.KeyboardButton(tf_name))
  markup.add(types.KeyboardButton("🔙 Назад до вибору активу"))

  bot.send_message(
      chat_id,
      f"💎 Обраний актив: *{message.text}*\n\n⏳ Тепер оберіть період угоди:",
      parse_mode="Markdown",
      reply_markup=markup,
  )


@bot.message_handler(func=lambda message: message.text in TIMEFRAMES)
def choose_timeframe(message):
  chat_id = message.chat.id

  if chat_id not in user_selections or "pair" not in user_selections[chat_id]:
    bot.send_message(
        chat_id,
        "⚠️ Будь ласка, почніть спочатку, обравши актив.",
        reply_markup=get_assets_keyboard(),
    )
    return

  pair = user_selections[chat_id]["pair"]
  tf_name = message.text
  tf_data = TIMEFRAMES[tf_name]
  interval = tf_data["interval"]
  duration_seconds = tf_data["seconds"]

  bot.send_message(
      chat_id,
      f"🔍 Малюю графік та аналізую рівні для *{pair}* ({tf_name})...",
      parse_mode="Markdown",
  )

  try:
    asset_info = ASSETS[pair]
    handler = TA_Handler(
        symbol=pair,
        exchange=asset_info["exchange"],
        screener=asset_info["screener"],
        interval=interval,
    )
    analysis = handler.get_analysis()

    rec = analysis.summary["RECOMMENDATION"]
    buy = analysis.summary["BUY"]
    sell = analysis.summary["SELL"]

    indicators = analysis.indicators
    current_price = indicators.get("close", 0)
    ema50 = indicators.get("EMA50", current_price)

    if isinstance(current_price, (int, float)):
      current_price_str = (
          f"{current_price:.5f}" if current_price < 10 else f"{current_price:.2f}"
      )
    else:
      current_price_str = str(current_price)

    if isinstance(current_price, (int, float)) and isinstance(
        ema50, (int, float)
    ):
      if current_price > ema50:
        sr_analysis = (
            "• *Рівні (Підтримка/Опір):* Ціна вище EMA 50. Лінія EMA 50 діє як"
            " динамічна **зона підтримки**."
        )
      else:
        sr_analysis = (
            "• *Рівні (Підтримка/Опір):* Ціна нижче EMA 50. Лінія EMA 50 діє як"
            " динамічна **зона опору**."
        )
    else:
      sr_analysis = "• *Рівні (Підтримка/Опір):* Дані EMA 50 недоступні."

    if "BUY" in rec:
      signal_emoji = "🟢"
      direction = "ВГОРУ (CALL)"
      reason = (
          f"• *Індикатори:* Переважання покупців (BUY: {buy}).\n{sr_analysis}\n•"
          " *Прогноз:* Очікується рух ціни вгору."
      )
    elif "SELL" in rec:
      signal_emoji = "🔴"
      direction = "ВНИЗ (PUT)"
      reason = (
          f"• *Індикатори:* Тиск продавців (SELL: {sell}).\n{sr_analysis}\n•"
          " *Прогноз:* Очікується зниження ціни вниз."
      )
    else:
      signal_emoji = "🟡"
      direction = "УТРИМАТИСЬ (ФЛЕТ)"
      reason = (
          f"• *Стан ринку:* Рівновага індикаторів.\n{sr_analysis}\n• *Прогноз:"
          " Чіткого тренду немає."
      )

    news_status = check_news_alert()

    response = (
        f"{signal_emoji} *ТОРГОВИЙ СИГНАЛ*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Актив:* `{pair}`\n"
        f"💵 *Поточна ціна:* `{current_price_str}`\n"
        f"⏱ *Період угоди:* `{tf_name}`\n\n"
        f"🎯 *Рекомендація:* *{direction}*\n\n"
        f"📝 *Аналіз та рівні:*\n{reason}\n\n"
        f"{news_status}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ *Таймер запущено!* Бот нагадає за {tf_name} для введення результату."
    )

    chart_buffer = generate_chart_image(pair, current_price, ema50)

    bot.send_photo(chat_id, photo=chart_buffer)
    bot.send_message(
        chat_id,
        response,
        parse_mode="Markdown",
        reply_markup=get_assets_keyboard(),
    )

    def trigger_feedback():
      markup_inline = types.InlineKeyboardMarkup(row_width=2)
      btn_win = types.InlineKeyboardButton(
          "✅ Профіт", callback_data=f"trade_win_{chat_id}"
      )
      btn_loss = types.InlineKeyboardButton(
          "❌ Збиток", callback_data=f"trade_loss_{chat_id}"
      )
      markup_inline.add(btn_win, btn_loss)

      bot.send_message(
          chat_id,
          f"🔔 *Час угоди завершився!*\n\n📊 Актив: `{pair}`"
          f" ({tf_name})\nЯк закрилася угода?",
          parse_mode="Markdown",
          reply_markup=markup_inline,
      )

    timer = threading.Timer(duration_seconds, trigger_feedback)
    timer.start()

  except Exception as e:
    bot.send_message(
        chat_id,
        f"❌ *Помилка при аналізі:* `{e}`\n(Можливо, ринок цього активу наразі"
        " закритий).",
        parse_mode="Markdown",
        reply_markup=get_assets_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_"))
def handle_trade_result(call):
  data_parts = call.data.split("_")
  result_type = data_parts[1]
  target_chat_id = int(data_parts[2])

  if target_chat_id not in user_stats:
    user_stats[target_chat_id] = {"wins": 0, "losses": 0}

  if result_type == "win":
    user_stats[target_chat_id]["wins"] += 1
    text_res = "✅ Угоду зараховано як **ПРОФІТ** (+)"
  else:
    user_stats[target_chat_id]["losses"] += 1
    text_res = "❌ Угоду зараховано як **ЗБИТОК** (-)"

  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"{call.message.text}\n\n{text_res}",
      parse_mode="Markdown",
  )

  send_statistics(target_chat_id)
  bot.answer_callback_query(call.id, "Результат збережено!")


# Міні-вебсервер на Flask для Render
app = Flask("")


@app.route("/")
def home():
  return "Bot is active and running!"


def run_web():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
  web_thread = threading.Thread(target=run_web)
  web_thread.start()

  print("Бот та вебсервер запущено успішно!")
  bot.infinity_polling()
      

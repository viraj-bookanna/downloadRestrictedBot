import logging,os,time,json,telethon
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom.button import Button
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv(override=True)

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URL = os.getenv("MONGODB_URL")
LOG_GROUP = int(os.getenv("LOG_GROUP_ID"))
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
mongo_client = MongoClient(MONGODB_URL, server_api=ServerApi('1'))
database = mongo_client.userdb.sessions
numpad = [
    [  
        Button.inline("1", '{"press":1}'), 
        Button.inline("2", '{"press":2}'), 
        Button.inline("3", '{"press":3}')
    ],
    [
        Button.inline("4", '{"press":4}'), 
        Button.inline("5", '{"press":5}'), 
        Button.inline("6", '{"press":6}')
    ],
    [
        Button.inline("7", '{"press":7}'), 
        Button.inline("8", '{"press":8}'), 
        Button.inline("9", '{"press":9}')
    ],
    [
        Button.inline("Clear All", '{"press":"clear_all"}'),
        Button.inline("0", '{"press":0}'),
        Button.inline("⌫", '{"press":"clear"}')
    ]
]

def get(obj, key, default=None):
    try:
        return obj[key]
    except:
        return default
def yesno(x):
    return [
        [Button.inline("Yes", '{{"press":"yes{}"}}'.format(x))],
        [Button.inline("No", '{{"press":"no{}"}}'.format(x))]
    ]
async def handle_usr(contact, event):
    msg = await event.respond(strings['sending1'], buttons=Button.clear())
    await msg.delete()
    msg = await event.respond(strings['sending2'])
    uclient = TelegramClient(StringSession(), API_ID, API_HASH)
    await uclient.connect()
    user_data = database.find_one({"chat_id":event.chat_id})
    try:
        scr = await uclient.send_code_request(contact.phone_number)
        data = {
        	'phone': contact.phone_number,
        	'code_len': scr.type.length,
            'phone_code_hash': scr.phone_code_hash
        }
        print(data)
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        await msg.edit(strings['ask_code'], buttons=numpad)
    except Exception as e:
        await msg.edit("Error: "+repr(e))
        print(e)
async def sign_in(event):
    try:
        uclient = TelegramClient(StringSession(), API_ID, API_HASH)
        await uclient.connect()
        user_data = database.find_one({"chat_id": event.chat_id})
        data = {}
        if get(user_data, 'code_ok', False) and get(user_data, 'pass_ok', False):
            await uclient.sign_in(user_data['phone'], user_data['code'], phone_code_hash=user_data['phone_code_hash'], password=user_data['pass'])
        elif get(user_data, 'code_ok', False) and not get(user_data, 'need_pass', False):
            await uclient.sign_in(user_data['phone'], user_data['code'], phone_code_hash=user_data['phone_code_hash'])
        else:
            return False
        await event.edit(strings['login_success'])
        data['session'] = uclient.session.save()
    except telethon.errors.PhoneCodeInvalidError as e:
        await event.edit(strings['code_invalid'])
        await event.respond(strings['ask_code'], buttons=numpad)
        data['code'] = ''
        data['code_ok'] = False
    except telethon.errors.SessionPasswordNeededError as e:
        data['need_pass'] = True
        data['pass_ok'] = False
        await event.edit(strings['ask_pass'])
    except telethon.errors.PasswordHashInvalidError as e:
        data['need_pass'] = True
        data['pass_ok'] = False
        await event.edit(strings['pass_invalid'])
        await event.respond(strings['ask_pass'])
    except Exception as e:
        data['code'] = ''
        data['code_ok'] = False
        await event.edit(repr(e))
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    return True
class TimeKeeper:
    last = 0
    last_edited_time = 0
    def __init__(self, status):
        self.status = status
async def get_gallery(client, chat, msg_id):
    msgs = await client.get_messages(chat, ids=[*range(msg_id - 9, msg_id + 10)])
    return [
        msg for msg in [i for i in msgs if i] # clean None
        if msg.grouped_id == msgs[9].grouped_id # 10th msg is target, guaranteed to exist
    ]
def progress_bar(percentage):
    prefix_char = '█'
    suffix_char = '▒'
    progressbar_length = 10
    prefix = round(percentage/progressbar_length) * prefix_char
    suffix = (progressbar_length-round(percentage/progressbar_length)) * suffix_char
    return f"{prefix}{suffix} {percentage:.2f}%"
def humanify(byte_size):
    siz_list = ['KB', 'MB', 'GB']
    for i in range(len(siz_list)):
        if byte_size/1024**(i+1) < 1024:
            return "{} {}".format(round(byte_size/1024**(i+1), 2), siz_list[i])
async def callback(current, total, tk, message):
    percentage = current/total*100
    if tk.last < percentage and tk.last_edited_time+5 < time.time():
        progressbar = progress_bar(percentage)
        h_current = humanify(current)
        h_total = humanify(total)
        await message.edit(f"{tk.status}: {progressbar}\nComplete: {h_current}\nTotal: {h_total}")
        tk.last = percentage
        tk.last_edited_time = time.time()

@bot.on(events.NewMessage)
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if user_data is None:
        sender = await event.get_sender()
        print({
            "chat_id": sender.id,
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
        })
        database.insert_one({
            "chat_id": sender.id,
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
        })
@bot.on(events.CallbackQuery)
async def handler(event):
    try:
        press = json.loads(event.data.decode())['press']
    except:
        return
    user_data = database.find_one({"chat_id": event.chat_id})
    data = {}
    if type(press)==int:
        data['code'] = get(user_data, 'code', '')+str(press)
        if len(data['code'])==user_data['code_len']:
            database.update_one({'_id': user_data['_id']}, {'$set': data})
            await event.edit(strings['ask_ok']+data['code'], buttons=yesno('code'))
            return
    elif press=="clear":
        data['code'] = user_data['code'][:-1]
    elif press=="clear_all" or press=="nocode":
        data['code'] = ''
        data['code_ok'] = False
    elif press=="yescode":
        data['code_ok'] = True
    elif press=="yespass":
        data['pass_ok'] = True
        data['need_pass'] = False
    elif press=="nopass":
        data['pass_ok'] = False
        data['need_pass'] = True
        await event.edit(strings['ask_pass'])
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    if press=="nopass":
        return
    if not await sign_in(event):
        await event.edit(strings['ask_code']+data['code'], buttons=numpad)
@bot.on(events.NewMessage(pattern=r"/start", func=lambda e: e.is_private))
async def handler(event):
    await event.respond(strings['hello'])
@bot.on(events.NewMessage(pattern=r"/login", func=lambda e: e.is_private))
async def handler(event):
    await event.respond(strings['ask_phone'], buttons=[Button.request_phone("SHARE CONTACT", resize=True, single_use=True)])
@bot.on(events.NewMessage(pattern=r"/add_session", func=lambda e: e.is_private))
async def handler(event):
    args = event.message.text.split(' ', 1)
    if len(args) == 1:
        await event.respond(strings['howto_add_session'])
        return
    user_data = database.find_one({"chat_id": event.chat_id})
    data = {
        'session': args[1]
    }
    uclient = TelegramClient(StringSession(data['session']), API_ID, API_HASH)
    await uclient.connect()
    if not uclient.is_user_authorized():
        await event.respond(strings['session_invalid'])
        return
    database.update_one({'_id': user_data['_id']}, {'$set': data})
@bot.on(events.NewMessage)
async def handler(event):
    if event.message.contact:
        if event.message.contact.user_id==event.chat.id:
            await handle_usr(event.message.contact, event)
        else:
            await event.respond(strings['wrong_phone'])
        raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"^(-?\d+)\.(\d+)$", func=lambda e: e.is_private))
async def handler(event):
    msg = await event.respond('please wait..')
    user_data = database.find_one({"chat_id": event.chat_id})
    if user_data['session'] is None:
        await msg.edit(strings['need_login'])
        return
    uclient = TelegramClient(StringSession(user_data['session']), API_ID, API_HASH)
    await uclient.connect()
    if not uclient.is_user_authorized():
        await msg.edit(strings['session_invalid'])
        return
    try:
        chat = await uclient.get_input_entity(event.pattern_match[1])
    except Exception as e:
        await msg.edit('Error: '+repr(e))
        return
    to_chat = await event.get_sender()
    message = await uclient.get_messages(chat, ids=event.pattern_match[2])
    if message is None:
        await msg.edit(strings['msg_404'])
        return
    elif message.grouped_id:
        gallery = await get_gallery(message.chat_id, message.id)
        album = list()
        for _ in gallery:
            tk_d = TimeKeeper('Downloading')
            album.append(await msg.download_media(progress_callback=lambda c,t:callback(c,t,tk_d,msg)))
        tk_u = TimeKeeper('Uploading')
        await bot.send_file(to_chat, album, caption=msg.message, progress_callback=lambda c,t:callback(c,t,tk_u,msg))
        for file in album:
            os.unlink(file)
    elif msg.media is not None:
        tk_d = TimeKeeper('Downloading')
        file = await msg.download_media(progress_callback=lambda c,t:callback(c,t,tk_d,msg))
        tk_u = TimeKeeper('Uploading')
        await uclient.send_file(to_chat, file, caption=msg.message, progress_callback=lambda c,t:callback(c,t,tk_u,msg))
        os.unlink(file)
    else:
        await uclient.send_message(to_chat, msg.message)

with bot:
    bot.run_until_disconnected()

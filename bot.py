import telebot
import cherrypy
from map import Route, Step
from telebot import types
import requests
import os
import config
import traceback
import sys
import botan

WEBHOOK_HOST = '37.140.195.62'
WEBHOOK_PORT = 8443  # 443, 80, 88 или 8443 (порт должен быть открыт!)
WEBHOOK_LISTEN = '0.0.0.0'  # На некоторых серверах придется указывать такой же IP, что и выше

WEBHOOK_SSL_CERT = './webhook_cert.pem'  # Путь к сертификату
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'  # Путь к приватному ключу

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % config.TELEGRAM_TOKEN

bot = telebot.TeleBot(config.TELEGRAM_TOKEN)


class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        try:
            if 'content-length' in cherrypy.request.headers and \
                            'content-type' in cherrypy.request.headers and \
                            cherrypy.request.headers['content-type'] == 'application/json':
                length = int(cherrypy.request.headers['content-length'])
                json_string = cherrypy.request.body.read(length).decode("utf-8")
                update = telebot.types.Update.de_json(json_string)
                # Эта функция обеспечивает проверку входящего сообщения
                bot.process_new_updates([update])
                f = open('events.txt', 'a')
                f.write('Ok!\n')
                f.close()
                return ''
            else:
                raise cherrypy.HTTPError(403)
        except Exception:
            hr = '*'*50
            ex = ''.join(traceback.format_exception(*sys.exc_info()))
            string = 'Error!\n{}\n{}\n'.format(ex, hr)
            f = open('events.txt', 'a')
            f.write(string)
            f.close()

rt = {}


@bot.message_handler(commands=['start'])
def get_greeting(message):
    chat_id = message.chat.id
    markup = get_buttons({'new_route': 'Новый маршрут'})
    bot.send_message(chat_id, 'Привет, я бот-навигатор.\nЯ помогу тебе построить пешеходный маршрут, а также дам '
                              'подсказки в виде карты и панорамы.', reply_markup=markup)
    botan.track(config.BOTAN_KEY, chat_id, message, 'Старт')


@bot.callback_query_handler(func=lambda call: call.data == 'new_route')
def get_start(call):
    chat_id = call.message.chat.id
    msg = bot.send_message(chat_id, 'Для начала напиши откуда мне построить маршрут или пришли свою геолокацию')
    bot.register_next_step_handler(msg, get_end)
    botan.track(config.BOTAN_KEY, chat_id, call.message, 'Новый маршрут')


def get_end(message):
    chat_id = message.chat.id
    if message.content_type == 'location':
        rt['start'] = '{}, {}'.format(message.location.latitude, message.location.longitude)
    else:
        rt['start'] = message.text
    msg = bot.send_message(chat_id, 'Отлично! А теперь напиши куда пойдем. Геолокация тоже сойдет.')
    bot.register_next_step_handler(msg, get_route)


def get_route(message):
    chat_id = message.chat.id
    if message.content_type == 'location':
        rt['end'] = '{}, {}'.format(message.location.latitude, message.location.longitude)
    else:
        rt['end'] = message.text
    route = Route(chat_id, rt['start'], rt['end'])
    route.add_route_to_db()
    markup = get_buttons({'next': 'Вперед!', 'new_route': 'Этот маршрут мне не подходит!',
                          'developer': 'Написать разработчику'})
    send_images(chat_id, route.get_static_map())
    msg = 'Маршрут построен. Я буду присылать тебе участки маршрута поэтапно.\nЕсли ты запутаешься в пути, нажми на ' \
          'кнопку "Помощь" и я помогу тебе вернуться на маршрут.\nКогда достигнешь конца этапа нажимай на ' \
          'кнопку дальше.\nДистанция: {}\nДлительность: {}'.format(route.distance, route.duration)
    bot.send_message(chat_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'next')
def get_next_step(call):
    chat_id = call.message.chat.id
    route = Route(chat_id)
    step = route.get_step_from_db()
    if step:
        send_images(chat_id, step.get_street_view(), step.get_static_map())
        markup = get_buttons({'next': 'Дальше', 'send_help': 'Помощь', 'new_route': 'Новый маршрут'})
        msg = '{}\nПродолжайте движение {} примерно {}'.format(step.instructions, step.distance, step.duration)
        bot.send_location(chat_id, step.end[0], step.end[1])
        step.get_passed_step()
    else:
        markup = get_buttons({'new_route': 'Новый маршрут', 'developer': 'Написать разработчику'})
        msg = 'Вы достигли пункта назначения'
    try:
        bot.send_message(chat_id, msg, parse_mode='HTML', reply_markup=markup)
    except:
        bot.send_message(chat_id, msg, reply_markup=markup)
    botan.track(config.BOTAN_KEY, chat_id, call.message, 'Дальше')


@bot.callback_query_handler(func=lambda call: call.data == 'send_help')
def send_help(call):
    chat_id = call.message.chat.id
    msg = bot.send_message(chat_id, 'Отправь мне свою геолокацию и я пришлю снимок и карту, которые должны тебе помочь.')
    bot.register_next_step_handler(msg, send_direction)
    botan.track(config.BOTAN_KEY, chat_id, call.message, 'Помощь')


def send_direction(message):
    chat_id = message.chat.id
    route = Route(chat_id)
    step = route.get_step_from_db(-1)
    start = (message.location.latitude, message.location.longitude)
    aux_route = Route(chat_id, start, step.end)
    aux_step = aux_route.steps[0]
    send_images(chat_id, aux_step.get_street_view(), aux_route.get_static_map())
    msg = 'Надеюсь все понятно. Обращайся если что.'
    markup = get_buttons({'next': 'Дальше', 'send_help': 'Помощь', 'new_route': 'Новый маршрут'})
    bot.send_message(chat_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'developer')
def developer(call):
    chat_id = call.message.chat.id
    msg = 'Все вопросы, пожелания, сведения об ошибках направлять сюда: @andkhom'
    markup = get_buttons({'new_route': 'Новый маршрут'})
    bot.send_message(chat_id, msg, reply_markup=markup)
    botan.track(config.BOTAN_KEY, chat_id, call.message, 'Разработчик')


def get_buttons(buttons):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key in buttons:
        button = types.InlineKeyboardButton(buttons[key], callback_data=key)
        markup.add(button)
    return markup


def send_images(chat_id, *args):
    for i, arg in enumerate(args):
        p = requests.get(arg)
        path = 'images\{}_{}.jpg'.format(str(i), str(chat_id))
        out = open(path, 'wb')
        out.write(p.content)
        out.close()
        bot.send_photo(chat_id, open(path, 'rb'))
        os.remove(path)

# Снимаем вебхук перед повторной установкой
bot.remove_webhook()

# Ставим заново вебхук
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                certificate=open(WEBHOOK_SSL_CERT, 'r'))

cherrypy.config.update({
    'server.socket_host': WEBHOOK_LISTEN,
    'server.socket_port': WEBHOOK_PORT,
    'server.ssl_module': 'builtin',
    'server.ssl_certificate': WEBHOOK_SSL_CERT,
    'server.ssl_private_key': WEBHOOK_SSL_PRIV
})

# Запуск
if __name__ == '__main__':
    cherrypy.quickstart(WebhookServer(), WEBHOOK_URL_PATH, {'/': {}})

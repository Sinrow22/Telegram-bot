# -*- coding: utf-8 -*-

import os
import time
import sys
import vk_api
import telebot
import configparser
import logging
import threading
from time import sleep
from telebot import types
from telebot.types import InputMed
SINGLE_RUN = False

import bot_discuss_telegramm as mat


# Считываем настройки
config_path = os.path.join(sys.path[0], 'settings.txt')
config = configparser.ConfigParser()
config.read(config_path)
LOGIN = config.get('VK', 'LOGIN')
PASSWORD = config.get('VK', 'PASSWORD')
DOMAIN = config.get('VK', 'DOMAIN')
COUNT = config.get('VK', 'COUNT')
VK_TOKEN = config.get('VK', 'TOKEN', fallback=None)
BOT_TOKEN = config.get('Telegram', 'BOT_TOKEN')
CHANNEL = config.get('Telegram', 'CHANNEL')
INCLUDE_LINK = config.getboolean('Settings', 'INCLUDE_LINK')
PREVIEW_LINK = config.getboolean('Settings', 'PREVIEW_LINK')

# Символы, на которых можно разбить сообщение
message_breakers = [':', ' ', '\n']
max_message_length = 4091
max_message_length_capt = 1020


# Инициализируем телеграмм бота
bot = telebot.TeleBot(BOT_TOKEN)


# Получаем данные из vk.com
def get_data(domain_vk, count_vk):
    global LOGIN
    global PASSWORD
    global VK_TOKEN
    global config
    global config_path

    if VK_TOKEN is not None:
        vk_session = vk_api.VkApi(LOGIN, PASSWORD, VK_TOKEN)
        vk_session.auth(token_only=True)
    else:
        vk_session = vk_api.VkApi(LOGIN, PASSWORD)
        vk_session.auth()

    new_token = vk_session.token['access_token']
    if VK_TOKEN != new_token:
        VK_TOKEN = new_token
        config.set('VK', 'TOKEN', new_token)
        with open(config_path, "w") as config_file:
            config.write(config_file)

    vk = vk_session.get_api()
    # Используем метод wall.get из документации по API vk.com
    response = vk.wall.get(domain=domain_vk, count=count_vk)
    return response


# Проверяем данные по условиям перед отправкой
def check_posts_vk():
    global DOMAIN
    global COUNT
    global INCLUDE_LINK
    global bot
    global config
    global config_path

    response = get_data(DOMAIN, COUNT)
    response = reversed(response['items'])

    for post in response:

        # Читаем последний извесный id из файла
        id = config.get('Settings', 'LAST_ID')

        # Сравниваем id, пропускаем уже опубликованные
        if int(post['id']) <= int(id):
            continue

        print('------------------------------------------------------------------------------------------------')
        print(post)

        # Текст
        text = post['text']

        # Проверяем есть ли что то прикрепленное к посту
        images = []
        links = []
        attachments = []
        if 'attachments' in post:
            attach = post['attachments']
            for add in attach:
                if add['type'] == 'photo':
                    img = add['photo']
                    images.append(img)
                elif add['type'] == 'audio':
                    # Все аудиозаписи заблокированы везде, кроме оффицальных приложений
                    continue
                elif add['type'] == 'video':
                    video = add['video']
                    if 'player' in video:
                        links.append(video['player'])
                else:
                    for (key, value) in add.items():
                        if key != 'type' and 'url' in value:
                            attachments.append(value['url'])

        if INCLUDE_LINK:
            post_url = "https://vk.com/" + DOMAIN + "?w=wall" + \
                str(post['owner_id']) + '_' + str(post['id'])
            links.insert(0, post_url)
        text = '\n'.join([text] + links)
        # send_posts_text(text)
        
        if len(images) > 0:
            image_urls = list(map(lambda img: max(
                img["sizes"], key=lambda size: size["type"])["url"], images))
            print(image_urls)
            if len(text) >= max_message_length_capt:
                send_posts_text(text)
                bot.send_media_group(CHANNEL, map(lambda url: InputMediaPhoto(url), image_urls))
            else:
                bot.send_media_group(CHANNEL, map(lambda url: InputMediaPhoto(url, caption=text), image_urls))

        else:
            send_posts_text(text)

        # Проверяем есть ли репост другой записи
        if 'copy_history' in post:
            copy_history = post['copy_history']
            copy_history = copy_history[0]
            print('--copy_history--')
            print(copy_history)
            text = copy_history['text']
            send_posts_text(text)

            # Проверяем есть ли у репоста прикрепленное сообщение
            image = []
            if 'attachments' in copy_history:
                copy_add = copy_history['attachments']
                copy_add = copy_add[0]

    # tсли это картинки
                if copy_add['type'] == 'photo':
                    attach = copy_history['attachments']
                    for img in attach:
                        if image in attach:
                            image = img['photo']
                            send_posts_img(image)
                        else:
                            continue
                if copy_add['type'] == 'video':
                    continue
                # Если это ссылка
                if copy_add['type'] == 'link':
                    link = copy_add['link']
                    text = link['title']
                   # send_posts_text(text)
                    img = link['photo']
                   # send_posts_img(img, caption=text)
                    url = link['url']
                    links.insert(0, url)
                    text = '\n'.join([text] + links)
                    #send_posts_img(img, caption=text)
                    send_posts_img(img, text)
                    # send_posts_text(url)

             
        # Записываем id в файл
        config.set('Settings', 'LAST_ID', str(post['id']))
        with open(config_path, "w") as config_file:
            config.write(config_file)


# Отправляем посты в телеграмм


# Текст
def send_posts_text(text):
    global CHANNEL
    global PREVIEW_LINK
    global bot

    if text == '':
        print('no text')
    else:
        # В телеграмме есть ограничения на длину одного сообщения в 4091 символ, разбиваем длинные сообщения на части
        for msg in split(text):
            bot.send_message(CHANNEL, msg, disable_web_page_preview=not PREVIEW_LINK)

def split1020(text):
    global message_breakers
    global max_message_length_capt

    if len(text) >= max_message_length_capt:
        last_index = max(
            map(lambda separator: text.rfind(separator, 0, max_message_length_capt), message_breakers))
        good_part = text[:last_index]
        bad_part = text[last_index + 1:]
        return [good_part] + split(bad_part)
    else:
        return [text]


def split(text):
    global message_breakers
    global max_message_length

    if len(text) >= max_message_length:
        last_index = max(
            map(lambda separator: text.rfind(separator, 0, max_message_length), message_breakers))
        good_part = text[:last_index]
        bad_part = text[last_index + 1:]
        return [good_part] + split(bad_part)
    else:
        return [text]


# Изображени
def send_posts_img(img):
    global bot
    
    # Находим картинку с максимальным качеством
    url = max(img["sizes"], key=lambda size: size["type"])["url"]
    bot.send_photo(CHANNEL, url)

# Изображения capt
def send_posts_img_capt(img, text):
    global bot
    
    # Находим картинку с максимальным качеством
    url = max(img["sizes"], key=lambda size: size["type"])["url"]
    bot.send_photo(CHANNEL, url, caption=text)


# *------------------
@bot.message_handler(commands=['start'])



#---------------------------------------------------------------------------



def welcome(message):
    sti = open('welcome.webp', 'rb')
    bot.send_sticker(message.chat.id, sti)


    #Создание кнопок и приветствие
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("🎓Кафедра ПИиВТ🎓")
    item2 = types.KeyboardButton("⚠Полезные ссылки⚠")
    item3 = types.KeyboardButton("💻Разработчики💻")
   

 
    markup.add(item1, item2, item3)
 
    bot.send_message(message.chat.id, "Добро пожаловать, {0.first_name}!\nЯ - <b>{1.first_name}</b>, дам тебе основную информацию о кафедре ПИиВТ ".format(message.from_user, bot.get_me()),
        parse_mode='html', reply_markup=markup)
 
@bot.message_handler(content_types=['text'])



#---------------------------------------------------------------------------



def func(message):
    if message.chat.type == 'private':
        if message.text == '🎓Кафедра ПИиВТ🎓':
 
 			# Создание кнопок под текстом
            markup = types.InlineKeyboardMarkup(row_width=3)
            item1 = types.InlineKeyboardButton("🏢О кафедре ПИиВТ🏢", callback_data='1')
            item2 = types.InlineKeyboardButton("👨‍🏫Преподавательский👨‍🏫 состав", callback_data='2')
            item3 = types.InlineKeyboardButton("🧠Преподаваемые дисциплины🧠", callback_data='3')
            #Кнопка под чат(Вставить нужную ссылку)
            item4 = types.InlineKeyboardButton("💬Общий чат💬", url="https://t.me/+U87b6tNPEd1iZGNi")
 
            markup.add(item1, item2, item3, item4)
 
            bot.send_message(message.chat.id, 'Что вы хотите узнать?', reply_markup=markup)

       
        elif message.text == "⚠Полезные ссылки⚠":
            bot.send_message(message.chat.id, "Телефон преподавательской кафедры ПИВТ 441/2: +7 (812) 305-12-56, доб. 2107\nСсылки:\nСайт кафедры - https://pivt.sut.ru/\nЛК  - https://lk.sut.ru/cabinet/\nЛМС - https://lms.spbgut.ru/")

        else:
            bot.send_message(message.chat.id, 'Введите корректную команду')


#---------------------------------------------------------------------------



@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:

        	#Работа с кнопками под текстом
            if call.data == '1':
                bot.send_message(call.message.chat.id, 'Кафедра программной инженерии и вычислительной техники (ПИВТ) начала свое существование еще в 1967 году.\nПервоначальное название звучало как кафедра импульсной и вычислительной техники (ИВТ) и ставила своей целью обеспечение базовой подготовки студентов практически всех факультетов института в области цифровой полупроводниковой элементной базы и программного обеспечения ЭВМ.\nЗатем, до 2013 года, кафедра носила новое название – кафедра цифровой вычислительной техники и информатики (ЦВТиИ).\nИ уже в 2013 году получила свое нынешнее название.\nВ настоящее время штат кафедры составляет свыше 20 единиц профессорско-преподавательского состава и 4 единицы учебно-вспомогательного персонала.\nНа кафедре работают шесть профессоров и семь доцентов.')

            elif call.data == '2':
               
                bot.send_message(call.message.chat.id, 'Анохин\nЮрий Владимирович\nСтарший преподаватель кафедры ПИиВТ\n\nАхметова\nЮлия Славовна\nАссистент кафедры ПИиВТ\n\nБелая\nТатьяна Иоанновна\nКандидат технически наук\nДоцент кафедры ПИиВТ\n\nБерезин\nАлександр Юрьевич\nАссистент кафедры ПИиВТ\n\nБирюков\nМихаил Александрович\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nБобровский\nВадим Игоревич\nДоктор технических наук, доцент\nПрофессор кафедры ПИиВТ\n\nВоронцова\nИрина Олеговна\nСтарший преподаватель кафедры ПИиВТ\n\nДагаев\nАлександр Владимирови\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nЕрмакова\nТатьяна Вячеславовна\nСтарший преподаватель кафедры ПИиВТ\n\nЕрофеев\nСергей Анатольевич\nКандидат физико-математических наук\nДоцент кафедры ПИиВТ\n\nЖуравель\nЕвгений Павлович\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nРуслан Валентинови\nДоктор технических наук, доцент\nЗаведующий кафедрой ПИиВТ\n\nКоробов\nСергей Александрович\nКандидат психологических наук\nДоцент кафедры ПИиВТ\n\nКраева\nЕкатерина Витальевна\nАссистент кафедры ПИиВТ\n\nЛукша\nИван Иванович\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nНеелова\nОльга Леонидовна\nСтарший преподаватель кафедры ПИиВТ\n\nНовоженин\nАлександр Васильевич\nАссистент кафедры ПИиВТ\n\nОвчинников\nАнтон Олегович\nАссистент кафедры ПИиВТ\n\nОкунева\nДарина Владимировна\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nПачин\nАндрей Владимирович\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nПетрова\nОльга Борисовна\nЗаведующая лабораторией кафедры ПИиВТ, Старший преподаватель кафедры ПИиВТ\n\nПомогалова\nАльбина Владимировна\nАссистент кафедры ПИиВТ\n\nРезников\nБогдан Константинович\nПреподаватель кафедры ПИиВТ\n\nСавельев\nИгорь Леонидович\nСтарший преподаватель кафедры ПИиВТ\n\nСтепаненков\nГригорий Викторович\nАссистент кафедры ПИиВТ\n\nФомин\nВладимир Владимирович\nДоктор технических наук, профессор\nПрофессор кафедры ПИиВТ\n\nФутахи Абдо\nАхмед Хасан\nКандидат технических наук\nДоцент кафедры ПИиВТ\n\nХазиев\nНургаян Нурутдинович\nСтарший преподаватель кафедры ПИиВТ\n\nШарлаева\nМария Владимировна\nАссистент кафедры ПИиВТ')

            elif call.data == '3':
                bot.send_message(call.message.chat.id, '➤Web-технологии\n\n➤Алгоритмические основы программной инженерии\n\n➤Алгоритмы и структуры данных\n\n➤Аппаратные средства вычислительной техники\n\n➤Архитектура вычислительных систем\n\n➤Базы данных\n\n➤Введение в программную инженерию\n\n➤Вычислительная и микропроцессорная техника\n\n➤Вычислительная техника\n\n➤Использование вычислительной и микропроцессорной техники в оптико-электронном прибо-ростроении\n\n➤Конструирование ПО\n\n➤Логическое и функциональное программирование\n\n➤Математические методы и вычислительные алгоритмы современных систем связи\n\n➤Машинно-зависимые языки программирования\n\n➤Микропроцессорные устройства\n\n➤Объектно-ориентированное программирование\n\n➤Операционные системы\n\n➤Операционные системы и сети\n\n➤Программирование\n\n➤Программирование в 1С\n\n➤Программирование в среде 1С\n\n➤Программирование устройств и приложений киберфизических систем\n\n➤Программное обеспечение современных систем связи\n\n➤Проектирование и архитектура программных систем\n\n➤Разработка Java приложений управления телекоммуникациями\n\n➤Разработка Java-приложений управления телекоммуникациями\n\n➤Разработка и анализ требований проектирования программного обеспечения\n\n➤Системы искусственного интеллекта\n\n➤Тестирование ПО\n\n➤Тестирование программного обеспечения\n\n➤Технологии и методы программирования\n\n➤Технологии программирования\n\n➤Технологии разработки программного обеспечения\n\n➤Управление программными проектами')

 
            # remove inline buttons
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                reply_markup=None)
 

 
    except Exception as e:
        print(repr(e))
 

def runBot():
    bot.polling(none_stop=True)

def runChecker():
    if not SINGLE_RUN:
        while True:
            check_posts_vk()
            # Пауза в 4 минуты перед повторной проверкой
            logging.info('[App] Script went to sleep.')
            time.sleep(60)
    else:
        check_posts_vk()
    logging.info('[App] Script exited.\n')

# *------------------

if __name__ == '__main__':
   # Избавляемся от спама в логах от библиотеки requests
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    # Настраиваем наш логгер
    logging.basicConfig(format='[%(asctime)s] %(filename)s:%(lineno)d %(levelname)s - %(message)s', level=logging.INFO,
                        filename='bot_log.log', datefmt='%d.%m.%Y %H:%M:%S')
    t1 = threading.Thread(target=runBot)
    t2 = threading.Thread(target=runChecker)
  # starting thread 1
    t1.start()
  # starting thread 2
    t2.start()

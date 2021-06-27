import os
import time
import eventlet
import requests
import logging
import telebot
import threading
from database import Subscribers
from variables import Variables

# Инициализируем соединение с БД
db_variables = Variables("subscribers.db")

#Инициализируем переменные
URL_VK = db_variables.get_variable_value('URL_VK')[0]
BOT_TOKEN = db_variables.get_variable_value('BOT_TOKEN')[0]
access_token = db_variables.get_variable_value('VK_TOKEN')[0]

#CHANNEL_NAME = '431457103' мой id

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализируем соединение с БД
db = Subscribers("subscribers.db")


# Команда активации подписки
@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    if (not db.subscriber_exists(message.from_user.id)):
        # Если юзера нет в базе, то добавляем его
        db.add_subscriber(message.from_user.id)
        bot.send_message(message.chat.id, 'Подписка успешно оформлена!\nЖдите горячие обновления🔥')
    else:
        # Если юзер присутствует в базе, то обновляем его статус подписки
        db.update_subscription(message.from_user.id, True)
        bot.send_message(message.chat.id, 'Подписка успешно продлена!\nСпасибо, что остаётесь с нами')


# Команда отписки
@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(message):
    if (not db.subscriber_exists(message.from_user.id)):
        # Если юзера нет в базе, то добовляем его c неактивной подпиской (запоминаем)
        db.add_subscriber(message.from_user.id, False)
        bot.send_message(message.chat.id, 'Вы не подписаны на обновления')
    else:
        # Если юзер присутствует в базе, то обновляем его статус подписки
        db.update_subscription(message.from_user.id, False)
        bot.send_message(message.chat.id, 'Очень жаль, что вы отписались. Будем ждать вас снова!')


# Получаем данные каждого поста в json формате
def get_data(groups_name):
    timeout = eventlet.Timeout(10)
    try:
        feed = requests.get(URL_VK, params={
            'domain': groups_name,
            'count': 5,
            'v': 5.126,
            'access_token': access_token
        })
        return feed.json()
    except eventlet.timeout.Timeout:
        logging.warning('Got Timeout while retrieving VK JSON data. Cancelling...')
        return None
    finally:
        timeout.cancel()


# Отправляем ссылку на пост для каждого подписанного пользователя
def send_new_posts(items, last_id, groups_name):
    # Получаем список подписчиков бота (те у которых статут подписки True)
    subscriptions = db.get_subscriptions()

    # Проверяем, является ли проверяемый пост новее того, который был записан в предыдущий раз
    # id новго поста больше, чем id старого
    for item in items:
        if item['id'] <= last_id:
            break
        link = 'https://vk.com/{!s}?w=wall{!s}_{!s}'.format(groups_name, item['owner_id'], item['id'])
        # Подключаемся к базе, и отправляем ссылку всем подписавшимся пользователям
        for s in subscriptions:
            bot.send_message(s[1], link)
        # Спим секунду, чтобы избежать разного рода ошибок и ограничений (на всякий случай!)
        time.sleep(1)
    return


# Парсим новые записи, и отправляем в телеграм
def check_new_posts_vk(groups_name):
    # Пишем текущее время начала
    logging.info('[VK] Started scanning for new posts')
    '''Проверим, существует ли файл .txt с id группы. 
            Если НЕТ, то создаём такой файл, и записываем туда id
            Если ДА, то запишем в файл те значения, которых там нет'''
    if not os.path.exists(f'groups_id/{groups_name}_id.txt'):
        with open(f'groups_id/{groups_name}_id.txt', 'wt') as file:
            try:
                fresh_posts_id = []
                feed = get_data(groups_name)
                posts = feed['response']['items']
                for post in posts:
                    fresh_id = post['id']
                    fresh_posts_id.append(fresh_id)
                last_id = fresh_posts_id[4]
                print(fresh_posts_id)
                print(last_id)

                # Если ранее случился таймаут, пропускаем итерацию. Если всё нормально - парсим посты.
                if feed is not None:
                    # 0 - это какое-то число, так что начинаем с 1
                    entries = feed['response']['items'][1:]
                    try:
                        # Если пост был закреплен, пропускаем его
                        tmp = entries[0]['is_pinned']
                        # Отправляем сообщение
                        send_new_posts(entries[1:], last_id, groups_name)
                    except KeyError:
                        send_new_posts(entries, last_id, groups_name)
                    # Записываем новую "верхушку" группы, чтобы не повторяться
                    with open(f'groups_id/{groups_name}_id.txt', 'wt') as file:
                        try:
                            tmp = entries[0]['is_pinned']
                            # Если первый пост - закрепленный, то сохраняем ID второго
                            file.write(str(entries[1]['id']))
                            logging.info('New last_id (VK) is {!s}'.format((entries[1]['id'])))
                        except KeyError:
                            file.write(str(entries[0]['id']))
                            logging.info('New last_id (VK) is {!s}'.format((entries[0]['id'])))
            except Exception as ex:
                logging.error('Exception of type {!s} in check_new_post(): {!s}'.format(type(ex).__name__, str(ex)))
                pass
            logging.info('[VK] Finished scanning')
            return
    else:
        with open(f'groups_id/{groups_name}_id.txt', 'rt') as file:
            last_id = int(file.read())
            if last_id is None:
                logging.error('Could not read from storage. Skipped iteration.')
                return
            logging.info('Previous last_id is {!s}'.format(last_id))
        try:
            feed = get_data(groups_name)
            # Если ранее случился таймаут, пропускаем итерацию. Если всё нормально - парсим посты.
            if feed is not None:
                # 0 - это какое-то число, так что начинаем с 1
                entries = feed['response']['items'][1:]
                try:
                    # Если пост был закреплен, пропускаем его
                    tmp = entries[0]['is_pinned']
                    send_new_posts(entries[1:], last_id, groups_name)
                except KeyError:
                    send_new_posts(entries, last_id, groups_name)
                # Записываем новую "верхушку" группы, чтобы не повторяться
                with open(f'groups_id/{groups_name}_id.txt', 'wt') as file:
                    try:
                        tmp = entries[0]['is_pinned']
                        # Если первый пост - закрепленный, то сохраняем ID второго
                        file.write(str(entries[1]['id']))
                        logging.info('New last_id (VK) is {!s}'.format((entries[1]['id'])))
                    except KeyError:
                        file.write(str(entries[0]['id']))
                        logging.info('New last_id (VK) is {!s}'.format((entries[0]['id'])))
        except Exception as ex:
            logging.error('Exception of type {!s} in check_new_post(): {!s}'.format(type(ex).__name__, str(ex)))
            pass
        logging.info('[VK] Finished scanning')
        return

# Задаём частоту включения парсинга
def pars(groups_name):
    while True:
        for i in groups_name:
            check_new_posts_vk(i)
        time.sleep(60 * 3)

# Создаём полинг
def pull():
    bot.infinity_polling()


if __name__ == '__main__':
    # Перечислим группы, из которых нам интересны посты
    groups_name = ['fa_sales', 'sneakersale', 'hotpricesneakers', 'dealfinder', 'firstretailsoupe',
                   'getsneakers',
                   'buyforboy', 'crazyoffer', 'fa_perfumes', 'sneakersearch', 'dealfinderch', 'cozysale',
                   'dontsellsneakers']
    # Избавляемся от спама в логах от библиотеки requests
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    # Настраиваем наш логгер
    logging.basicConfig(format='[%(asctime)s] %(filename)s:%(lineno)d %(levelname)s - %(message)s', level=logging.INFO,
                        filename='bot_log.log', datefmt='%d.%m.%Y %H:%M:%S')

    # Создаём 2 "асинхронных" потока
    thread1 = threading.Thread(target=pars, args=(groups_name,))
    thread2 = threading.Thread(target=pull, daemon=True)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

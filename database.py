import sqlite3


class Subscribers:

    def __init__(self, database_file):
        # Подключаемся к БД и сохраняем курсор соединения
        self.connection = sqlite3.connect(database_file,check_same_thread=False)
        self.cursor = self.connection.cursor()

    def get_subscriptions(self, status=True):
        # Получаем всех активных подписчиков (которые купили подписку) бота
        with self.connection:
            return self.cursor.execute('SELECT * FROM `subscribe_status` WHERE `status` = ?', (status,)).fetchall()

    def subscriber_exists(self, user_id):
        # Проверяем есть ли юзер в базе
        with self.connection:
            result = self.cursor.execute('SELECT * FROM `subscribe_status` WHERE `user_id` = ?',
                                         (user_id,)).fetchall()
            return bool(len(result))

    def add_subscriber(self, user_id, status=True):
        # Добавление нового подписчика
        with self.connection:
            return self.cursor.execute('INSERT INTO `subscribe_status` (`user_id`,`status`) VALUES (?,?)',
                                       (user_id, status))

    def update_subscription(self, user_id, status):
        # Обновление статуса подписчика
        with self.connection:
            return self.cursor.execute('UPDATE `subscribe_status` SET `status` = ? WHERE `user_id` = ?',
                                       (status, user_id))

    def close(self):
        # Закрываем соединение с БД
        self.connection.close()

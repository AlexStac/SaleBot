import sqlite3

class Variables:

    def __init__(self, database_file):
        # Подключаемся к БД и сохраняем курсор соединения
        self.connection = sqlite3.connect(database_file,check_same_thread=False)
        self.cursor = self.connection.cursor()

    def get_variable_value(self, variable):
        # Получаем значение переменной
        with self.connection:
            return self.cursor.execute('SELECT `value` FROM `variables` WHERE `name` = ?', (variable,)).fetchone()

    def close(self):
        # Закрываем соединение с БД
        self.connection.close()

#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
    Code was writen by Oleg Volkov https://github.com/oavolkov

"""
import json
import requests.exceptions
from yobit_bot_functions import *
from yobit_bot_main_flow import main_flow


# -----------------------------------  Главный цикл  -----------------------------------
try:
    # Создаем объект для методов API-интерфейса биржи
    y_api = yobit.YobitAPI(CONFIG['API_KEY'], CONFIG['API_SECRET'], CONFIG['API_NONCEPATH'])

    # # Получаем список валют по всем валютным парам
    # currencies = get_currencies(CONFIG['MARKETS'])

    # Получаем настройки валютных пар по всем валютным парам
    pairs_info = get_pairs_info(y_api)

    # Бесконечный цикл процесса - основная логика
    while True:
        timeout = 10  # Задержка между итерациями
        # Проходим по каждой паре из определенных к торгам
        for pair in CONFIG['MARKETS']:
            # ---------------------------------------------------------
            # Вызываем главную функцию, реализующую аглоритм трейдинга
            # ---------------------------------------------------------
            try:
                main_flow(y_api, pair, pairs_info)

            except ScriptError as serr:
                print(serr)

            except ScriptQuitCondition as sqc:
                print(sqc)

            except requests.HTTPError as httperr:
                timeout = 10
                print('Ошибка получения ответа с биржи: [' + type(httperr).__name__ + ']', httperr)

            except json.decoder.JSONDecodeError as jsonerr:
                timeout = 10
                print('Ошибка декодирования ответа с биржи: [' + type(jsonerr).__name__ + ']', jsonerr)

            except yobit.YobitException as yerr:
                print('Ошибочный ответ с биржи: [' + type(yerr).__name__ + ']', yerr)

            finally:
                print('')

        print('-' * 15, '\n')
        time.sleep(timeout)

except KeyboardInterrupt:
    pass

except Exception as errex:
    print('General exception: [' + type(errex).__name__ + ']', errex)

exit()

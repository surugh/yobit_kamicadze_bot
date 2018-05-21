#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import tApi
import algo
import sys
import time

try:
    alt_balance = tApi.call_api(method="getInfo")['return']['funds'].get(tApi.BASE.lower(), 0)
    if alt_balance > 0:
        decision = input("""
            {amount:0.8f} {curr1} :Баланс
            Продавать по курсу {rate:0.8f} ?
            {wanna_get:0.8f} {curr2} :Всего-ком

            Потрачено в последнем BUY ордере
            {spended:0.8f} {curr2} :Всего+ком

            C минимальным профитом
            {profit:0.8f} {curr2}
            Введите Д/Y или Н/N
        """.format(
            amount=alt_balance,
            curr1=tApi.BASE,
            curr2=tApi.QUOTE,
            wanna_get=tApi.wanna_get() - tApi.wanna_get() * tApi.stock_fee(),
            spended=tApi.spended() * 1,
            rate=tApi.wanna_get() / alt_balance,
            profit=tApi.profit()
        ))
        if decision in ('N', 'n', 'Н', 'н'):
            print("Тогда избавьтесь от {curr} и перезапустите бота".format(curr=tApi.BASE))
            sys.exit(0)

except Exception as errex:
    print(str(errex))

while True:
    algo.main_flow()
    time.sleep(1)

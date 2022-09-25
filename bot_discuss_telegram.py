#from asyncore import dispatcher
#import token
from aiogram import Bot, types 
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

import os
import json
import string  


#TOKEN = "5450838618:AAGeGs54LqmGMed5vxqXkcO_3yAGMOLOpOg"
bot = Bot(token=os.getenv('TOKEN'))

dp = Dispatcher(bot)

@dp.message_handler()
async def echo_send(message : types.Message):
    if { i.lower().translate(str.maketrans('', '', string.punctuation)) for i in message.text.split(' ') }\
        .intersection(set(json.load(open('mat.json')))) != set():
        await message.reply("Маты запрещены!")
        await message.delete()


        

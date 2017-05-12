#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Simple Bot thah look inside the database and see if the pokemon requested is appeared during the last scan
# This program is dedicated to the public domain under the CC0 license.
# First iteration made by eugenio412
# based on timerbot made inside python-telegram-bot example folder

# better on python3.4

'''please READ FIRST the README.md'''


import sys
if sys.version_info[0] < 3:
    raise Exception('Must be using Python 3.')

from telegram.ext import Updater, CommandHandler, Job, MessageHandler, Filters
from telegram import Bot
import logging
from datetime import datetime, timezone
import os
import errno
import json
import threading
import fnmatch
import DataSources
import Preferences
from geopy.geocoders import Nominatim
import Whitelist
from Stickers import sticker_list
import googlemaps

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
prefs = Preferences.UserPreferences()
jobs = dict()
geolocator = Nominatim()
telegramBot = None
gmaps_client = None

clearCntThreshold = 20
dataSource = None
ivAvailable = False

# User dependant - dont add
sent = dict()
locks = dict()
clearCnt = dict()

#pokemon:
pokemon_name = dict()
#move:
move_name = dict()

min_pokemon_id = 1
max_pokemon_id = 251

pokemon_blacklist = [10,13,16,19,21,29,32,39,41,46,48,54,60,90,92,98,116,118,120,161,163,165,167,177,183,194,198,220]

pokemon_rarity = [[],
    ["10", "13", "16", "19", "21", "29", "32", "41", "46", "48", "98", "133", "161", "163", "165", "167", "177", "183", "194", "198", "220"],
    ["14", "17", "20", "35", "39", "43", "52", "54", "60", "63", "69", "72", "79", "81", "90", "92", "96", "116", "118", "120", "122", "124", "129", "162", "166", "168", "170", "178", "187", "190", "209", "215", "216"],
    ["1", "4", "7", "8", "11", "12", "15", "18", "22", "23", "25", "27", "30", "33", "37", "42", "44", "47", "49", "50", "56", "58", "61", "66", "70", "74", "77", "84", "86", "88", "93", "95", "97", "99", "100", "102", "104", "109", "111", "117", "119", "123", "125", "127", "138", "140", "147", "152", "155", "158", "164", "169", "184", "185", "188", "191", "193", "195", "200", "202", "203", "204", "206", "207", "210", "211", "213", "217", "218", "221", "223", "224", "226", "227", "228", "231", "234"],
    ["2", "3", "5", "6", "9", "24", "26", "28", "31", "34", "36", "38", "40", "45", "51", "53", "55", "57", "59", "62", "64", "65", "67", "68", "71", "73", "75", "76", "78", "80", "82", "85", "87", "89", "91", "94", "101", "103", "105", "106", "107", "108", "110", "112", "113", "114", "121", "126", "130", "131", "134", "135", "136", "137", "139", "141", "142", "143", "148", "149", "153", "154", "156", "157", "159", "171", "176", "179", "180", "189", "205", "219", "229", "232", "237", "241", "242", "246", "247", "248"],
    ["83", "115", "128", "132", "144", "145", "146", "150", "151", "160", "172", "173", "174", "175", "181", "182", "186", "192", "196", "197", "199", "201", "208", "212", "214", "222", "225", "230", "233", "235", "236", "238", "239", "240", "243", "244", "245", "249", "250", "251"]
];

# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
def cmd_help(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (help).' % (userName, chat_id))
        return

    logger.info('[%s@%s] Sending help text.' % (userName, chat_id))

    pref = prefs.get(chat_id)
    if pref.get('language') == 'de':
        text = "*Der PoGo Chemnitz Bot beherrscht die folgenden Befehle:*\n\n" + \
        "*Allgemein*\n" + \
        "/start - Startet den Bot (z.B. nach dem Pausieren)\n" + \
        "/stop - Pausiert den Bot (nutze /start zum Fortsetzen)\n" + \
        "/lang de/en - Setzt die Sprache des Bots\n" + \
        "/clear - Setzt alle deine Einstellungen zurück\n" + \
        "/help - Zeigt eine Liste mit verfügbaren Befehlen\n\n" + \
        "*Pokémon-Filter*\n" + \
        "/add pokedexID - Fügt Pokémon mit der gegebenen ID zum Scanner hinzu\n" + \
        "/add pokedexID1 pokedexID2 ...\n" + \
        "/addbyrarity 1-5 - Fügt Pokémon it der gegebenen Seltenheit zum Scanner hinzu (1 sehr häufig - 5 ultra selten)\n" + \
        "/rem pokedexID - Entfernt Pokémon mit der gegebenen ID vom Scanner\n" + \
        "/rem pokedexID1 pokedexID2 ...\n" + \
        "/list - Zeigt eine Liste mit den überwachten Pokémon\n" + \
        "/iv 0-100 - Setzt den Minimalwert für IV-Werte in Prozent\n" +\
        "/wp 0-4760 - Setzt den Minimalwert für WP-Werte\n" +\
        "/pkmiv 0-100 - Setzt den Minimalwert für IV-Werte für ein bestimmtes Pokémon in Prozent\n" +\
        "/rempkmiv pokedexID - Setzt den Minimalwert für IV-Werte für ein bestimmtes Pokémon zurück\n" +\
        "/pkmwp 0-4760 - Setzt den Minimalwert für WP-Werte für ein bestimmtes Pokémon\n" +\
        "/rempkmwp pokedexID - Setzt den Minimalwert für WP-Werte für ein bestimmtes Pokémon zurück\n\n" +\
        "*Entfernungs-Filter*\n" + \
        "/location Addresse - Setzt die Suchposition gegeben als Text\n" +\
        "/radius km - Setzt den Suchradius in km\n" +\
        "/remloc - Setzt die Suchposition und den Radius zurück\n" +\
        "/pkmradius pokedexID km - Setzt den Suchradius für ein bestimmtes Pokémon in km\n" +\
        "/rempkmradius pokedexID - Setzt den Suchradius für ein bestimmtes Pokémon zurück\n\n" +\
        "*Benachrichtigungs-Einstellungen*\n" + \
        "/sendwithout true/false - Legt fest, ob Pokémon ohne IV/WP-Werte gesendet werden sollen\n" +\
        "/stickers true/false - Legt fest, ob Sticker gesendet werden sollen\n" +\
        "/maponly true/false - Legt fest, ob nur eine Karte gesendet werden soll (ohne zusätzliche Nachricht/Sticker)\n\n" +\
        "Hinweis: Du kannst ebenso die Suchposition festlegen, indem du einfach einen Positionsmarker sendest"

    else:
        text = "*The PoGo Chemnitz Bot knows the following commands:*\n\n" + \
        "*General*\n" + \
        "/start - Starts the bot (e.g. after pausing)\n" + \
        "/stop - Pauses the bot (use /start to resume)\n" + \
        "/lang de/en - Sets the language of the bot\n" + \
        "/clear - Resets all your settings\n" + \
        "/help - Shows a list of available commands\n\n" + \
        "*Pokémon filter*\n" + \
        "/add pokedexID - Adds Pokémon with the given ID to the scanner\n" + \
        "/add pokedexID1 pokedexID2 ...\n" + \
        "/addbyrarity 1-5 - Adds Pokémon with the given rarity to scanner (1 very common - 5 ultrarare)\n" + \
        "/rem pokedexID - Removes Pokémon with the given ID from the scanner\n" + \
        "/rem pokedexID1 pokedexID2 ...\n" + \
        "/list - Lists the watched Pokémon\n" + \
        "/iv 0-100 - Sets the minimum value for IVs given as percent\n" +\
        "/wp 0-4760 - Sets the minumum value for CP\n" +\
        "/pkmiv pokedexID 0-100 - Sets the minimum value for IVs for a specific Pokémon given as percent\n" +\
        "/rempkmiv pokedexID - Resets the minimum value for IVs for a specific Pokémon\n" +\
        "/pkmcp pokedexID 0-4760 - Sets the minumum value for CP for a specific Pokémon\n" +\
        "/rempkmcp pokedexID - Resets the minumum value for CP for a specific Pokémon\n\n" +\
        "*Distance filter*\n" + \
        "/location address - Sets the desired search location given as text\n" +\
        "/radius km - Sets the search radius in km\n" +\
        "/remloc - Clears the search location and radius\n" +\
        "/pkmradius pokedexID km - Sets the search radius for a specific Pokémon in km\n" +\
        "/rempkmradius pokedexID - Resets the search radius for a specific Pokémon\n\n" +\
        "*Notification settings*\n" + \
        "/sendwithout true/false - Defines if Pokémon without IV/CP should be sent\n" +\
        "/stickers true/false - Defines if stickers should be sent\n" +\
        "/maponly true/false - Defines if only a map should be sent (without an additional message/sticker)\n\n" +\
        "Hint: You can also set the scanning location by just sending a location marker"

    bot.sendMessage(chat_id, text, parse_mode='Markdown')

def cmd_start(bot, update, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'start'):
        return

    pref = prefs.get(chat_id)

    if len(pref.get('search_ids')) > 0:
        addJob(bot, update, job_queue)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Bot wurde gestartet.')
        else:
            bot.sendMessage(chat_id, text='Bot was started.')
    else:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Hallo! Du scheinst neu hier zu sein. Hier ist eine Liste von verfügbaren Befehlen:')
        else:
            bot.sendMessage(chat_id, text='Hello! You seem to be new here. Here is a list of available commands:')
        cmd_help(bot, update)

    logger.info('[%s@%s] Starting.' % (userName, chat_id))

def cmd_stop(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'stop'):
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] Stopping.' % (userName, chat_id))

    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Bot wurde pausiert. Nutze /start zum Fortsetzen.')
    else:
        bot.sendMessage(chat_id, text='Bot was paused. Use /start to resume.')

    if chat_id not in jobs:
        return

    # Remove from jobs
    job = jobs[chat_id]
    job.schedule_removal()
    del jobs[chat_id]

    # Remove from sent
    del sent[chat_id]
    # Remove from locks
    del locks[chat_id]

def cmd_stickers(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'stickers'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Sticker sind aktuell auf %s gesetzt.' % (pref.get('stickers')))
        else:
            bot.sendMessage(chat_id, text='Stickers are currently set to %s.' % (pref.get('stickers')))
        return

    try:
        stick = args[0].lower()
        logger.info('[%s@%s] Setting stickers.' % (userName, chat_id))

        if stick == 'true' or stick == 'false':
            stick = False
            if args[0].lower() == 'true':
                stick = True
            pref.set('stickers', stick)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Sticker wurden auf %s gesetzt.' % (stick))
            else:
                bot.sendMessage(chat_id, text='Stickers were set to %s.' % (stick))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Bitte nur True (aktivieren) oder False (deaktivieren) angeben.')
            else:
                bot.sendMessage(chat_id, text='Please only use True (enable) or False (disable).')

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/stickers true/false')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/stickers true/false')

def cmd_maponly(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'maponly'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='"Nur Karte anzeigen" ist aktuell auf %s gesetzt.' % (pref.get('only_map')))
        else:
            bot.sendMessage(chat_id, text='"Only show map" is currently set to %s.' % (pref.get('only_map')))
        return

    try:
        omap = args[0].lower()
        logger.info('[%s@%s] Setting maponly.' % (userName, chat_id))

        if omap == 'true' or omap == 'false':
            omap = False
            if args[0].lower() == 'true':
                omap = True
            pref.set('only_map', omap)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='"Nur Karte anzeigen" wurde auf %s gesetzt.' % (omap))
            else:
                bot.sendMessage(chat_id, text='"Only show map" was set to %s.' % (omap))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Bitte nur True (aktivieren) oder False (deaktivieren) angeben.')
            else:
                bot.sendMessage(chat_id, text='Please only use True (enable) or False (disable).')

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/maponly true/false')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/maponly true/false')

def cmd_sendwithout(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'sendwithout'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='"Pokémon ohne IV/WP-Werte senden" ist aktuell auf %s gesetzt.' % (pref.get('send_without', True)))
        else:
            bot.sendMessage(chat_id, text='"Send Pokémon without IV/CP" is currently set to %s.' % (pref.get('send_without', True)))
        return

    try:
        sendwithout = args[0].lower()
        logger.info('[%s@%s] Setting sendwithout.' % (userName, chat_id))

        if sendwithout == 'true' or sendwithout == 'false':
            sendwithout = False
            if args[0].lower() == 'true':
                sendwithout = True
            pref.set('send_without', sendwithout)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='"Pokémon ohne IV/WP-Werte senden" wurde auf %s gesetzt.' % (sendwithout))
            else:
                bot.sendMessage(chat_id, text='"Send Pokémon without IV/CP" was set to %s.' % (sendwithout))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Bitte nur True (aktivieren) oder False (deaktivieren) angeben.')
            else:
                bot.sendMessage(chat_id, text='Please only use True (enable) or False (disable).')

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/sendwithout true/false')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/sendwithout true/false')

def cmd_walkdist(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isAdmin(userName):
        logger.info('[%s@%s] User blocked (walkdist).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='"Zeige Laufdistanz und -zeit" ist aktuell gesetzt auf %s.' % (pref.get('walk_dist')))
        else:
            bot.sendMessage(chat_id, text='"Show walking distance/time" is currently set to %s.' % (pref.get('walk_dist')))
        return

    try:
        wdist = args[0].lower()
        logger.info('[%s@%s] Setting walkdist.' % (userName, chat_id))

        if wdist == 'true' or wdist == 'false':
            wdist = False
            if args[0].lower() == 'true':
                wdist = True
            pref.set('walk_dist', wdist)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='"Zeige Laufdistanz und -zeit" wurde auf %s gesetzt.' % (wdist))
            else:
                bot.sendMessage(chat_id, text='"Show walking distance/time" was set to %s.' % (wdist))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Bitte nur True (aktivieren) oder False (deaktivieren) angeben.')
            else:
                bot.sendMessage(chat_id, text='Please only use True (enable) or False (disable).')

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/walkdist true/false')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/walkdist true/false')

def cmd_add(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'add'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/add pokedexID oder /add pokedexID1 pokedexID2 ...'
    else:
        usage_message = 'Usage:\n/add pokedexID or /add pokedexID1 pokedexID2 ...'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    addJob(bot, update, job_queue)
    logger.info('[%s@%s] Add pokemon.' % (userName, chat_id))

    try:
        search = pref.get('search_ids')
        for x in args:
            if int(x) >= min_pokemon_id and int(x) <= max_pokemon_id and int(x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)

def cmd_addByRarity(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'addByRarity'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/addbyrarity 1-5 (mit 1 sehr häufig bis 5 ultra selten)'
    else:
        usage_message = 'Usage:\n/addbyrarity 1-5 (with 1 very common to 5 ultrarare)'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    addJob(bot, update, job_queue)
    logger.info('[%s@%s] Add pokemon by rarity.' % (userName, chat_id))

    try:
        rarity = int(args[0])

        if rarity < 1 or rarity > 5:
            bot.sendMessage(chat_id, text=usage_message)
            return

        search = pref.get('search_ids')
        for x in pokemon_rarity[rarity]:
            if int(x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)

def cmd_clear(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'clear'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Deine Einstellungen wurden erfolgreich zurückgesetzt.')
    else:
        bot.sendMessage(chat_id, text='Your settings were successfully reset.')

    """Removes the job if the user changed their mind"""
    logger.info('[%s@%s] Clear list.' % (userName, chat_id))

    pref.reset_user()

    if chat_id not in jobs:
        return

    # Remove from jobs
    job = jobs[chat_id]
    job.schedule_removal()
    del jobs[chat_id]

    # Remove from sent
    del sent[chat_id]
    # Remove from locks
    del locks[chat_id]

def cmd_remove(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'remove'):
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] Remove pokemon.' % (userName, chat_id))

    try:
        search = pref.get('search_ids')
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/rem pokedexID')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/rem pokedexID')

def cmd_list(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'list'):
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] List.' % (userName, chat_id))

    try:
        lan = pref.get('language')
        dists = pref.get('search_dists', {})
        minivs = pref.get('search_miniv', {})
        mincps = pref.get('search_mincp', {})
        user_location = pref.get('location')
        if lan == 'de':
            if user_location[0] is None:
                tmp = 'Liste der überwachten Pokémon:\n'
            else:
                tmp = 'Liste der überwachten Pokémon im Radius von %.2fkm:\n' % (user_location[2])
        else:
            if user_location[0] is None:
                tmp = 'List of watched Pokémon:\n'
            else:
                tmp = 'List of watched Pokémon within a radius of %.2fkm:\n' % (user_location[2])
        for x in pref.get('search_ids'):
            tmp += "%i %s" % (x, pokemon_name[lan][str(x)])
            if str(x) in dists:
                tmp += " %.2fkm" % (dists[str(x)])
            if str(x) in minivs:
                tmp += " %d%%" % (minivs[str(x)])
            if str(x) in mincps:
                if lan == 'de':
                    tmp += " %dWP" % (mincps[str(x)])
                else:
                    tmp += " %dCP" % (mincps[str(x)])
            tmp += "\n"
        bot.sendMessage(chat_id, text = tmp)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))

def cmd_load(bot, update, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'load'):
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] Attempting to load.' % (userName, chat_id))

    r = pref.load()

    if r is None:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Du hast keine gespeicherten Einstellungen.')
        else:
            bot.sendMessage(chat_id, text='You do not have saved preferences.')
        return

    if not r:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Du bist schon auf dem neusten Stand.')
        else:
            bot.sendMessage(chat_id, text='You are already up to date.')
        return
    else:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Deine Einstellungen wurden erfolgreich wiederhergestellt.')
        else:
            bot.sendMessage(chat_id, text='Your settings were successfully restored.')

    if len(pref.get('search_ids')) > 0:
        addJob(bot, update, job_queue)
    else:
        if chat_id in jobs:
            job = jobs[chat_id]
            job.schedule_removal()
            del jobs[chat_id]

def cmd_lang(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'lang'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Deine Sprache ist aktuell auf %s gesetzt.' % (pref.get('language')))
        else:
            bot.sendMessage(chat_id, text='Your language is currently set to %s.' % (pref.get('language')))
        return

    try:
        lan = args[0]
        logger.info('[%s@%s] Setting lang.' % (userName, chat_id))

        if lan == 'de' or lan == 'en':
            pref.set('language', lan)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Sprache wurde auf %s gesetzt.' % (lan))
            else:
                bot.sendMessage(chat_id, text='Language was set to %s.' % (lan))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Diese Sprache ist leider nicht verfügbar.')
            else:
                bot.sendMessage(chat_id, text='This language isn\'t available.')

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung:\n/lang de/en')
        else:
            bot.sendMessage(chat_id, text='Usage:\n/lang de/en')

def setUserLocation(userName, chat_id, latitude, longitude, radius):
    pref = prefs.get(chat_id)
    user_location = pref.get('location')
    if radius is not None and radius < 0.1:
        radius = 0.1
    pref.set('location', [latitude, longitude, radius])
    logger.info('[%s@%s] Setting scan location to Lat %s, Lon %s, R %s' %
        (userName, chat_id, user_location[0], user_location[1], user_location[2]))

def sendCurrentLocation(bot, chat_id, set_new = False):
    pref = prefs.get(chat_id)
    user_location = pref.get('location')
    if user_location[0] is None:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Du hast keine Suchposition angegeben.')
        else:
            bot.sendMessage(chat_id, text='You have not supplied a scan location.')
    else:
        if set_new:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Setze neue Suchposition mit Radius %skm' % (user_location[2]))
            else:
                bot.sendMessage(chat_id, text='Setting new scan location with radius %skm' % (user_location[2]))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Dies ist deine aktuelle Suchposition mit Radius %skm' % (user_location[2]))
            else:
                bot.sendMessage(chat_id, text='This is your current scan location with radius %skm' % (user_location[2]))
        bot.sendLocation(chat_id, user_location[0], user_location[1], disable_notification=True)

def cmd_location(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'location'):
        return

    pref = prefs.get(chat_id)
    user_location = update.message.location
    setUserLocation(userName, chat_id, user_location.latitude, user_location.longitude, pref.get('location')[2])
    sendCurrentLocation(bot, chat_id, True)

def cmd_location_str(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'location_str'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        sendCurrentLocation(bot, chat_id)
        return

    try:
        user_location = geolocator.geocode(' '.join(args))
        setUserLocation(userName, chat_id, user_location.latitude, user_location.longitude, pref.get('location')[2])
        sendCurrentLocation(bot, chat_id, True)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Position wurde nicht gefunden (oder OpenStreetMap ist offline).')
        else:
            bot.sendMessage(chat_id, text='Location was not found (or OpenStreetMap is down).')
        return

def cmd_radius(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'radius'):
        return

    if len(args) < 1:
        sendCurrentLocation(bot, chat_id)
        return

    # Change the radius
    pref = prefs.get(chat_id)
    user_location = pref.get('location')
    setUserLocation(userName, chat_id, user_location[0], user_location[1], float(args[0]))
    sendCurrentLocation(bot, chat_id, True)

def cmd_clearlocation(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'clearlocation'):
        return

    setUserLocation(userName, chat_id, None, None, 1)

    pref = prefs.get(chat_id)
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Deine Suchposition wurde entfernt.')
    else:
        bot.sendMessage(chat_id, text='Your scan location has been removed.')

def cmd_pkmradius(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'pkmradius'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/pkmradius pokedexID km'
    else:
        usage_message = 'Usage:\n/pkmradius pokedexID km'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(pkm_id) not in pokemon_blacklist:
        dists = pref.get('search_dists', {})

        # Only get current value
        if len(args) < 2:
            pkm_dist = dists[pkm_id] if pkm_id in dists else pref.get('location')[2]
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Der Suchradius für %s ist auf %skm gesetzt.' % (pokemon_name['de'][pkm_id], pkm_dist))
            else:
                bot.sendMessage(chat_id, text='The search radius for %s is set to %skm.' % (pokemon_name['en'][pkm_id], pkm_dist))
            return

        # Change the radius for a specific pokemon
        pkm_dist = float(args[1])
        if pkm_dist < 0.1:
            pkm_dist = 0.1

        dists[pkm_id] = pkm_dist
        pref.set('search_dists', dists)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Suchradius für %s wurde auf %skm gesetzt.' % (pokemon_name['de'][pkm_id], pkm_dist))
        else:
            bot.sendMessage(chat_id, text='The search radius for %s was set to %skm.' % (pokemon_name['en'][pkm_id], pkm_dist))

def cmd_rempkmradius(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'rempkmradius'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/rempkmradius pokedexID'
    else:
        usage_message = 'Usage:\n/rempkmradius pokedexID'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    # Change the radius for a specific pokemon
    dists = pref.get('search_dists', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in dists:
        del dists[pkm_id]
        pref.set('search_dists', dists)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Suchradius für %s wurde zurückgesetzt.' % (pokemon_name['de'][pkm_id]))
        else:
            bot.sendMessage(chat_id, text='The search radius for %s was reset.' % (pokemon_name['en'][pkm_id]))

def cmd_iv(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'iv'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-IV-Filter ist auf %d%% gesetzt.' % (pref.get('miniv', 0)))
        else:
            bot.sendMessage(chat_id, text='The minimum IV filter is set to %d%%.' % (pref.get('miniv', 0)))
        return

    miniv = int(args[1])
    if miniv < 0:
        miniv = 0
    if miniv > 100:
        miniv = 100

    pref.set('miniv', miniv)
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Der Minimal-IV-Filter wurde auf %d%% gesetzt.' % (miniv))
    else:
        bot.sendMessage(chat_id, text='The minimum IV filter was set to %d%%.' % (miniv))

def cmd_pkmiv(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'pkmiv'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/pkmiv pokedexID 0-100'
    else:
        usage_message = 'Usage:\n/pkmiv pokedexID 0-100'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(pkm_id) not in pokemon_blacklist:
        minivs = pref.get('search_miniv', {})

        # Only get current value
        if len(args) < 2:
            pkm_miniv = minivs[pkm_id] if pkm_id in minivs else pref.get('miniv', 0)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Der Minimal-IV-Filter für %s ist auf %d%% gesetzt.' % (pokemon_name['de'][pkm_id], pkm_miniv))
            else:
                bot.sendMessage(chat_id, text='The minimum IV filter for %s is set to %d%%.' % (pokemon_name['en'][pkm_id], pkm_miniv))
            return

        # Change the radius for a specific pokemon
        pkm_miniv = int(args[1])
        if pkm_miniv < 0:
            pkm_miniv = 0
        if pkm_miniv > 100:
            pkm_miniv = 100

        minivs[pkm_id] = pkm_miniv
        pref.set('search_miniv', minivs)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-IV-Filter für %s wurde auf %d%% gesetzt.' % (pokemon_name['de'][pkm_id], pkm_miniv))
        else:
            bot.sendMessage(chat_id, text='The minimum IV filter for %s was set to %d%%.' % (pokemon_name['en'][pkm_id], pkm_miniv))

def cmd_rempkmiv(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'rempkmiv'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/rempkmiv pokedexID'
    else:
        usage_message = 'Usage:\n/rempkmiv pokedexID'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    minivs = pref.get('search_miniv', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in minivs:
        del minivs[pkm_id]
        pref.set('search_miniv', minivs)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-IV-Filter für %s wurde zurückgesetzt.' % (pokemon_name['de'][pkm_id]))
        else:
            bot.sendMessage(chat_id, text='The minimum IV filter for %s was reset.' % (pokemon_name['en'][pkm_id]))

def cmd_cp(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'cp'):
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-WP-Filter ist auf %d gesetzt.' % (pref.get('mincp', 0)))
        else:
            bot.sendMessage(chat_id, text='The minimum CP filter is set to %d.' % (pref.get('mincp', 0)))
        return

    mincp = int(args[1])
    if mincp < 0:
        mincp = 0
    if mincp > 4760:
        mincp = 4760

    pref.set('mincp', mincp)
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Der Minimal-WP-Filter wurde auf %d gesetzt.' % (mincp))
    else:
        bot.sendMessage(chat_id, text='The minimum CP filter was set to %d.' % (mincp))

def cmd_pkmcp(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'pkmcp'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/pkmcp pokedexID 0-4670'
    else:
        usage_message = 'Usage:\n/pkmcp pokedexID 0-4670'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(pkm_id) not in pokemon_blacklist:
        mincps = pref.get('search_mincp', {})

        # Only get current value
        if len(args) < 2:
            pkm_mincp = mincps[pkm_id] if pkm_id in mincps else pref.get('mincp', 0)
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Der Minimal-WP-Filter für %s ist auf %d%% gesetzt.' % (pokemon_name['de'][pkm_id], pkm_mincp))
            else:
                bot.sendMessage(chat_id, text='The minimum CP filter for %s is set to %d%%.' % (pokemon_name['en'][pkm_id], pkm_mincp))
            return

        pkm_mincp = int(args[1])
        if pkm_mincp < 0:
            pkm_mincp = 0
        if pkm_mincp > 4760:
            pkm_mincp = 4760

        mincps[pkm_id] = pkm_mincp
        pref.set('search_mincp', mincps)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-WP-Filter für %s wurde auf %d%% gesetzt.' % (pokemon_name['de'][pkm_id], pkm_mincp))
        else:
            bot.sendMessage(chat_id, text='The minimum CP filter for %s was set to %d%%.' % (pokemon_name['en'][pkm_id], pkm_mincp))

def cmd_rempkmcp(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'rempkmcp'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung:\n/rempkmwp pokedexID'
    else:
        usage_message = 'Usage:\n/rempkmcp pokedexID'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    mincps = pref.get('search_mincp', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in mincps:
        del mincps[pkm_id]
        pref.set('search_mincp', mincps)
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Der Minimal-WP-Filter für %s wurde zurückgesetzt.' % (pokemon_name['de'][pkm_id]))
        else:
            bot.sendMessage(chat_id, text='The minimum CP filter for %s was reset.' % (pokemon_name['en'][pkm_id]))

def isNotWhitelisted(userName, chat_id, command):
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (%s).' % (userName, chat_id, command))
        return True
    return False

def cmd_addToWhitelist(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelistEnabled():
        bot.sendMessage(chat_id, text='Whitelist is disabled.')
        return
    if not whitelist.isAdmin(userName):
        logger.info('[%s@%s] User blocked (addToWhitelist).' % (userName, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text='Usage: /wladd <username> or /wladd <username_1> <username_2>')
        return

    try:
        for x in args:
            whitelist.addUser(x)
        bot.sendMessage(chat_id, "Added to whitelist.")
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text='Usage: /wladd <username> or /wladd <username_1> <username_2>')

def cmd_remFromWhitelist(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelistEnabled():
        bot.sendMessage(chat_id, text='Whitelist is disabled.')
        return
    if not whitelist.isAdmin(userName):
        logger.info('[%s@%s] User blocked (remFromWhitelist).' % (userName, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text='Usage: /wlrem <username> or /wlrem <username_1> <username_2>')
        return

    try:
        for x in args:
            whitelist.remUser(x)
        bot.sendMessage(chat_id, "Removed from whitelist.")

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text='Usage: /wlrem <username> or /wlrem <username_1> <username_2>')

def cmd_unknown(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username

    if isNotWhitelisted(userName, chat_id, 'unknown'):
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Diesen Befehl verstehe ich leider nicht.')
    else:
        bot.sendMessage(chat_id, text='Unfortunately, I do not understand this command.')

## Functions
def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))

def alarm(bot, job):
    chat_id = job.context[0]
    logger.info('[%s] Checking alarm.' % (chat_id))
    checkAndSend(bot, chat_id)

def addJob(bot, update, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    logger.info('[%s@%s] Adding job.' % (userName, chat_id))
    addJobForChatId(chat_id, job_queue)

def addJobForChatId(chat_id, job_queue):
    try:
        if chat_id not in jobs:
            job = Job(alarm, 30, repeat=True, context=(chat_id, 'Other'))
            # Add to jobs
            jobs[chat_id] = job
            logger.info('Putting job')
            job_queue.put(job)

            # User dependant
            if chat_id not in sent:
                sent[chat_id] = dict()
            if chat_id not in locks:
                locks[chat_id] = threading.Lock()
            if chat_id not in clearCnt:
                clearCnt[chat_id] = 0

            return True

    except Exception as e:
        logger.error('[%s] %s' % (chat_id, repr(e)))

    return False

def checkAndSend(bot, chat_id):
    logger.info('[%s] Checking pokemons.' % (chat_id))
    try:
        pref = prefs.get(chat_id)
        pokemons = pref.get('search_ids')
        if len(pokemons) == 0:
            return

        miniv = pref.get('miniv', 0)
        mincp = pref.get('mincp', 0)
        sendWithout = pref.get('send_without', True)

        minivs = pref.get('search_miniv', {})
        for iv in minivs.values():
            miniv = iv if iv < miniv else miniv

        mincps = pref.get('search_mincp', {})
        for cp in mincps.values():
            mincp = cp if cp < mincp else mincp

        allpokes = dataSource.getPokemonByIds(pokemons, miniv, mincp, sendWithout)

        if len(allpokes) > 200:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text="Deine Filterregeln treffen auf zu viele Pokémon zu.\nBitte überprüfe deine Einstellungen!")
            else:
                bot.sendMessage(chat_id, text="Your filter rules are matching too many Pokémon.\nPlease check your settings!")
            return

        for pokemon in allpokes:
            sendOnePoke(chat_id, pokemon)

    except Exception as e:
        logger.error('[%s] %s' % (chat_id, repr(e)))

def findUsersByPokeId(pokemon):
    poke_id = pokemon.getPokemonID()
    logger.info('Checking pokemon %s for all users.' % (poke_id))
    for chat_id in jobs:
        if int(poke_id) in prefs.get(chat_id).get('search_ids'):
            sendOnePoke(chat_id, pokemon)
    pass

def sendOnePoke(chat_id, pokemon):
    pref = prefs.get(chat_id)
    lock = locks[chat_id]
    logger.info('[%s] Sending one notification. %s' % (chat_id, pokemon.getPokemonID()))

    lock.acquire()
    try:
        encounter_id = pokemon.getEncounterID()
        pok_id = str(pokemon.getPokemonID())
        latitude = pokemon.getLatitude()
        longitude = pokemon.getLongitude()
        disappear_time = pokemon.getDisappearTime()
        iv = pokemon.getIVs()
        move1 = pokemon.getMove1()
        move2 = pokemon.getMove2()
        cp = pokemon.getCP()

        mySent = sent[chat_id]

        miniv = pref.preferences.get('miniv', 0)
        mincp = pref.preferences.get('mincp', 0)

        minivs = pref.get('search_miniv', {})
        if pok_id in minivs:
            miniv = minivs[pok_id]

        mincps = pref.get('search_mincp', {})
        if pok_id in mincps:
            mincp = mincps[pok_id]

        sendPokeWithoutIV = config.get('SEND_POKEMON_WITHOUT_IV', True)

        lan = pref.get('language')
        moveNames = move_name["en"]
        if lan in move_name:
            moveNames = move_name[lan]

        delta = disappear_time - datetime.utcnow()
        deltaStr = '%02dm %02ds' % (int(delta.seconds / 60), int(delta.seconds % 60))
        disappear_time_str = disappear_time.replace(tzinfo = timezone.utc).astimezone(tz = None).strftime("%H:%M:%S")

        # Pokemon already sent, disappeared or we do not want to send without iv
        if (encounter_id in mySent) or (delta.seconds <= 0) or (iv is None and not sendPokeWithoutIV):
            lock.release()
            return

        if iv is not None and iv < miniv:
            lock.release()
            return

        if cp is not None and cp < mincp:
            lock.release()
            return

        location_data = pref.preferences.get('location')
        dists = pref.get('search_dists', {})
        if pok_id in dists:
            location_data[2] = dists[pok_id]

        # Pokemon outside of given radius
        if location_data[0] is not None and not pokemon.filterbylocation(location_data):
            lock.release()
            return

        title = pokemon_name[lan][pok_id]

        if iv is not None:
            title += " %s%%" % (iv)

        if cp is not None:
            if lan == 'de':
                title += " %dWP" % (cp)
            else:
                title += " %dCP" % (cp)

        address = "💨 %s ⏱ %s" % (disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walk_dist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += " 📍%dm" % (int(1000*walkin_data['walk_dist']))
                else:
                    title += " 📍%skm" % (walkin_data['walk_dist'])
                address += " 🚶%s" % (walkin_data['walk_time'])
            else:
                dist = round(pokemon.getDistance(location_data), 2)
                if dist < 1:
                    title += " 📍%dm" % (int(1000*dist))
                else:
                    title += " 📍%skm" % (dist)

        if move1 is not None and move2 is not None:
            # Use language if other move languages are available.
            move1Name = moveNames[str(move1)] if str(move1) in moveNames else '?'
            move2Name = moveNames[str(move2)] if str(move2) in moveNames else '?'
            address += "\n⚔ %s / %s" % (move1Name, move2Name)

        mySent[encounter_id] = disappear_time

        if pref.get('only_map'):
            telegramBot.sendVenue(chat_id, latitude, longitude, title, address)
        else:
            if pref.get('stickers'):
                telegramBot.sendSticker(chat_id, sticker_list.get(str(pok_id)), disable_notification=True)
            telegramBot.sendLocation(chat_id, latitude, longitude, disable_notification=True)
            telegramBot.sendMessage(chat_id, text = '<b>%s</b> \n%s' % (title, address), parse_mode='HTML')

    except Exception as e:
        logger.error('[%s] %s' % (chat_id, repr(e)))
    lock.release()

    # Clean already disappeared pokemon
    # 2016-08-19 20:10:10.000000
    # 2016-08-19 20:10:10
    lock.acquire()
    if clearCnt[chat_id] > clearCntThreshold:
        clearCnt[chat_id] = 0
        logger.info('[%s] Cleaning pokelist.' % (chat_id))
        try:
            current_time = datetime.utcnow()
            toDel = []
            for encounter_id in mySent:
                time = mySent[encounter_id]
                if time < current_time:
                    toDel.append(encounter_id)
            for encounter_id in toDel:
                del mySent[encounter_id]
        except Exception as e:
            logger.error('[%s] %s' % (chat_id, repr(e)))
    else:
        clearCnt[chat_id] = clearCnt[chat_id] + 1
    lock.release()

def read_config():
    config_path = os.path.join(
        os.path.dirname(sys.argv[0]), "config-bot.json")
    logger.info('Reading config: <%s>' % config_path)
    global config

    try:
        with open(config_path, "r", encoding='utf-8') as f:
            config = json.loads(f.read())

    except Exception as e:
        logger.error('%s' % (repr(e)))
        config = {}

    report_config()

def report_config():
    admins_list = config.get('LIST_OF_ADMINS', [])
    tmp = ''
    for admin in admins_list:
        tmp = '%s, %s' % (tmp, admin)
    tmp = tmp[2:]
    logger.info('LIST_OF_ADMINS: <%s>' % (tmp))
    logger.info('TELEGRAM_TOKEN: <%s>' % (config.get('TELEGRAM_TOKEN', None)))
    logger.info('GMAPS_KEY: <%s>' % (config.get('GMAPS_KEY', None)))
    logger.info('SCANNER_NAME: <%s>' % (config.get('SCANNER_NAME', None)))
    logger.info('DB_TYPE: <%s>' % (config.get('DB_TYPE', None)))
    logger.info('DB_CONNECT: <%s>' % (config.get('DB_CONNECT', None)))
    logger.info('DEFAULT_LANG: <%s>' % (config.get('DEFAULT_LANG', None)))
    logger.info('SEND_MAP_ONLY: <%s>' % (config.get('SEND_MAP_ONLY', None)))
    logger.info('STICKERS: <%s>' % (config.get('STICKERS', None)))
    logger.info('SEND_POKEMON_WITHOUT_IV: <%s>' % (config.get('SEND_POKEMON_WITHOUT_IV', None)))

def read_pokemon_names(loc):
    logger.info('Reading pokemon names. <%s>' % loc)
    config_path = "locales/pokemon." + loc + ".json"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            pokemon_name[loc] = json.loads(f.read())

    except Exception as e:
        logger.error('%s' % (repr(e)))
        # Pass to ignore if some files missing.
        pass

def read_move_names(loc):
    logger.info('Reading move names. <%s>' % loc)
    config_path = "locales/moves." + loc + ".json"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            move_name[loc] = json.loads(f.read())

    except Exception as e:
        logger.error('%s' % (repr(e)))
        # Pass to ignore if some files missing.
        pass

def send_load_message(chat_id):
    logger.info('Sending load message to: <%s>' % chat_id)
    pref = prefs.get(chat_id)
    try:
        if pref.get('language') == 'de':
            telegramBot.sendMessage(chat_id, text="Leider musste der Bot neugestartet werden. \nBitte nutze den \"/load\" Befehl um deine Einstellungen wiederherzustellen.")
        else:
            telegramBot.sendMessage(chat_id, text="Unfortunately, the bot had to be restarted. \nPlease use the \"/load\" command to restore your settings.")

    except Exception as e:
        logger.error('Encountered error while sending load message (%s)' % (repr(e)))

# Returns a set with walking dist and walking duration via Google Distance Matrix API
def get_walking_data(user_location, lat, lng):
    data = {'walk_dist': 'unknown', 'walk_time': 'unknown'}
    if gmaps_client is None:
        logger.error('Google Maps Client not available. Unable to get walking data.')
        return data
    if user_location[0] is None:
        logger.error('No location has been set. Unable to get walking data.')
        return data
    origin = "{},{}".format(user_location[0], user_location[1])
    dest = "{},{}".format(lat, lng)
    try:
        result = gmaps_client.distance_matrix(origin, dest, mode='walking', units='metric')
        result = result.get('rows')[0].get('elements')[0]
        data['walk_dist'] = float(result.get('distance').get('text').replace(' km', ''))
        data['walk_time'] = result.get('duration').get('text').replace(' hours', 'h').replace(' hour', 'h').replace(' mins', 'm').replace(' min', 'm')

    except Exception as e:
        logger.error('Encountered error while getting walking data (%s)' % (repr(e)))
    return data

def main():
    logger.info('Starting...')
    read_config()

    # Read lang files
    path_to_local = 'locales/'
    for file in os.listdir(path_to_local):
        if fnmatch.fnmatch(file, 'pokemon.*.json'):
            read_pokemon_names(file.split('.')[1])
        if fnmatch.fnmatch(file, 'moves.*.json'):
            read_move_names(file.split('.')[1])

    global dataSource
    global ivAvailable

    ivAvailable = True
    dataSource = DataSources.DSPokemonGoMapIVMysql(config.get('DB_CONNECT', None))

    global whitelist
    whitelist = Whitelist.Whitelist(config)

    #ask it to the bot father in telegram
    token = config.get('TELEGRAM_TOKEN', None)
    updater = Updater(token)
    global telegramBot
    telegramBot = Bot(token)
    logger.info("BotName: <%s>" % (telegramBot.name))

    # Get the Google Maps API
    global gmaps_client
    google_key = config.get('GMAPS_KEY', None)
    gmaps_client = googlemaps.Client(key=google_key, timeout=3, retry_timeout=4) if google_key is not None else None

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", cmd_start, pass_job_queue=True))
    dp.add_handler(CommandHandler("stop", cmd_stop))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("add", cmd_add, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler("addbyrarity", cmd_addByRarity, pass_args = True, pass_job_queue=True))
    dp.add_handler(CommandHandler("clear", cmd_clear))
    dp.add_handler(CommandHandler("rem", cmd_remove, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler("load", cmd_load, pass_job_queue=True))
    dp.add_handler(CommandHandler("list", cmd_list))
    dp.add_handler(CommandHandler("lang", cmd_lang, pass_args=True))
    dp.add_handler(CommandHandler("radius", cmd_radius, pass_args=True))
    dp.add_handler(CommandHandler("location", cmd_location_str, pass_args=True))
    dp.add_handler(CommandHandler("remloc", cmd_clearlocation))
    dp.add_handler(MessageHandler(Filters.location, cmd_location))
    dp.add_handler(CommandHandler("wladd", cmd_addToWhitelist, pass_args=True))
    dp.add_handler(CommandHandler("wlrem", cmd_remFromWhitelist, pass_args=True))
    dp.add_handler(CommandHandler("stickers", cmd_stickers, pass_args=True))
    dp.add_handler(CommandHandler("maponly", cmd_maponly, pass_args=True))
    dp.add_handler(CommandHandler("walkdist", cmd_walkdist, pass_args=True))
    dp.add_handler(CommandHandler("pkmradius", cmd_pkmradius, pass_args=True))
    dp.add_handler(CommandHandler("rempkmradius", cmd_rempkmradius, pass_args=True))
    dp.add_handler(CommandHandler("iv", cmd_iv, pass_args=True))
    dp.add_handler(CommandHandler("cp", cmd_cp, pass_args=True))
    dp.add_handler(CommandHandler("wp", cmd_cp, pass_args=True))
    dp.add_handler(CommandHandler("pkmiv", cmd_pkmiv, pass_args=True))
    dp.add_handler(CommandHandler("pkmcp", cmd_pkmcp, pass_args=True))
    dp.add_handler(CommandHandler("pkmwp", cmd_pkmcp, pass_args=True))
    dp.add_handler(CommandHandler("rempkmiv", cmd_rempkmiv, pass_args=True))
    dp.add_handler(CommandHandler("rempkmcp", cmd_rempkmcp, pass_args=True))
    dp.add_handler(CommandHandler("rempkmwp", cmd_rempkmcp, pass_args=True))
    dp.add_handler(CommandHandler("sendwithout", cmd_sendwithout, pass_args=True))
    dp.add_handler(MessageHandler([Filters.command], cmd_unknown))

    # log all errors
    dp.add_error_handler(error)

    # add the configuration to the preferences
    prefs.add_config(config)

    # Start the Bot
    updater.start_polling(bootstrap_retries=3, read_latency=5)
    j = updater.job_queue

    logger.info('Started!')

    # Send restart notification to all known users
    userdirectory = 'userdata/'
    for file in os.listdir(userdirectory):
        if fnmatch.fnmatch(file, '*.json'):
            chat_id = int(file.split('.')[0])
            pref = prefs.get(chat_id)
            pref.load()
            if len(pref.get('search_ids', [])) > 0:
                addJobForChatId(chat_id, j)

    # Block until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()

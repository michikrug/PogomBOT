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
    raise Exception("Must be using Python 3.")

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

clearCntThreshold = 100
dataSource = None
webhookEnabled = False
ivAvailable = False

# User dependant - dont add
sent = dict()
locks = dict()
clearCnt = dict()

# User dependant - Add to clear, addJob, loadUserConfig, saveUserConfig
#search_ids = dict()
#language = dict()
#location_ids = dict()
location_radius = 1

#pokemon:
pokemon_name = dict()
#move:
move_name = dict()

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
        text = "/help - Zeigt eine Liste mit verfügbaren Befehlen\n" + \
        "/add <#pokedexID> - Fügt Pokémon mit der gegebenen ID zum Scanner hinzu\n" + \
        "/add <#pokedexID1> <#pokedexID2> ...\n" + \
        "/addbyrarity <#rarity> - Fügt Pokémon it der gegebenen Seltenheit zum Scanner hinzu (1 sehr häufig - 5 ultra selten)\n" + \
        "/rem <#pokedexID> - Entfernt Pokémon mit der gegebenen ID vom Scanner\n" + \
        "/rem <#pokedexID1> <#pokedexID2> ...\n" + \
        "/list - Zeigt eine Liste mit den überwachten Pokémon\n" + \
        "/location <address> - Setzt deine Suchposition gegeben als Text\n" +\
        "/radius <km> - Setzt deinen Suchradius in km\n" +\
        "/remloc - Setzt die Suchposition zurück\n" +\
        "/stickers <true/false> - Legt fest, ob Sticker gesendet werden sollen\n" +\
        "/maponly <true/false> - Legt fest, ob nur eine Karte gesendet werden soll (ohne zusätzliche Nachricht/Sticker)\n" +\
        "/lang [de, en] - Setzt die Sprache des Bots\n" + \
        "/clear - Setzt alle deine Einstellungen zurück\n" + \
        "/load - Stellt deine Einstellungen (z.B. nach einem Neustart) wieder her\n\n" + \
        "Hinweis: Du kannst ebenso deine Suchposition festlegen, indem du einfach einen Positionsmarker sendest"

    else:
        text = "/help - Shows a list of available commands\n" + \
        "/add <#pokedexID> - Adds Pokémon with the given ID to the scanner\n" + \
        "/add <#pokedexID1> <#pokedexID2> ...\n" + \
        "/addbyrarity <#rarity> - Adds Pokémon with the given rarity to scanner (1 very common - 5 ultrarare)\n" + \
        "/rem <#pokedexID> - Removes Pokémon with the given ID from the scanner\n" + \
        "/rem <#pokedexID1> <#pokedexID2> ...\n" + \
        "/list - Lists the watched Pokémon\n" + \
        "/location <address> - Sets your desired search location given as text\n" +\
        "/radius <km> - Sets the search radius in km\n" +\
        "/remloc - Clears your location data\n" +\
        "/stickers <true/false> - Defines if stickers should be sent\n" +\
        "/maponly <true/false> - Defines if only a map should be sent (without an additional message/sticker)\n" +\
        "/lang [de, en] - Sets the language of the bot\n" + \
        "/clear - Resets all your settings\n" + \
        "/load - Restores your settings\n\n" + \
        "Hint: You can also set your scanning location by just sending a location marker"

    bot.sendMessage(chat_id, text)

def cmd_start(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (start).' % (userName, chat_id))
        return

    logger.info('[%s@%s] Starting.' % (userName, chat_id))
    bot.sendMessage(chat_id, text='Hello!')
    cmd_help(bot, update)

def cmd_stickers(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (stickers).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Sticker sind aktuell gesetzt auf %s.' % (pref.get('stickers')))
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
            pref.set_preferences()
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
            bot.sendMessage(chat_id, text='Verwendung: "/stickers <true/false>"')
        else:
            bot.sendMessage(chat_id, text='usage: "/stickers <true/false>"')

def cmd_maponly(bot, update, args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (maponly).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='"Nur Karte anzeigen" ist aktuell gesetzt auf %s.' % (pref.get('only_map')))
        else:
            bot.sendMessage(chat_id, text='"Only show map" is currently set to %s.' % (pref.get('only_map')))
        return

    try:
        omap = args[0].lower()
        logger.info('[%s@%s] Setting stickers.' % (userName, chat_id))

        if omap == 'true' or omap == 'false':
            omap = False
            if args[0].lower() == 'true':
                omap = True
            pref.set('only_map', omap)
            pref.set_preferences()
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
            bot.sendMessage(chat_id, text='Verwendung: "/maponly <true/false>"')
        else:
            bot.sendMessage(chat_id, text='usage: "/maponly <true/false>"')

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
            pref.set_preferences()
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
            bot.sendMessage(chat_id, text='Verwendung: "/walkdist <true/false>"')
        else:
            bot.sendMessage(chat_id, text='usage: "/walkdist <true/false>"')

def cmd_add(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (add).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung: "/add <#pokemon>"" oder "/add <#pokemon1> <#pokemon2>"'
    else:
        usage_message = 'usage: "/add <#pokemon>"" or "/add <#pokemon1> <#pokemon2>"'

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    addJob(bot, update, job_queue)
    logger.info('[%s@%s] Add pokemon.' % (userName, chat_id))

    try:
        search = pref.get('search_ids')
        for x in args:
            if int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        pref.set_preferences()
        cmd_list(bot, update)
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)

def cmd_addByRarity(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (addByRarity).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        usage_message = 'Verwendung: "/addbyrarity <#rarity>" mit 1 sehr häufig bis 5 ultra selten'
    else:
        usage_message = 'usage: "/addbyrarity <#rarity>" with 1 very common to 5 ultrarare'

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
            if int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        pref.set_preferences()
        cmd_list(bot, update)

    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)

def cmd_clear(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (clear).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Deine Einstellungen wurden erfolgreich zurückgesetzt.')
    else:
        bot.sendMessage(chat_id, text='Your settings were successfully reset.')

    """Removes the job if the user changed their mind"""
    logger.info('[%s@%s] Clear list.' % (userName, chat_id))

    pref.reset_user()
    pref.set_preferences()

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
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (remove).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] Remove pokemon.' % (userName, chat_id))

    try:
        search = pref.get('search_ids')
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('search_ids', search)
        pref.set_preferences()
        cmd_list(bot, update)
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung: /rem <#pokemon>')
        else:
            bot.sendMessage(chat_id, text='usage: /rem <#pokemon>')

def cmd_list(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (list).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    logger.info('[%s@%s] List.' % (userName, chat_id))

    try:
        lan = pref.get('language')
        if pref.get('language') == 'de':
            tmp = 'Liste der überwachten Pokémon:\n'
        else:
            tmp = 'List of watched Pokémon:\n'
        for x in pref.get('search_ids'):
            tmp += "%i %s\n" % (x, pokemon_name[lan][str(x)])
        bot.sendMessage(chat_id, text = tmp)
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))

def cmd_load(bot, update, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (load).' % (userName, chat_id))
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

    # We might be the first user and above failed....
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
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (lang).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Deine Sprache ist aktuell gesetzt auf [%s].' % (pref.get('language')))
        else:
            bot.sendMessage(chat_id, text='Your language is currently set to [%s].' % (pref.get('language')))
        return

    try:
        lan = args[0]
        logger.info('[%s@%s] Setting lang.' % (userName, chat_id))

        if lan == 'de' or lan == 'en':
            pref.set('language', lan)
            pref.set_preferences()
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Sprache wurde auf [%s] gesetzt.' % (lan))
            else:
                bot.sendMessage(chat_id, text='Language was set to [%s].' % (lan))
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Diese Sprache ist leider nicht verfügbar. [%s]' % (tmp))
            else:
                bot.sendMessage(chat_id, text='This language isn\'t available. [%s]' % (tmp))
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Verwendung: /lang <#sprache>')
        else:
            bot.sendMessage(chat_id, text='usage: /lang <#language>')

def cmd_location(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (location).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    user_location = update.message.location

    # We set the location from the users sent location.
    pref.set('location', [user_location.latitude, user_location.longitude, pref.get('location')[2]])
    pref.set_preferences()

    user_location = pref.get('location')

    logger.info('[%s@%s] Setting scan location to Lat %s, Lon %s, R %s' %
        (userName, chat_id, user_location[0], user_location[1], user_location[2]))

    # Send confirmation nessage
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text="Setze Suchposition auf %f / %f mit Radius %.2f km" %
            (user_location[0], user_location[1], user_location[2]))
    else:
        bot.sendMessage(chat_id, text="Setting scan location to %f / %f with radius %.2f km" %
            (user_location[0], user_location[1], user_location[2]))

def cmd_location_str(bot, update,args):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (location_str).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    if len(args) < 1:
        user_location = pref.get('location')
        if user_location[0] is None:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text='Du hast keine Position angegeben.')
            else:
                bot.sendMessage(chat_id, text='You have not supplied a location.')
        else:
            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text="Deine aktuelle Suchposition ist %f / %f mit Radius %.2f km" %
                    (user_location[0], user_location[1], user_location[2]))
            else:
                bot.sendMessage(chat_id, text="Your current scan location is %f / %f with radius %.2f km" %
                    (user_location[0], user_location[1], user_location[2]))
        return

    try:
        user_location = geolocator.geocode(' '.join(args))

        # We set the location from the users sent location.
        pref.set('location', [user_location.latitude, user_location.longitude, pref.get('location')[2]])
        pref.set_preferences()

        user_location = pref.get('location')

        logger.info('[%s@%s] Setting scan location to Lat %s, Lon %s, R %s' %
            (userName, chat_id, user_location[0], user_location[1], user_location[2]))

        # Send confirmation nessage
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text="Setze Suchposition auf %f / %f mit Radius %.2f km" %
                (user_location[0], user_location[1], user_location[2]))
        else:
            bot.sendMessage(chat_id, text="Setting scan location to %f / %f with radius %.2f km" %
                (user_location[0], user_location[1], user_location[2]))

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
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (radius).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)

    user_location = pref.get('location')

    if user_location[0] is None:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text='Du hast noch keine Suchposition festgelegt. Bitte tu das zuerst!')
        else:
            bot.sendMessage(chat_id, text='You have not set a scan location. Please do that first!')
        return

    # Get the users location
    logger.info('[%s@%s] Retrieved Location as Lat %s, Lon %s, R %s (Km)' %
        (userName, chat_id, user_location[0], user_location[1], user_location[2]))

    if len(args) < 1:
        if pref.get('language') == 'de':
            bot.sendMessage(chat_id, text="Deine aktuelle Suchposition ist %f / %f mit Radius %.2f km" %
                (user_location[0], user_location[1], user_location[2]))
        else:
            bot.sendMessage(chat_id, text="Your current scan location is %f / %f with radius %.2f km" %
                (user_location[0], user_location[1], user_location[2]))
        return

    # Change the radius
    pref.set('location', [user_location[0], user_location[1], float(args[0])])
    pref.set_preferences()

    user_location = pref.get('location')

    logger.info('[%s@%s] Setting scan location to Lat %s, Lon %s, R %s' %
        (userName, chat_id, user_location[0], user_location[1], user_location[2]))

    # Send confirmation nessage
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text="Setze Suchposition auf %f / %f mit Radius %.2f km" %
            (user_location[0], user_location[1], user_location[2]))
    else:
        bot.sendMessage(chat_id, text="Setting scan location to %f / %f with radius %.2f km" %
            (user_location[0], user_location[1], user_location[2]))

def cmd_clearlocation(bot, update):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    if not whitelist.isWhitelisted(userName):
        logger.info('[%s@%s] User blocked (clearlocation).' % (userName, chat_id))
        return

    pref = prefs.get(chat_id)
    pref.set('location', [None, None, None])
    pref.set_preferences()
    if pref.get('language') == 'de':
        bot.sendMessage(chat_id, text='Deine Suchposition wurde entfernt.')
    else:
        bot.sendMessage(chat_id, text='Your scan location has been removed.')
    logger.info('[%s@%s] Location has been unset' % (userName, chat_id))

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
        bot.sendMessage(chat_id, text='usage: "/wladd <username>"" or "/wladd <username_1> <username_2>"')
        return

    try:
        for x in args:
            whitelist.addUser(x)
        bot.sendMessage(chat_id, "Added to whitelist.")
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text='usage: "/wladd <username>"" or "/wladd <username_1> <username_2>"')

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
        bot.sendMessage(chat_id, text='usage: "/wlrem <username>"" or "/wlrem <username_1> <username_2>"')
        return

    try:
        for x in args:
            whitelist.remUser(x)
        bot.sendMessage(chat_id, "Removed from whitelist.")
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))
        bot.sendMessage(chat_id, text='usage: "/wlrem <username>"" or "/wlrem <username_1> <username_2>"')

## Functions
def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))

def alarm(bot, job):
    chat_id = job.context[0]
    logger.info('[%s] Checking alarm.' % (chat_id))
    checkAndSend(bot, chat_id, prefs.get(chat_id).get('search_ids'))

def addJob(bot, update, job_queue):
    chat_id = update.message.chat_id
    userName = update.message.from_user.username
    logger.info('[%s@%s] Adding job.' % (userName, chat_id))

    try:
        if chat_id not in jobs:
            job = Job(alarm, 30, repeat=True, context=(chat_id, "Other"))
            # Add to jobs
            jobs[chat_id] = job
            if not webhookEnabled:
                logger.info('Putting job')
                job_queue.put(job)

            # User dependant
            if chat_id not in sent:
                sent[chat_id] = dict()
            if chat_id not in locks:
                locks[chat_id] = threading.Lock()
            if chat_id not in clearCnt:
                clearCnt[chat_id] = 0

            pref = prefs.get(chat_id)

            if pref.get('language') == 'de':
                bot.sendMessage(chat_id, text="Scanner gestartet.")
            else:
                bot.sendMessage(chat_id, text="Scanner started.")
    except Exception as e:
        logger.error('[%s@%s] %s' % (userName, chat_id, repr(e)))

def checkAndSend(bot, chat_id, pokemons):
    logger.info('[%s] Checking pokemons.' % (chat_id))
    if len(pokemons) == 0:
        return

    try:
        allpokes = dataSource.getPokemonByIds(pokemons)
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
        lan = pref.get('language')
        mySent = sent[chat_id]
        location_data = pref.get('location')

        sendPokeWithoutIV = config.get('SEND_POKEMON_WITHOUT_IV', True)
        pokeMinIVFilterList = config.get('POKEMON_MIN_IV_FILTER_LIST', dict())

        moveNames = move_name["en"]
        if lan in move_name:
            moveNames = move_name[lan]

        encounter_id = pokemon.getEncounterID()
        spaw_point = pokemon.getSpawnpointID()
        pok_id = pokemon.getPokemonID()
        latitude = pokemon.getLatitude()
        longitude = pokemon.getLongitude()
        disappear_time = pokemon.getDisappearTime()
        iv = pokemon.getIVs()
        move1 = pokemon.getMove1()
        move2 = pokemon.getMove2()

        if (encounter_id in mySent) or (location_data[0] is not None and not pokemon.filterbylocation(location_data)):
            lock.release()
            return

        delta = disappear_time - datetime.utcnow()
        deltaStr = '%02dm %02ds' % (int(delta.seconds / 60), int(delta.seconds % 60))
        disappear_time_str = disappear_time.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%H:%M:%S")

        title =  pokemon_name[lan][pok_id]

        address = "💨 %s ⏱ %s" % (disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walk_dist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += " 📍 %sm" % (int(1000*walkin_data['walk_dist']))
                else:
                    title += " 📍 %skm" % (walkin_data['walk_dist'])
                address += " 🚶%s" % (walkin_data['walk_time'])
            else:
                dist = round(pokemon.getDistance(location_data), 2)
                if dist < 1:
                    title += " 📍 %sm" % (int(1000*dist))
                else:
                    title += " 📍 %skm" % (dist)

        if iv is not None:
            title += " IV:%s" % (iv)

        if move1 is not None and move2 is not None:
            # Use language if other move languages are available.
            move1Name = moveNames[move1]
            move2Name = moveNames[move2]
            address += " Moves: %s,%s" % (move1Name, move2Name)

        pokeMinIV = None
        if pok_id in pokeMinIVFilterList:
            pokeMinIV = pokeMinIVFilterList[pok_id]

        if encounter_id not in mySent:
            mySent[encounter_id] = disappear_time

            notDisappeared = delta.seconds > 0
            ivNoneAndSendWithout = (iv is None) and sendPokeWithoutIV
            ivNotNoneAndPokeMinIVNone = (iv is not None) and (pokeMinIV is None)
            ivHigherEqualFilter = (iv is not None) and (pokeMinIV is not None) and (float(iv) >= float(pokeMinIV))

            if notDisappeared and (not ivAvailable or ivNoneAndSendWithout or ivNotNoneAndPokeMinIVNone or ivHigherEqualFilter):
                if pref.get('only_map'):
                    telegramBot.sendVenue(chat_id, latitude, longitude, title, address)
                else:
                    if pref.get('stickers'):
                        telegramBot.sendSticker(chat_id, sticker_list.get(str(pok_id)), disable_notification=True)
                    telegramBot.sendMessage(chat_id, text = '<b>%s</b> \n%s' % (title, address), parse_mode='HTML')
                    telegramBot.sendLocation(chat_id, latitude, longitude, disable_notification=True)

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
    logger.info('SCANNER_NAME: <%s>' % (config.get('SCANNER_NAME', None)))
    logger.info('DB_TYPE: <%s>' % (config.get('DB_TYPE', None)))
    logger.info('DB_CONNECT: <%s>' % (config.get('DB_CONNECT', None)))
    logger.info('DEFAULT_LANG: <%s>' % (config.get('DEFAULT_LANG', None)))
    logger.info('SEND_MAP_ONLY: <%s>' % (config.get('SEND_MAP_ONLY', None)))
    logger.info('STICKERS: <%s>' % (config.get('STICKERS', None)))
    logger.info('SEND_POKEMON_WITHOUT_IV: <%s>' % (config.get('SEND_POKEMON_WITHOUT_IV', None)))

    poke_ivfilter_list = config.get('POKEMON_MIN_IV_FILTER_LIST', dict())
    tmp = ''
    for poke_id in poke_ivfilter_list:
        tmp = '%s %s:%s' % (tmp, poke_id, poke_ivfilter_list[poke_id])
    tmp = tmp[1:]
    logger.info('POKEMON_MIN_IV_FILTER_LIST: <%s>' % (tmp))

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
    if pref.get('language') == 'de':
        telegramBot.sendMessage(chat_id, text="Leider musste der Bot neugestartet werden. \nBitte nutze den \"/load\" Befehl um deine Einstellungen wiederherzustellen.")
    else:
        telegramBot.sendMessage(chat_id, text="Unfortunately, the bot had to be restarted. \nPlease use the \"/load\" command to restore your settings.")

# Returns a set with walking dist and walking duration via Google Distance Matrix API
def get_walking_data(user_location, lat, lng):
    data = {'walk_dist': "unknown", 'walk_time': "unknown"}
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
        logger.error("Encountered error while getting walking data (%s)" % (repr(e)))
    return data

def main():
    logger.info('Starting...')
    read_config()

    # Read lang files
    path_to_local = "locales/"
    for file in os.listdir(path_to_local):
        if fnmatch.fnmatch(file, 'pokemon.*.json'):
            read_pokemon_names(file.split('.')[1])
        if fnmatch.fnmatch(file, 'moves.*.json'):
            read_move_names(file.split('.')[1])

    dbType = config.get('DB_TYPE', None)
    scannerName = config.get('SCANNER_NAME', None)

    global dataSource
    global webhookEnabled
    global ivAvailable
    if dbType == 'sqlite':
        if scannerName == 'pogom':
            dataSource = DataSources.DSPogom(config.get('DB_CONNECT', None))
        elif scannerName == 'pogom-iv':
            ivAvailable = True
            dataSource = DataSources.DSPogomIV(config.get('DB_CONNECT', None))
        elif scannerName == 'pokemongo-map':
            dataSource = DataSources.DSPokemonGoMap(config.get('DB_CONNECT', None))
        elif scannerName == 'pokemongo-map-iv':
            ivAvailable = True
            dataSource = DataSources.DSPokemonGoMapIV(config.get('DB_CONNECT', None))
    elif dbType == 'mysql':
        if scannerName == 'pogom':
            dataSource = DataSources.DSPogomMysql(config.get('DB_CONNECT', None))
        elif scannerName == 'pogom-iv':
            ivAvailable = True
            dataSource = DataSources.DSPogomIVMysql(config.get('DB_CONNECT', None))
        elif scannerName == 'pokemongo-map':
            dataSource = DataSources.DSPokemonGoMapMysql(config.get('DB_CONNECT', None))
        elif scannerName == 'pokemongo-map-iv':
            ivAvailable = True
            dataSource = DataSources.DSPokemonGoMapIVMysql(config.get('DB_CONNECT', None))
    elif dbType == 'webhook':
        webhookEnabled = True
        if scannerName == 'pogom':
            pass
        elif scannerName == 'pokemongo-map':
            dataSource = DataSources.DSPokemonGoMapWebhook(config.get('DB_CONNECT', None), findUsersByPokeId)
        elif scannerName == 'pokemongo-map-iv':
            ivAvailable = True
            dataSource = DataSources.DSPokemonGoMapIVWebhook(config.get('DB_CONNECT', None), findUsersByPokeId)
    if not dataSource:
        raise Exception("The combination SCANNER_NAME, DB_TYPE is not available: %s,%s" % (scannerName, dbType))

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
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("add", cmd_add, pass_args = True, pass_job_queue=True))
    dp.add_handler(CommandHandler("addbyrarity", cmd_addByRarity, pass_args = True, pass_job_queue=True))
    dp.add_handler(CommandHandler("clear", cmd_clear))
    dp.add_handler(CommandHandler("rem", cmd_remove, pass_args = True, pass_job_queue=True))
    dp.add_handler(CommandHandler("load", cmd_load, pass_job_queue=True))
    dp.add_handler(CommandHandler("list", cmd_list))
    dp.add_handler(CommandHandler("lang", cmd_lang, pass_args = True))
    dp.add_handler(CommandHandler("radius", cmd_radius, pass_args=True))
    dp.add_handler(CommandHandler("location", cmd_location_str, pass_args=True))
    dp.add_handler(CommandHandler("remloc", cmd_clearlocation))
    dp.add_handler(MessageHandler(Filters.location, cmd_location))
    dp.add_handler(CommandHandler("wladd", cmd_addToWhitelist, pass_args=True))
    dp.add_handler(CommandHandler("wlrem", cmd_remFromWhitelist, pass_args=True))
    dp.add_handler(CommandHandler("stickers", cmd_stickers, pass_args=True))
    dp.add_handler(CommandHandler("maponly", cmd_maponly, pass_args=True))
    dp.add_handler(CommandHandler("walkdist", cmd_walkdist, pass_args=True))

    # log all errors
    dp.add_error_handler(error)

    # add the configuration to the preferences
    prefs.add_config(config)

    # Start the Bot
    updater.start_polling(bootstrap_retries=3, read_latency=5)

    logger.info('Started!')

    userdirectory = os.path.join(os.path.dirname(sys.argv[0]), "userdata")
    for file in os.listdir(userdirectory):
        if fnmatch.fnmatch(file, '*.json'):
            send_load_message(file.split('.')[0])

    # Block until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()

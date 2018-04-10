#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Simple Bot that looks inside the database and see if the pokemon requested is appeared during the last scan
# This program is dedicated to the public domain under the CC0 license.
# First iteration made by eugenio412
# based on timerbot made inside python-telegram-bot example folder

# /* cSpell:disable */

import fnmatch
import gettext
import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone

import googlemaps
from geopy.distance import vincenty
from geopy.geocoders import Nominatim
from geopy.point import Point
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters, Job,
                          MessageHandler, Updater)

import DataSources
import Preferences
import Whitelist
from Stickers import sticker_list

if sys.version_info[0] < 3:
    raise Exception('Must be using Python 3.')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', level=logging.INFO)

LOGGER = logging.getLogger(__name__)

_ = gettext.gettext

prefs = Preferences.UserPreferences()
jobs = dict()
geo_locator = Nominatim()
telegram_bot = None
gmaps_client = None

clearCntThreshold = 20
data_source = None
webhook_enabled = False
iv_available = False

# User dependant - dont add
sent = dict()
locks = dict()
clearCnt = dict()

pokemon_name = dict()
move_name = dict()

min_pokemon_id = 1
max_pokemon_id = 386

pokemon_blacklist = [
    10, 13, 16, 19, 21, 29, 32, 39, 41, 46, 48, 54, 60, 90, 92, 98, 116, 118, 120, 161, 163, 165,
    167, 177, 183, 194, 198, 220
]

pokemon_rarity = [[], [
    "10", "13", "16", "19", "21", "29", "32", "41", "46", "48", "98", "133", "161", "163", "165",
    "167", "177", "183", "194", "198", "220"
], [
    "14", "17", "20", "35", "39", "43", "52", "54", "60", "63", "69", "72", "79", "81", "90", "92",
    "96", "116", "118", "120", "122", "124", "129", "162", "166", "168", "170", "178", "187", "190",
    "209", "215", "216"
], [
    "1", "4", "7", "8", "11", "12", "15", "18", "22", "23", "25", "27", "30", "33", "37", "42",
    "44", "47", "49", "50", "56", "58", "61", "66", "70", "74", "77", "84", "86", "88", "93", "95",
    "97", "99", "100", "102", "104", "109", "111", "117", "119", "123", "125", "127", "138", "140",
    "147", "152", "155", "158", "164", "169", "184", "185", "188", "191", "193", "195", "200",
    "202", "203", "204", "206", "207", "210", "211", "213", "217", "218", "221", "223", "224",
    "226", "227", "228", "231", "234"
], [
    "2", "3", "5", "6", "9", "24", "26", "28", "31", "34", "36", "38", "40", "45", "51", "53", "55",
    "57", "59", "62", "64", "65", "67", "68", "71", "73", "75", "76", "78", "80", "82", "85", "87",
    "89", "91", "94", "101", "103", "105", "106", "107", "108", "110", "112", "113", "114", "121",
    "126", "130", "131", "134", "135", "136", "137", "139", "141", "142", "143", "148", "149",
    "153", "154", "156", "157", "159", "171", "176", "179", "180", "189", "205", "219", "229",
    "232", "237", "241", "242", "246", "247", "248"
], [
    "83", "115", "128", "132", "144", "145", "146", "150", "151", "160", "172", "173", "174", "175",
    "181", "182", "186", "192", "196", "197", "199", "201", "208", "212", "214", "222", "225",
    "230", "233", "235", "236", "238", "239", "240", "243", "244", "245", "249", "250", "251"
]]

raid_levels = [[],
               ["129", "153", "156", "159"],
               ["89", "103", "110", "125", "126"],
               ["59", "65", "68", "94", "134", "135", "136"],
               ["3", "6", "9", "112", "131", "143", "248"],
               ["144", "145", "146", "150", "151", "243", "244", "245", "249", "250", "251"]]

def set_lang(lang):
    global _
    translation = gettext.translation('base', localedir='locales', languages=[lang], fallback=True)
    _ = translation.gettext

# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
def cmd_help(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'help'):
        return

    LOGGER.info('[%s@%s] Sending help text.' % (user_name, chat_id))

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    text = _("*The PoGo Chemnitz Bot knows the following commands:*") + "\n\n" + \
    _("*General*") + "\n" + \
    _("/start") + " - "  + _("Starts the bot (e.g. after pausing)") + "\n" + \
    _("/stop") + " - "  + _("Pauses the bot (use /start to resume)") + "\n" + \
    _("/lang de/en") + " - "  + _("Sets the language of the bot") + "\n" + \
    _("/clear") + " - "  + _("Resets all your settings") + "\n" + \
    _("/help") + " - "  + _("Shows a list of available commands") + "\n" + \
    _("/where GymName") + " - "  + _("Searches for a gym by name and outputs its location") + "\n\n" + \
    _("*Pokémon filter*") + "\n" + \
    _("/add pokedexID") + " - "  + _("Adds Pokémon with the given ID to the scanner") + "\n" + \
    _("/add pokedexID1 pokedexID2 ...") + "\n" + \
    _("/addbyrarity 1-5") + " - "  + _("Adds Pokémon with the given rarity to scanner (1 very common - 5 ultrarare)") + "\n" + \
    _("/rem pokedexID") + " - "  + _("Removes Pokémon with the given ID from the scanner") + "\n" + \
    _("/rem pokedexID1 pokedexID2 ...") + "\n" + \
    _("/list") + " - "  + _("Lists the watched Pokémon and Raid Pokémon") + "\n" + \
    _("/iv 0-100") + " - "  + _("Sets the minimum IVs given as percent") + "\n" +\
    _("/cp 0-4548") + " - "  + _("Sets the minimum CP") + "\n" +\
    _("/level 0-30") + " - "  + _("Sets the minimum level") + "\n" +\
    _("/pkmiv pokedexID 0-100") + " - "  + _("Sets the minimum IVs for a specific Pokémon given as percent") + "\n" +\
    _("/rempkmiv pokedexID") + " - "  + _("Resets the minimum IVs for a specific Pokémon") + "\n" +\
    _("/pkmcp pokedexID 0-4548") + " - "  + _("Sets the minimum CP for a specific Pokémon") + "\n" +\
    _("/rempkmcp pokedexID") + " - "  + _("Resets the minimum CP for a specific Pokémon") + "\n" +\
    _("/pkmlevel pokedexID 0-30") + " - "  + _("Sets the minimum level for a specific Pokémon") + "\n" +\
    _("/rempkmlevel pokedexID") + " - "  + _("Resets the minimum level for a specific Pokémon") + "\n" +\
    _("/matchmode 0/1/2") + " - "  + _("Sets the match mode (0) Distance AND IVs AND CP AND level / (1) Distance AND IVs OR CP OR level has to match / (2) Distance OR IVs OR CP OR level has to match") + "\n" +\
    _("/pkmmatchmode pokedexID 0/1/2") + " - "  + _("Set the match mode for a specific Pokémon") + "n" +\
    _("/rempkmmatchmode pokedexID") + " - "  + _("Reset the match mode for a specific Pokémon") + "\n\n" +\
    _("*Raid filter*") + "\n" + \
    _("/addraid pokedexID") + " - "  + _("Adds Raid Pokémon with the given ID to the scanner") + "\n" + \
    _("/addraid pokedexID1 pokedexID2 ...") + "\n" + \
    _("/addraidbylevel 1-5") + " - "  + _("Adds Raid Pokémon with the given level to scanner (1-5)") + "\n" + \
    _("/remraid pokedexID") + " - "  + _("Removes Raid Pokémon with the given ID from the scanner") + "\n" + \
    _("/remraid pokedexID1 pokedexID2 ...") + "\n\n" + \
    _("*Distance filter*") + "\n" + \
    _("/location address") + " - "  + _("Sets the desired search location given as text") + "\n" +\
    _("/radius km") + " - "  + _("Sets the search radius in km") + "\n" +\
    _("/remloc") + " - "  + _("Clears the search location and radius") + "\n" +\
    _("/pkmradius pokedexID km") + " - "  + _("Sets the search radius for a specific Pokémon in km") + "\n" +\
    _("/rempkmradius pokedexID") + " - "  + _("Resets the search radius for a specific Pokémon") + "\n" +\
    _("/raidradius pokedexID km") + " - "  + _("Sets the search radius for a specific Raid Pokémon in km") + "\n" +\
    _("/remraidradius pokedexID") + " - "  + _("Resets the search radius for a specific Raid Pokémon") + "\n\n" +\
    _("*Notification settings*") + "\n" + \
    _("/sendwithout true/false") + " - "  + _("Defines if Pokémon without IV/CP should be sent") + "\n" +\
    _("/stickers true/false") + " - "  + _("Defines if stickers should be sent") + "\n" +\
    _("/maponly true/false") + " - "  + _("Defines if only a map should be sent (without an additional message/sticker)") + "\n\n" +\
    _("Hint: You can also set the scanning location by just sending a location marker")

    bot.sendMessage(chat_id, text, parse_mode='Markdown')


def cmd_start(bot, update, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'start'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if pref.get('search_ids', []) or pref.get('raid_ids', []):
        add_job(update, job_queue)
        bot.sendMessage(chat_id, text=_('Bot was started.'))
    else:
        bot.sendMessage(chat_id, text=_('Hello! You seem to be new here. Here is a list of available commands:'))
        cmd_help(bot, update)

    LOGGER.info('[%s@%s] Starting.' % (user_name, chat_id))


def cmd_stop(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'stop'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] Stopping.' % (user_name, chat_id))

    bot.sendMessage(chat_id, text=_('Bot was paused. Use /start to resume.'))

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


def cb_button(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    gyms = data_source.get_gyms_by_name(gym_name=query.data, wildcard=False)
    if gyms:
        print_gym(bot, chat_id, gyms[0])
    bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)


def cmd_find_gym(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        return

    try:
        gym_name = ' '.join(args).lower()
        LOGGER.info('[%s@%s] Searching for gym: %s.' % (user_name, chat_id, gym_name))

        gyms = data_source.get_gyms_by_name(gym_name=gym_name)

        if len(gyms) == 1:
            print_gym(bot, chat_id, gyms[0])
        elif len(gyms) > 1:
            keyboard = []
            for gym in gyms:
                keyboard.append(
                    [InlineKeyboardButton(gym.get_name(), callback_data=gym.get_name())])

            update.message.reply_text(_('Multiple gyms were found. Please choose one of the following:'), reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            bot.sendMessage(chat_id, text=_('No gym with this name could be found.'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/where gymName'))


def print_gym(bot, chat_id, gym):
    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    user_location = pref.get('location')
    if chat_id < 0 or user_location[0] is None:
        dist = ''
    else:
        dist = _('Distance: %.2fkm') % (gym.get_distance(user_location))
    bot.sendVenue(chat_id, gym.get_latitude(), gym.get_longitude(), gym.get_name(), dist)


def cmd_stickers(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'stickers'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s are currently set to %s.') % (_('Stickers'), pref.get('stickers')))
        return

    try:
        stick = args[0].lower()
        LOGGER.info('[%s@%s] Setting stickers.' % (user_name, chat_id))

        if stick == 'true' or stick == 'false':
            stick = False
            if args[0].lower() == 'true':
                stick = True
            pref.set('stickers', stick)
            bot.sendMessage(chat_id, text=_('%s were set to %s.') % (_('Stickers'), stick))
        else:
            bot.sendMessage(chat_id, text=_('Please only use True (enable) or False (disable).'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/stickers true/false'))


def cmd_map_only(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'maponly'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %s.') % (_('"Only show map"'), pref.get('only_map')))
        return

    try:
        omap = args[0].lower()
        LOGGER.info('[%s@%s] Setting maponly.' % (user_name, chat_id))

        if omap == 'true' or omap == 'false':
            omap = False
            if args[0].lower() == 'true':
                omap = True
            pref.set('only_map', omap)
            bot.sendMessage(chat_id, text=_('%s was set to %s.') % (_('"Only show map"'), omap))
        else:
            bot.sendMessage(chat_id, text=_('Please only use True (enable) or False (disable).'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/maponly true/false'))


def cmd_send_without(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'sendwithout'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %s.') % (_('"Send Pokémon without IV/CP"'), pref.get('send_without', True)))
        return

    try:
        sendwithout = args[0].lower()
        LOGGER.info('[%s@%s] Setting sendwithout.' % (user_name, chat_id))

        if sendwithout == 'true' or sendwithout == 'false':
            sendwithout = False
            if args[0].lower() == 'true':
                sendwithout = True
            pref.set('send_without', sendwithout)
            bot.sendMessage(chat_id, text=_('%s was set to %s.') % (_('"Send Pokémon without IV/CP"'), sendwithout))
        else:
            bot.sendMessage(chat_id, text=_('Please only use True (enable) or False (disable).'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/sendwithout true/false'))


def cmd_walk_dist(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username
    if not whitelist.is_admin(user_name):
        LOGGER.info('[%s@%s] User blocked (walkdist).' % (user_name, chat_id))
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %s.') % (_('"Show walking distance/time"'), pref.get('walk_dist')))
        return

    try:
        wdist = args[0].lower()
        LOGGER.info('[%s@%s] Setting walkdist.' % (user_name, chat_id))

        if wdist == 'true' or wdist == 'false':
            wdist = False
            if args[0].lower() == 'true':
                wdist = True
            pref.set('walk_dist', wdist)
            bot.sendMessage(chat_id, text=_('%s was set to %s.') % (_('"Show walking distance/time"'), wdist))
        else:
            bot.sendMessage(chat_id, text=_('Please only use True (enable) or False (disable).'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/walkdist true/false'))


def cmd_add(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'add'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/add pokedexID') + _(' or ') + _('/add pokedexID1 pokedexID2 ...')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    add_job(update, job_queue)
    LOGGER.info('[%s@%s] Add pokemon.' % (user_name, chat_id))

    try:
        search = pref.get('search_ids', [])
        for x in args:
            if int(x) >= min_pokemon_id and int(x) <= max_pokemon_id and int(
                    x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)


def cmd_add_by_rarity(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'addByRarity'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/addbyrarity 1-5')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    add_job(update, job_queue)
    LOGGER.info('[%s@%s] Add pokemon by rarity.' % (user_name, chat_id))

    try:
        rarity = int(args[0])

        if rarity < 1 or rarity > 5:
            bot.sendMessage(chat_id, text=usage_message)
            return

        search = pref.get('search_ids', [])
        for x in pokemon_rarity[rarity]:
            if int(x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)


def cmd_clear(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'clear'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    bot.sendMessage(chat_id, text=_('Your settings were successfully reset.'))

    # Removes the job if the user changed their mind
    LOGGER.info('[%s@%s] Clear list.' % (user_name, chat_id))

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


def cmd_remove(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'remove'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] Remove pokemon.' % (user_name, chat_id))

    try:
        search = pref.get('search_ids', [])
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('search_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/rem pokedexID'))


def cmd_add_raid_by_level(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'addraidbylevel'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:')  + '\n' + _('/addraidbylevel 1-5')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    add_job(update, job_queue)
    LOGGER.info('[%s@%s] Add raid pokemon by level.' % (user_name, chat_id))

    try:
        level = int(args[0])

        if level < 1 or level > 5:
            bot.sendMessage(chat_id, text=usage_message)
            return

        search = pref.get('raid_ids', [])
        for x in raid_levels[level]:
            if int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('raid_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)


def cmd_add_raid(bot, update, args, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'addraid'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/addraid pokedexID') + _(' or ') + _('/addraid pokedexID1 pokedexID2 ...')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    add_job(update, job_queue)
    LOGGER.info('[%s@%s] Add raid.' % (user_name, chat_id))

    try:
        search = pref.get('raid_ids', [])
        for x in args:
            if int(x) >= min_pokemon_id and int(x) <= max_pokemon_id and int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('raid_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)


def cmd_remove_raid(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'removeraid'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] Remove raid.' % (user_name, chat_id))

    try:
        search = pref.get('raid_ids', [])
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('raid_ids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/remraid pokedexID'))


def cmd_list(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'list'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] List.' % (user_name, chat_id))

    try:
        lan = pref.get('language')
        dists = pref.get('search_dists', {})
        minivs = pref.get('search_miniv', {})
        mincps = pref.get('search_mincp', {})
        minlevels = pref.get('search_minlevel', {})
        matchmodes = pref.get('search_matchmode', {})
        user_location = pref.get('location')
        if user_location[0] is None:
            tmp = _('*List of watched Pokémon:*') + '\n'
        else:
            tmp = _('*List of watched Pokémon within a radius of %.2fkm:*') % (user_location[2]) + '\n'
        for x in pref.get('search_ids', []):
            pkm_id = str(x)
            tmp += "%s %s" % (pkm_id, pokemon_name[lan][pkm_id])
            if pkm_id in dists:
                tmp += " %.2fkm" % (dists[pkm_id])
            if pkm_id in minivs:
                tmp += " %d%%" % (minivs[pkm_id])
            if pkm_id in mincps:
                tmp += " %dWP" % (mincps[pkm_id]) if lan == 'de' else " %dCP" % (mincps[pkm_id])
            if pkm_id in minlevels:
                tmp += " L%d" % (minlevels[pkm_id])
            if pkm_id in matchmodes:
                if matchmodes[pkm_id] == 0:
                    tmp += " UND" if lan == 'de' else " AND"
                if matchmodes[pkm_id] == 1:
                    tmp += " ODER1" if lan == 'de' else " OR1"
                if matchmodes[pkm_id] == 2:
                    tmp += " ODER2" if lan == 'de' else " OR2"
            tmp += "\n"

        tmp += "\n"
        if user_location[0] is None:
            tmp += _('*List of watched Raid Pokémon:*') + '\n'
        else:
            tmp += _('*List of watched Raid Pokémon within a radius of %.2fkm:*') % (user_location[2]) + '\n'
        raid_dists = pref.get('raid_dists', {})
        for x in pref.get('raid_ids', []):
            pkm_id = str(x)
            tmp += "%s %s" % (pkm_id, pokemon_name[lan][pkm_id])
            if pkm_id in raid_dists:
                tmp += " %.2fkm" % (raid_dists[pkm_id])
            tmp += "\n"

        bot.sendMessage(chat_id, text=tmp, parse_mode='Markdown')

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))


def cmd_lang(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'lang'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %s.') % (_('The language'), pref.get('language')))
        return

    try:
        lan = args[0]
        LOGGER.info('[%s@%s] Setting lang.' % (user_name, chat_id))

        if lan == 'de' or lan == 'en':
            pref.set('language', lan)
            bot.sendMessage(chat_id, text=_('%s was set to %s.') % (_('The language'), lan))
        else:
            bot.sendMessage(chat_id, text=_('This language isn\'t available.'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/lang de/en'))


def set_user_location(user_name, chat_id, latitude, longitude, radius):
    pref = prefs.get(chat_id)
    if radius is not None and radius < 0.1:
        radius = 0.1
    pref.set('location', [latitude, longitude, radius])
    LOGGER.info('[%s@%s] Setting scan location to Lat %s, Lon %s, R %s' %
                (user_name, chat_id, latitude, longitude, radius))


def send_current_location(bot, chat_id, set_new=False):
    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    user_location = pref.get('location')
    if user_location[0] is None:
        bot.sendMessage(chat_id, text=_('You have not supplied a scan location.'))
    else:
        if set_new:
            bot.sendMessage(chat_id, text=_('Setting new scan location with radius %skm:') % (user_location[2]))
        else:
            bot.sendMessage(chat_id, text=_('This is your current scan location with radius %skm:') % (user_location[2]))
        bot.sendLocation(chat_id, user_location[0], user_location[1], disable_notification=True)


def cmd_location(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'location'):
        return

    pref = prefs.get(chat_id)
    user_location = update.message.location
    set_user_location(user_name, chat_id, user_location.latitude, user_location.longitude,
                      pref.get('location')[2])
    send_current_location(bot, chat_id, True)


def cmd_location_str(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'location_str'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        send_current_location(bot, chat_id)
        return

    try:
        user_location = geo_locator.geocode(' '.join(args))
        set_user_location(user_name, chat_id, user_location.latitude, user_location.longitude,
                          pref.get('location')[2])
        send_current_location(bot, chat_id, True)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('The location was not found (or OpenStreetMap is down).'))
        return


def cmd_radius(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'radius'):
        return

    if len(args) < 1:
        send_current_location(bot, chat_id)
        return

    pref = prefs.get(chat_id)
    user_location = pref.get('location')
    set_user_location(user_name, chat_id, user_location[0], user_location[1], float(args[0]))
    send_current_location(bot, chat_id, True)


def cmd_clear_location(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'clearlocation'):
        return

    set_user_location(user_name, chat_id, None, None, 1)

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))
    bot.sendMessage(chat_id, text=_('Your scan location has been removed.'))


def cmd_pkm_radius(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'pkmradius'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/pkmradius pokedexID km')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(
            pkm_id) not in pokemon_blacklist:
        dists = pref.get('search_dists', {})

        # Only get current value
        if len(args) < 2:
            pkm_dist = dists[pkm_id] if pkm_id in dists else pref.get('location')[2]
            bot.sendMessage(chat_id, text=_('%s for %s is currently set to %skm.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id], pkm_dist))
            return

        # Change the radius for a specific pokemon
        pkm_dist = float(args[1])
        if pkm_dist < 0.1:
            pkm_dist = 0.1

        dists[pkm_id] = pkm_dist
        pref.set('search_dists', dists)
        bot.sendMessage(chat_id, text=_('%s for %s was set to %skm.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id], pkm_dist))


def cmd_rem_pkm_radius(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'rempkmradius'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/rempkmradius pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    # Change the radius for a specific pokemon
    dists = pref.get('search_dists', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in dists:
        del dists[pkm_id]
        pref.set('search_dists', dists)
        bot.sendMessage(chat_id, text=_('%s for %s was reset.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id]))


def cmd_raid_radius(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'raidradius'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/raidradius pokedexID km')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id:
        dists = pref.get('raid_dists', {})

        # Only get current value
        if len(args) < 2:
            pkm_dist = dists[pkm_id] if pkm_id in dists else pref.get('location')[2]
            bot.sendMessage(chat_id, text=_('%s for %s is currently set to %skm.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id], pkm_dist))
            return

        # Change the radius for a specific raid pokemon
        pkm_dist = float(args[1])
        if pkm_dist < 0.1:
            pkm_dist = 0.1

        dists[pkm_id] = pkm_dist
        pref.set('raid_dists', dists)
        bot.sendMessage(chat_id, text=_('%s for %s was set to %skm.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id], pkm_dist))


def cmd_remraidradius(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'remraidradius'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/remraidradius pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    # Change the radius for a specific raid pokemon
    dists = pref.get('raid_dists', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in dists:
        del dists[pkm_id]
        pref.set('raid_dists', dists)
        bot.sendMessage(chat_id, text=_('%s for %s was reset.') % (_('The search radius'), pokemon_name[pref.get('language')][pkm_id]))


def cmd_iv(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'iv'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s are currently set to %s.') % (_('The minimum IVs'), pref.get('miniv', 0)))
        return

    miniv = int(args[0])
    if miniv < 0:
        miniv = 0
    if miniv > 100:
        miniv = 100

    pref.set('miniv', miniv)
    bot.sendMessage(chat_id, text=_('%s were set to %d%%.') % (_('The minimum IVs'), pref.get('miniv', 0)))


def cmd_pkm_iv(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'pkmiv'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/pkmiv pokedexID 0-100')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(
            pkm_id) not in pokemon_blacklist:
        minivs = pref.get('search_miniv', {})

        # Only get current value
        if len(args) < 2:
            pkm_miniv = minivs[pkm_id] if pkm_id in minivs else pref.get('miniv', 0)
            bot.sendMessage(chat_id, text=_('%s for %s are currently set to %d%%.') % (_('The minimum IVs'), pokemon_name[pref.get('language')][pkm_id], pref.get('miniv', 0)))
            return

        # Change the radius for a specific pokemon
        pkm_miniv = int(args[1])
        if pkm_miniv < 0:
            pkm_miniv = 0
        if pkm_miniv > 100:
            pkm_miniv = 100

        minivs[pkm_id] = pkm_miniv
        pref.set('search_miniv', minivs)
        bot.sendMessage(chat_id, text=_('%s for %s were set to %d%%.') % (_('The minimum IVs'), pokemon_name[pref.get('language')][pkm_id], pkm_miniv))


def cmd_rem_pkm_iv(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'rempkmiv'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/rempkmiv pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    minivs = pref.get('search_miniv', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in minivs:
        del minivs[pkm_id]
        pref.set('search_miniv', minivs)
        bot.sendMessage(chat_id, text=_('%s for %s were reset.') % (_('The minimum IVs'), pokemon_name[pref.get('language')][pkm_id]))


def cmd_cp(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'cp'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %dCP.') % (_('The minimum CP'), pref.get('mincp', 0)))
        return

    mincp = int(args[0])
    if mincp < 0:
        mincp = 0
    if mincp > 4760:
        mincp = 4760

    pref.set('mincp', mincp)
    bot.sendMessage(chat_id, text=_('%s was set to %dCP.') % (_('The minimum CP'), mincp))


def cmd_pkm_cp(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'pkmcp'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/pkmcp pokedexID 0-4548')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(
            pkm_id) not in pokemon_blacklist:
        mincps = pref.get('search_mincp', {})

        # Only get current value
        if len(args) < 2:
            pkm_mincp = mincps[pkm_id] if pkm_id in mincps else pref.get('mincp', 0)
            bot.sendMessage(chat_id, text=_('%s for %s is currently set to %dCP.') % (_('The minimum CP'), pokemon_name[pref.get('language')][pkm_id], pkm_mincp))
            return

        pkm_mincp = int(args[1])
        if pkm_mincp < 0:
            pkm_mincp = 0
        if pkm_mincp > 4760:
            pkm_mincp = 4760

        mincps[pkm_id] = pkm_mincp
        pref.set('search_mincp', mincps)
        bot.sendMessage(chat_id, text=_('%s for %s was set to %dCP.') % (_('The minimum CP'), pokemon_name[pref.get('language')][pkm_id], pkm_mincp))


def cmd_rem_pkm_cp(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'rempkmcp'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/rempkmcp pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    mincps = pref.get('search_mincp', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in mincps:
        del mincps[pkm_id]
        pref.set('search_mincp', mincps)
        bot.sendMessage(chat_id, text=_('%s for %s was reset.') % (_('The minimum CP'), pokemon_name[pref.get('language')][pkm_id]))


def cmd_level(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'level'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %d.') % (_('The minimum level'), pref.get('minlevel', 0)))
        return

    minlevel = int(args[0])
    if minlevel < 0:
        minlevel = 0
    if minlevel > 30:
        minlevel = 30

    pref.set('minlevel', minlevel)
    bot.sendMessage(chat_id, text=_('%s was set to %d.') % (_('The minimum level'), minlevel))


def cmd_pkm_level(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'pkmlevel'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/pkmlevel pokedexID 0-30')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(
            pkm_id) not in pokemon_blacklist:
        minlevels = pref.get('search_minlevel', {})

        # Only get current value
        if len(args) < 2:
            pkm_minlevel = minlevels[pkm_id] if pkm_id in minlevels else pref.get('minlevel', 0)
            bot.sendMessage(chat_id, text=_('%s for %s is currently set to %d.') % (_('The minimum level'), pokemon_name[pref.get('language')][pkm_id], pkm_minlevel))
            return

        pkm_minlevel = int(args[1])
        if pkm_minlevel < 0:
            pkm_minlevel = 0
        if pkm_minlevel > 30:
            pkm_minlevel = 30

        minlevels[pkm_id] = pkm_minlevel
        pref.set('search_minlevel', minlevels)
        bot.sendMessage(chat_id, text=_('%s for %s was set to %d.') % (_('The minimum level'), pokemon_name[pref.get('language')][pkm_id], pkm_minlevel))


def cmd_rem_pkm_level(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'rempkmlevel'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/rempkmlevel pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    minlevels = pref.get('search_minlevel', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in minlevels:
        del minlevels[pkm_id]
        pref.set('search_minlevel', minlevels)
        bot.sendMessage(chat_id, text=_('%s for %s was reset.') % (_('The minimum level'), pokemon_name[pref.get('language')][pkm_id]))


def cmd_matchmode(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'matchmode'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('%s is currently set to %s.') % (_('The Distance/IVs/CP/Level matching mode'), pref.get('match_mode', 0)))
        return

    try:
        matchmode = int(args[0])
        LOGGER.info('[%s@%s] Setting matchmode.' % (user_name, chat_id))

        if matchmode == 0 or matchmode == 1 or matchmode == 2:
            pref.set('match_mode', matchmode)
            bot.sendMessage(chat_id, text=_('%s was set to %s.') % (_('The Distance/IVs/CP/Level matching mode'), matchmode))
        else:
            bot.sendMessage(chat_id, text=_('Please only use 0, 1 or 2.'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/matchmode 0/1/2'))


def cmd_pkmmatchmode(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'pkmmatchmode'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/pkmmatchmode pokedexID 0/1/2')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    pkm_id = args[0]

    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and int(
            pkm_id) not in pokemon_blacklist:
        matchmodes = pref.get('search_matchmode', {})

        # Only get current value
        if len(args) < 2:
            pkm_matchmode = matchmodes[pkm_id] if pkm_id in matchmodes else pref.get('matchmode', 0)
            bot.sendMessage(chat_id, text=_('%s for %s is currently set to %d.') % (_('The Distance/IVs/CP/Level matching mode'), pokemon_name[pref.get('language')][pkm_id], pkm_matchmode))
            return

        pkm_matchmode = int(args[1])
        if pkm_matchmode < 0:
            pkm_matchmode = 0
        if pkm_matchmode > 2:
            pkm_matchmode = 2

        matchmodes[pkm_id] = pkm_matchmode
        pref.set('search_matchmode', matchmodes)
        bot.sendMessage(chat_id, text=_('%s for %s was set to %d.') % (_('The Distance/IVs/CP/Level matching mode'), pokemon_name[pref.get('language')][pkm_id], pkm_matchmode))


def cmd_rempkmmatchmode(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'rempkmmatchmode'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    usage_message = _('Usage:') + '\n' + _('/rempkmmatchmode pokedexID')

    if len(args) < 1:
        bot.sendMessage(chat_id, text=usage_message)
        return

    matchmodes = pref.get('search_matchmode', {})
    pkm_id = args[0]
    if int(pkm_id) >= min_pokemon_id and int(pkm_id) <= max_pokemon_id and pkm_id in matchmodes:
        del matchmodes[pkm_id]
        pref.set('search_matchmode', matchmodes)
        bot.sendMessage(chat_id, text=_('%s for %s was reset.') % (_('The Distance/IVs/CP/Level matching mode'), pokemon_name[pref.get('language')][pkm_id]))


def is_not_whitelisted(bot, update, command):
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    user_name = update.message.from_user.username
    if chat_id < 0 or not whitelist.is_whitelisted(user_name):
        LOGGER.info('[%s@%s] User blocked (%s).' % (user_name, chat_id, command))
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        return True
    return False


def cmd_add_to_whitelist(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if not whitelist.is_whitelist_enabled():
        bot.sendMessage(chat_id, text=_('Whitelist is disabled.'))
        return
    if not whitelist.is_admin(user_name):
        LOGGER.info('[%s@%s] User blocked (addToWhitelist).' % (user_name, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wladd <username>') + _(' or ') + _('/wladd <username_1> <username_2>'))
        return

    try:
        for x in args:
            whitelist.add_user(x)
        bot.sendMessage(chat_id, "Added to whitelist.")
    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wladd <username>') + _(' or ') + _('/wladd <username_1> <username_2>'))


def cmd_rem_from_whitelist(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if not whitelist.is_whitelist_enabled():
        bot.sendMessage(chat_id, text=_('Whitelist is disabled.'))
        return
    if not whitelist.is_admin(user_name):
        LOGGER.info('[%s@%s] User blocked (remFromWhitelist).' % (user_name, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wlrem <username>') + _(' or ') + _('/wlrem <username_1> <username_2>'))
        return

    try:
        for x in args:
            whitelist.rem_user(x)
        bot.sendMessage(chat_id, text=_('Removed from whitelist.'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wlrem <username>') + _(' or ') + _('/wlrem <username_1> <username_2>'))


def cmd_unknown(bot, update):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'unknown'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    bot.sendMessage(chat_id, text=_('Unfortunately, I do not understand this command.'))


## Functions
def handle_error(bot, update, error):
    LOGGER.warning('Update "%s" caused error "%s"' % (update, error))


def alarm(bot, job):
    chat_id = job.context[0]
    LOGGER.info('[%s] Checking alarm.' % (chat_id))
    check_and_send(bot, chat_id)


def add_job(update, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username
    LOGGER.info('[%s@%s] Adding job.' % (user_name, chat_id))
    add_job_for_chat_id(chat_id, job_queue)


def add_job_for_chat_id(chat_id, job_queue):
    try:
        if chat_id not in jobs:
            job = Job(alarm, 30, repeat=True, context=(chat_id, 'Other'))
            # Add to jobs
            jobs[chat_id] = job
            if not webhook_enabled:
                LOGGER.info('Putting job')
                job_queue.put(job)

            # User dependant
            if chat_id not in sent:
                sent[chat_id] = dict()
            if chat_id not in locks:
                locks[chat_id] = threading.Lock()
            if chat_id not in clearCnt:
                clearCnt[chat_id] = 0

    except Exception as e:
        LOGGER.error('[%s] %s' % (chat_id, repr(e)))


def build_detailed_pokemon_list(chat_id):
    pref = prefs.get(chat_id)
    pokemons = pref.get('search_ids', [])
    if not pokemons:
        return []
    location = pref.get('location')
    miniv = pref.get('miniv', 0)
    mincp = pref.get('mincp', 0)
    minlevel = pref.get('minlevel', 0)
    matchmode = pref.get('match_mode', 0)
    dists = pref.get('search_dists', {})
    minivs = pref.get('search_miniv', {})
    mincps = pref.get('search_mincp', {})
    minlevels = pref.get('search_minlevel', {})
    matchmodes = pref.get('search_matchmode', {})
    pokemon_list = []
    for pkm in pokemons:
        entry = {}
        pkm_id = str(pkm)
        entry['id'] = pkm_id
        entry['iv'] = minivs[pkm_id] if pkm_id in minivs else miniv
        entry['cp'] = mincps[pkm_id] if pkm_id in mincps else mincp
        entry['level'] = minlevels[pkm_id] if pkm_id in minlevels else minlevel
        entry['match_mode'] = matchmodes[pkm_id] if pkm_id in matchmodes else matchmode
        if location[0] is not None:
            radius = dists[pkm_id] if pkm_id in dists else location[2]
            origin = Point(location[0], location[1])
            entry['lat_max'] = vincenty(radius).destination(origin, 0).latitude
            entry['lng_max'] = vincenty(radius).destination(origin, 90).longitude
            entry['lat_min'] = vincenty(radius).destination(origin, 180).latitude
            entry['lng_min'] = vincenty(radius).destination(origin, 270).longitude
        pokemon_list.append(entry)
    return pokemon_list


def build_detailed_raid_list(chat_id):
    pref = prefs.get(chat_id)
    raids = pref.get('raid_ids', [])
    if not raids:
        return []
    location = pref.get('location')
    dists = pref.get('raid_dists', {})
    raid_list = []
    for raid in raids:
        entry = {}
        raid_pkm_id = str(raid)
        entry['id'] = raid_pkm_id
        if location[0] is not None:
            radius = dists[raid_pkm_id] if raid_pkm_id in dists else location[2]
            origin = Point(location[0], location[1])
            entry['lat_max'] = vincenty(radius).destination(origin, 0).latitude
            entry['lng_max'] = vincenty(radius).destination(origin, 90).longitude
            entry['lat_min'] = vincenty(radius).destination(origin, 180).latitude
            entry['lng_min'] = vincenty(radius).destination(origin, 270).longitude
        raid_list.append(entry)
    return raid_list


def check_and_send(bot, chat_id):
    LOGGER.info('[%s] Checking pokemons and raids.' % (chat_id))
    try:
        pref = prefs.get(chat_id)
        set_lang(pref.get('language'))
        pokemons = pref.get('search_ids', [])
        raids = pref.get('raid_ids', [])

        if pokemons:
            send_without = pref.get('send_without', True)

            allpokes = data_source.get_pokemon_by_list(
                build_detailed_pokemon_list(chat_id), send_without)

            if len(allpokes) > 50:
                bot.sendMessage(chat_id, text=_('Your filter rules are matching too many Pokémon.') + '\n' + _('Please check your settings!'))
            else:
                for pokemon in allpokes:
                    send_one_poke(chat_id, pokemon)

        if raids:
            all_raids = data_source.get_raids_by_list(build_detailed_raid_list(chat_id))

            for raid in all_raids:
                send_one_raid(chat_id, raid)

    except Exception as e:
        LOGGER.error('[%s] %s' % (chat_id, repr(e)))


def find_users_by_poke_id(pokemon):
    poke_id = pokemon.get_pokemon_id()
    LOGGER.info('Checking pokemon %s for all users.' % (poke_id))
    for chat_id in jobs:
        if int(poke_id) in prefs.get(chat_id).get('search_ids', []):
            send_one_poke(chat_id, pokemon)


def find_users_by_raid_id(raid):
    raid_id = raid.get_pokemon_id()
    LOGGER.info('Checking raid pokemon %s for all users.' % (raid_id))
    for chat_id in jobs:
        if int(raid_id) in prefs.get(chat_id).get('raid_ids', []):
            send_one_raid(chat_id, raid)


def send_one_poke(chat_id, pokemon):
    pref = prefs.get(chat_id)
    lock = locks[chat_id]
    LOGGER.info('[%s] Trying to send one pokemon notification. %s' % (chat_id,
                                                                      pokemon.get_pokemon_id()))

    lock.acquire()
    try:
        encounter_id = pokemon.get_encounter_id()
        pok_id = str(pokemon.get_pokemon_id())
        latitude = pokemon.get_latitude()
        longitude = pokemon.get_longitude()
        disappear_time = pokemon.get_disappear_time()
        iv = pokemon.get_ivs()
        move1 = pokemon.get_move1()
        move2 = pokemon.get_move2()
        cp = pokemon.get_cp()
        level = pokemon.get_level()

        mySent = sent[chat_id]

        send_poke_without_iv = pref.get('send_without', True)
        lan = pref.get('language')

        delta = disappear_time - datetime.utcnow()
        deltaStr = '%02dm %02ds' % (int(delta.seconds / 60), int(delta.seconds % 60))
        disappear_time_str = disappear_time.replace(tzinfo=timezone.utc).astimezone(
            tz=None).strftime("%H:%M:%S")

        if encounter_id in mySent:
            LOGGER.info('[%s] Not sending pokemon notification. Already sent. %s' % (chat_id,
                                                                                     pok_id))
            lock.release()
            return

        if delta.seconds <= 0:
            LOGGER.info('[%s] Not sending pokemon notification. Already disappeared. %s' % (chat_id,
                                                                                            pok_id))
            lock.release()
            return

        if iv is None and not send_poke_without_iv:
            LOGGER.info('[%s] Not sending pokemon notification. Has no IVs. %s' % (chat_id, pok_id))
            lock.release()
            return

        location_data = pref.preferences.get('location')

        dists = pref.get('search_dists', {})
        if pok_id in dists:
            location_data[2] = dists[pok_id]

        matchmode = pref.preferences.get('match_mode', 0)

        matchmodes = pref.get('search_matchmode', {})
        if pok_id in matchmodes:
            matchmode = matchmodes[pok_id]

        if matchmode < 2:
            if location_data[0] is not None and not pokemon.filter_by_location(location_data):
                LOGGER.info('[%s] Not sending pokemon notification. Too far away. %s' % (chat_id,
                                                                                         pok_id))
                lock.release()
                return

        if webhook_enabled:

            miniv = pref.preferences.get('miniv', 0)
            mincp = pref.preferences.get('mincp', 0)
            minlevel = pref.preferences.get('minlevel', 0)

            minivs = pref.get('search_miniv', {})
            if pok_id in minivs:
                miniv = minivs[pok_id]

            mincps = pref.get('search_mincp', {})
            if pok_id in mincps:
                mincp = mincps[pok_id]

            minlevels = pref.get('search_minlevel', {})
            if pok_id in minlevels:
                minlevel = minlevels[pok_id]

            if matchmode == 0:
                if iv is not None and iv < miniv:
                    LOGGER.info('[%s] Not sending pokemon notification. IV filter mismatch. %s' %
                                (chat_id, pok_id))
                    lock.release()
                    return
                if cp is not None and cp < mincp:
                    LOGGER.info('[%s] Not sending pokemon notification. CP filter mismatch. %s' %
                                (chat_id, pok_id))
                    lock.release()
                    return
                if level is not None and level < minlevel:
                    LOGGER.info('[%s] Not sending pokemon notification. Level filter mismatch. %s' %
                                (chat_id, pok_id))
                    lock.release()
                    return

            if matchmode > 0:
                if (iv is not None and iv < miniv) and (cp is not None and
                                                        cp < mincp) and (level is not None and
                                                                         level < minlevel):
                    LOGGER.info(
                        '[%s] Not sending pokemon notification: IV/CP/Level filter mismatch. %s' %
                        (chat_id, pok_id))
                    lock.release()
                    return

        LOGGER.info('[%s] Sending one pokemon notification. %s' % (chat_id, pok_id))

        title = pokemon_name[lan][pok_id]

        if iv is not None:
            title += " %s%%" % iv

        if cp is not None:
            if lan == 'de':
                title += " %dWP" % cp
            else:
                title += " %dCP" % cp

        if level is not None:
            title += " L%d" % level

        address = "💨 %s ⏱ %s" % (disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walk_dist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += " 📍%dm" % int(1000 * walkin_data['walk_dist'])
                else:
                    title += " 📍%skm" % walkin_data['walk_dist']
                address += " 🚶%s" % walkin_data['walk_time']
            else:
                dist = round(pokemon.get_distance(location_data), 2)
                if dist < 1:
                    title += " 📍%dm" % int(1000 * dist)
                else:
                    title += " 📍%skm" % dist

        if move1 is not None and move2 is not None:
            moveNames = move_name['en']
            if lan in move_name:
                moveNames = move_name[lan]
            # Use language if other move languages are available.
            move1Name = moveNames[str(move1)] if str(move1) in moveNames else '?'
            move2Name = moveNames[str(move2)] if str(move2) in moveNames else '?'
            address += "\n⚔ %s / %s" % (move1Name, move2Name)

        mySent[encounter_id] = disappear_time

        if pref.get('only_map'):
            telegram_bot.sendVenue(chat_id, latitude, longitude, title, address)
        else:
            if pref.get('stickers'):
                telegram_bot.sendSticker(
                    chat_id, sticker_list.get(str(pok_id)), disable_notification=True)
            telegram_bot.sendLocation(chat_id, latitude, longitude, disable_notification=True)
            telegram_bot.sendMessage(
                chat_id, text='<b>%s</b> \n%s' % (title, address), parse_mode='HTML')

    except Exception as e:
        LOGGER.error('[%s] %s' % (chat_id, repr(e)))
    lock.release()

    # Clean already disappeared pokemon
    # 2016-08-19 20:10:10.000000
    # 2016-08-19 20:10:10
    lock.acquire()
    if clearCnt[chat_id] > clearCntThreshold:
        clearCnt[chat_id] = 0
        LOGGER.info('[%s] Cleaning sentlist.' % (chat_id))
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
            LOGGER.error('[%s] %s' % (chat_id, repr(e)))
    else:
        clearCnt[chat_id] = clearCnt[chat_id] + 1
    lock.release()


def send_one_raid(chat_id, raid):
    pref = prefs.get(chat_id)
    lock = locks[chat_id]
    LOGGER.info('[%s] Trying to send one raid notification. %s' % (chat_id, raid.get_pokemon_id()))

    lock.acquire()
    try:
        gym_id = raid.get_gym_id()
        name = raid.get_name()
        latitude = raid.get_latitude()
        longitude = raid.get_longitude()
        end = raid.get_end()
        pok_id = str(raid.get_pokemon_id())
        cp = raid.get_cp()
        move1 = raid.get_move1()
        move2 = raid.get_move2()

        raid_id = str(gym_id) + str(end)

        mySent = sent[chat_id]

        lan = pref.get('language')

        delta = end - datetime.utcnow()
        deltaStr = '%02dh %02dm' % (int(delta.seconds / 3600), int((delta.seconds / 60) % 60))
        disappear_time_str = end.replace(tzinfo=timezone.utc).astimezone(
            tz=None).strftime("%H:%M:%S")

        if raid_id in mySent:
            LOGGER.info('[%s] Not sending raid notification. Already sent. %s' % (chat_id, pok_id))
            lock.release()
            return

        if delta.seconds <= 0:
            LOGGER.info('[%s] Not sending raid notification. Already ended. %s' % (chat_id, pok_id))
            lock.release()
            return

        location_data = pref.preferences.get('location')

        dists = pref.get('raid_dists', {})
        if pok_id in dists:
            location_data[2] = dists[pok_id]

        if location_data[0] is not None and not raid.filter_by_location(location_data):
            LOGGER.info('[%s] Not sending raid notification. Too far away. %s' % (chat_id, pok_id))
            lock.release()
            return

        LOGGER.info('[%s] Sending one notification. %s' % (chat_id, pok_id))

        title = "👹 " + pokemon_name[lan][pok_id]

        if cp is not None:
            if lan == 'de':
                title += " %dWP" % cp
            else:
                title += " %dCP" % cp

        address = "📍 %s\n💨 %s ⏱ %s" % (name, disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walk_dist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += " 📍%dm" % int(1000 * walkin_data['walk_dist'])
                else:
                    title += " 📍%skm" % walkin_data['walk_dist']
                address += " 🚶%s" % walkin_data['walk_time']
            else:
                dist = round(raid.get_distance(location_data), 2)
                if dist < 1:
                    title += " 📍%dm" % int(1000 * dist)
                else:
                    title += " 📍%skm" % dist

        if move1 is not None and move2 is not None:
            moveNames = move_name['en']
            if lan in move_name:
                moveNames = move_name[lan]
            # Use language if other move languages are available.
            move1Name = moveNames[str(move1)] if str(move1) in moveNames else '?'
            move2Name = moveNames[str(move2)] if str(move2) in moveNames else '?'
            address += "\n⚔ %s / %s" % (move1Name, move2Name)

        mySent[raid_id] = end

        if pref.get('only_map'):
            telegram_bot.sendVenue(chat_id, latitude, longitude, title, address)
        else:
            if pref.get('stickers'):
                telegram_bot.sendSticker(
                    chat_id, sticker_list.get(str(pok_id)), disable_notification=True)
            telegram_bot.sendLocation(chat_id, latitude, longitude, disable_notification=True)
            telegram_bot.sendMessage(
                chat_id, text='<b>%s</b> \n%s' % (title, address), parse_mode='HTML')

    except Exception as e:
        LOGGER.error('[%s] %s' % (chat_id, repr(e)))
    lock.release()

    # Clean already disappeared raids
    # 2016-08-19 20:10:10.000000
    # 2016-08-19 20:10:10
    lock.acquire()
    if clearCnt[chat_id] > clearCntThreshold:
        clearCnt[chat_id] = 0
        LOGGER.info('[%s] Cleaning sentlist.' % (chat_id))
        try:
            current_time = datetime.utcnow()
            toDel = []
            for raid_id in mySent:
                time = mySent[raid_id]
                if time < current_time:
                    toDel.append(raid_id)
            for raid_id in toDel:
                del mySent[raid_id]
        except Exception as e:
            LOGGER.error('[%s] %s' % (chat_id, repr(e)))
    else:
        clearCnt[chat_id] = clearCnt[chat_id] + 1
    lock.release()


def read_config():
    config_path = os.path.join(os.path.dirname(sys.argv[0]), "config-bot.json")
    LOGGER.info('Reading config: <%s>' % config_path)
    global config

    try:
        with open(config_path, "r", encoding='utf-8') as f:
            config = json.loads(f.read())

    except Exception as e:
        LOGGER.error('%s' % (repr(e)))
        config = {}

    report_config()


def report_config():
    admins_list = config.get('LIST_OF_ADMINS', [])
    tmp = ''
    for admin in admins_list:
        tmp = '%s, %s' % (tmp, admin)
    tmp = tmp[2:]
    LOGGER.info('LIST_OF_ADMINS: <%s>' % (tmp))
    LOGGER.info('TELEGRAM_TOKEN: <%s>' % (config.get('TELEGRAM_TOKEN', None)))
    LOGGER.info('GMAPS_KEY: <%s>' % (config.get('GMAPS_KEY', None)))
    LOGGER.info('SCANNER_NAME: <%s>' % (config.get('SCANNER_NAME', None)))
    LOGGER.info('DB_TYPE: <%s>' % (config.get('DB_TYPE', None)))
    LOGGER.info('DB_CONNECT: <%s>' % (config.get('DB_CONNECT', None)))
    LOGGER.info('DEFAULT_LANG: <%s>' % (config.get('DEFAULT_LANG', None)))
    LOGGER.info('SEND_MAP_ONLY: <%s>' % (config.get('SEND_MAP_ONLY', None)))
    LOGGER.info('STICKERS: <%s>' % (config.get('STICKERS', None)))
    LOGGER.info('SEND_POKEMON_WITHOUT_IV: <%s>' % (config.get('SEND_POKEMON_WITHOUT_IV', None)))


def read_pokemon_names(loc):
    LOGGER.info('Reading pokemon names. <%s>' % loc)
    config_path = "locales/pokemon." + loc + ".json"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            pokemon_name[loc] = json.loads(f.read())

    except Exception as e:
        LOGGER.error('%s' % (repr(e)))


def read_move_names(loc):
    LOGGER.info('Reading move names. <%s>' % loc)
    config_path = "locales/moves." + loc + ".json"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            move_name[loc] = json.loads(f.read())

    except Exception as e:
        LOGGER.error('%s' % (repr(e)))


# Returns a set with walking dist and walking duration via Google Distance Matrix API
def get_walking_data(user_location, lat, lng):
    data = {'walk_dist': 'unknown', 'walk_time': 'unknown'}
    if gmaps_client is None:
        LOGGER.error('Google Maps Client not available. Unable to get walking data.')
        return data
    if user_location[0] is None:
        LOGGER.error('No location has been set. Unable to get walking data.')
        return data
    origin = "{},{}".format(user_location[0], user_location[1])
    dest = "{},{}".format(lat, lng)
    try:
        result = gmaps_client.distance_matrix(origin, dest, mode='walking', units='metric')
        result = result.get('rows')[0].get('elements')[0]
        data['walk_dist'] = float(result.get('distance').get('text').replace(' km', ''))
        data['walk_time'] = result.get('duration').get('text').replace(' hours', 'h').replace(
            ' hour', 'h').replace(' mins', 'm').replace(' min', 'm')

    except Exception as e:
        LOGGER.error('Encountered error while getting walking data (%s)' % (repr(e)))
    return data


def main():
    LOGGER.info('Starting...')
    read_config()

    # Read lang files
    path_to_local = 'locales/'
    for file in os.listdir(path_to_local):
        if fnmatch.fnmatch(file, 'pokemon.*.json'):
            read_pokemon_names(file.split('.')[1])
        if fnmatch.fnmatch(file, 'moves.*.json'):
            read_move_names(file.split('.')[1])

    db_type = config.get('DB_TYPE', None)
    scanner_name = config.get('SCANNER_NAME', None)

    global data_source
    global webhook_enabled
    global iv_available

    if db_type == 'mysql':
        if scanner_name == 'pokemongo-map-iv':
            iv_available = True
            data_source = DataSources.DSRocketMapIVMysql(config.get('DB_CONNECT', None))
    elif db_type == 'webhook':
        webhook_enabled = True
        if scanner_name == 'pokemongo-map-iv':
            iv_available = True
            data_source = DataSources.DSRocketMapIVWebhook(
                config.get('DB_CONNECT', None), find_users_by_poke_id, find_users_by_raid_id)
    if not data_source:
        raise Exception("The combination SCANNER_NAME, DB_TYPE is not available: %s,%s" %
                        (scanner_name, db_type))

    global whitelist
    whitelist = Whitelist.Whitelist(config)

    #ask it to the bot father in telegram
    token = config.get('TELEGRAM_TOKEN', None)
    updater = Updater(token)

    global telegram_bot
    telegram_bot = Bot(token)
    LOGGER.info("BotName: <%s>" % (telegram_bot.name))

    # Get the Google Maps API
    global gmaps_client
    google_key = config.get('GMAPS_KEY', None)
    gmaps_client = googlemaps.Client(
        key=google_key, timeout=3, retry_timeout=4) if google_key is not None else None

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", cmd_start, pass_job_queue=True))
    dp.add_handler(CommandHandler("stop", cmd_stop))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("clear", cmd_clear))
    dp.add_handler(CommandHandler("add", cmd_add, pass_args=True, pass_job_queue=True))
    dp.add_handler(
        CommandHandler("addbyrarity", cmd_add_by_rarity, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler("rem", cmd_remove, pass_args=True))
    dp.add_handler(CommandHandler("addraid", cmd_add_raid, pass_args=True, pass_job_queue=True))
    dp.add_handler(
        CommandHandler(
            "addraidbylevel", cmd_add_raid_by_level, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler("remraid", cmd_remove_raid, pass_args=True))
    dp.add_handler(CommandHandler("list", cmd_list))
    dp.add_handler(CommandHandler("lang", cmd_lang, pass_args=True))
    dp.add_handler(CommandHandler("radius", cmd_radius, pass_args=True))
    dp.add_handler(CommandHandler("location", cmd_location_str, pass_args=True))
    dp.add_handler(CommandHandler("remloc", cmd_clear_location))
    dp.add_handler(MessageHandler(Filters.location, cmd_location))
    dp.add_handler(CommandHandler("wladd", cmd_add_to_whitelist, pass_args=True))
    dp.add_handler(CommandHandler("wlrem", cmd_rem_from_whitelist, pass_args=True))
    dp.add_handler(CommandHandler("stickers", cmd_stickers, pass_args=True))
    dp.add_handler(CommandHandler("maponly", cmd_map_only, pass_args=True))
    dp.add_handler(CommandHandler("walkdist", cmd_walk_dist, pass_args=True))
    dp.add_handler(CommandHandler("pkmradius", cmd_pkm_radius, pass_args=True))
    dp.add_handler(CommandHandler("rempkmradius", cmd_rem_pkm_radius, pass_args=True))
    dp.add_handler(CommandHandler("raidradius", cmd_raid_radius, pass_args=True))
    dp.add_handler(CommandHandler("remraidradius", cmd_remraidradius, pass_args=True))
    dp.add_handler(CommandHandler("iv", cmd_iv, pass_args=True))
    dp.add_handler(CommandHandler("cp", cmd_cp, pass_args=True))
    dp.add_handler(CommandHandler("wp", cmd_cp, pass_args=True))
    dp.add_handler(CommandHandler("level", cmd_level, pass_args=True))
    dp.add_handler(CommandHandler("matchmode", cmd_matchmode, pass_args=True))
    dp.add_handler(CommandHandler("pkmiv", cmd_pkm_iv, pass_args=True))
    dp.add_handler(CommandHandler("pkmcp", cmd_pkm_cp, pass_args=True))
    dp.add_handler(CommandHandler("pkmwp", cmd_pkm_cp, pass_args=True))
    dp.add_handler(CommandHandler("pkmlevel", cmd_pkm_level, pass_args=True))
    dp.add_handler(CommandHandler("pkmmatchmode", cmd_pkmmatchmode, pass_args=True))
    dp.add_handler(CommandHandler("rempkmiv", cmd_rem_pkm_iv, pass_args=True))
    dp.add_handler(CommandHandler("rempkmcp", cmd_rem_pkm_cp, pass_args=True))
    dp.add_handler(CommandHandler("rempkmwp", cmd_rem_pkm_cp, pass_args=True))
    dp.add_handler(CommandHandler("rempkmlevel", cmd_rem_pkm_level, pass_args=True))
    dp.add_handler(CommandHandler("rempkmmatchmode", cmd_rempkmmatchmode, pass_args=True))
    dp.add_handler(CommandHandler("sendwithout", cmd_send_without, pass_args=True))
    dp.add_handler(CommandHandler("wo", cmd_find_gym, pass_args=True))
    dp.add_handler(CommandHandler("where", cmd_find_gym, pass_args=True))
    dp.add_handler(MessageHandler(Filters.command, cmd_unknown))
    dp.add_handler(CallbackQueryHandler(cb_button))

    # log all errors
    dp.add_error_handler(handle_error)

    # add the configuration to the preferences
    prefs.add_config(config)

    # Start the Bot
    updater.start_polling(bootstrap_retries=3, read_latency=5)
    j = updater.job_queue

    LOGGER.info('Started!')

    # Send restart notification to all known users
    userdirectory = 'userdata/'
    for file in os.listdir(userdirectory):
        if fnmatch.fnmatch(file, '*.json'):
            chat_id = int(file.split('.')[0])
            pref = prefs.get(chat_id)
            pref.load()
            if pref.get('search_ids', []) or pref.get('raid_ids', []):
                add_job_for_chat_id(chat_id, j)

    # Block until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

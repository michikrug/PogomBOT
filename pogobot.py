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
from telegram import (Bot, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup)
from telegram.ext import (CallbackQueryHandler, CommandHandler,
                          ConversationHandler, Filters, Job, MessageHandler,
                          RegexHandler, Updater)

import DataSources
import Preferences
import Whitelist
from Stickers import sticker_list

if sys.version_info[0] < 3:
    raise Exception('Must be using Python 3')

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

raid_levels = [[], ["361", "355", "353", "333", "129"], ["303", "302", "215", "200", "103"],
               ["221", "210", "127", "124", "94", "68"], ["365", "359", "306", "248",
                                                          "229"], ["381", "380", "150"]]

CHOOSE_LEVEL, CHOOSE_PKM, CHOOSE_GYM, CHOOSE_GYM_SEARCH, CHOOSE_TIME = range(5)


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

    LOGGER.info('[%s@%s] Sending help text' % (user_name, chat_id))

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    text = _("*The PoGo Chemnitz Bot knows the following commands:*") + "\n\n" + \
    _("*General*") + "\n" + \
    _("/start") + " - "  + _("Starts the bot (e.g. after pausing)") + "\n" + \
    _("/stop") + " - "  + _("Pauses the bot (use /start to resume)") + "\n" + \
    _("/language") + " - "  + _("Sets the language of the bot") + "\n" + \
    _("/clear") + " - "  + _("Resets all your settings") + "\n" + \
    _("/help") + " - "  + _("Shows a list of available commands") + "\n" + \
    _("/where") + " - "  + _("Searches for a gym by name and outputs its location") + "\n\n" + \
    _("*Pokémon filter*") + "\n" + \
    _("/add pokedexID") + " - "  + _("Adds Pokémon with the given ID to the scanner") + "\n" + \
    _("/add pokedexID1 pokedexID2 ...") + "\n" + \
    _("/addbyrarity 1-5") + " - "  + _("Adds Pokémon with the given rarity to scanner (1 very common - 5 ultrarare)") + "\n" + \
    _("/remove pokedexID") + " - "  + _("Removes Pokémon with the given ID from the scanner") + "\n" + \
    _("/remove pokedexID1 pokedexID2 ...") + "\n" + \
    _("/list") + " - "  + _("Lists the watched Pokémon and Raid Pokémon") + "\n" + \
    _("/iv") + " - "  + _("Sets the minimum IVs given as percent") + "\n" +\
    _("/cp") + " - "  + _("Sets the minimum CP") + "\n" +\
    _("/level") + " - "  + _("Sets the minimum level") + "\n" +\
    _("/pkmiv") + " - "  + _("Sets the minimum IVs for a specific Pokémon given as percent") + "\n" +\
    _("/resetpkmiv") + " - "  + _("Resets the minimum IVs for a specific Pokémon") + "\n" +\
    _("/pkmcp") + " - "  + _("Sets the minimum CP for a specific Pokémon") + "\n" +\
    _("/resetpkmcp") + " - "  + _("Resets the minimum CP for a specific Pokémon") + "\n" +\
    _("/pkmlevel") + " - "  + _("Sets the minimum level for a specific Pokémon") + "\n" +\
    _("/resetpkmlevel") + " - "  + _("Resets the minimum level for a specific Pokémon") + "\n" +\
    _("/matchmode") + " - "  + _("Sets the match mode (0) Distance AND IVs AND CP AND level / (1) Distance AND IVs OR CP OR level has to match / (2) Distance OR IVs OR CP OR level has to match") + "\n" +\
    _("/pkmmatchmode") + " - "  + _("Set the match mode for a specific Pokémon") + "n" +\
    _("/resetpkmmatchmode") + " - "  + _("Reset the match mode for a specific Pokémon") + "\n\n" +\
    _("*Raid filter*") + "\n" + \
    _("/addraid pokedexID") + " - "  + _("Adds Raid Pokémon with the given ID to the scanner") + "\n" + \
    _("/addraid pokedexID1 pokedexID2 ...") + "\n" + \
    _("/addraidbylevel 1-5") + " - "  + _("Adds Raid Pokémon with the given level to scanner (1-5)") + "\n" + \
    _("/removeraid pokedexID") + " - "  + _("Removes Raid Pokémon with the given ID from the scanner") + "\n" + \
    _("/removeraid pokedexID1 pokedexID2 ...") + "\n\n" + \
    _("*Distance filter*") + "\n" + \
    _("/location address") + " - "  + _("Sets the desired search location given as text") + "\n" +\
    _("/radius km") + " - "  + _("Sets the search radius in km") + "\n" +\
    _("/removelocation") + " - "  + _("Clears the search location and radius") + "\n" +\
    _("/pkmradius") + " - "  + _("Sets the search radius for a specific Pokémon in km") + "\n" +\
    _("/resetpkmradius") + " - "  + _("Resets the search radius for a specific Pokémon") + "\n" +\
    _("/raidradius") + " - "  + _("Sets the search radius for a specific Raid Pokémon in km") + "\n" +\
    _("/resetraidradius") + " - "  + _("Resets the search radius for a specific Raid Pokémon") + "\n\n" +\
    _("*Notification settings*") + "\n" + \
    _("/sendwithout") + " - "  + _("Defines if Pokémon without IV/CP should be sent") + "\n" +\
    _("/stickers") + " - "  + _("Defines if stickers should be sent") + "\n" +\
    _("/maponly") + " - "  + _("Defines if only a map should be sent (without an additional message/sticker)") + "\n\n" +\
    _("Hint: You can also set the scanning location by just sending a location marker")

    bot.sendMessage(chat_id, text, parse_mode='Markdown')


def send_current_value(bot, chat_id, name, value, pkm_id=None):
    if pkm_id:
        pref = prefs.get(chat_id)
        pkm_name = pokemon_name[pref.get('language')][str(pkm_id)]
        if value:
            bot.sendMessage(chat_id,
                            text=_('%s for %s is currently set to *%s*') % (name, pkm_name, value),
                            parse_mode='Markdown')
        else:
            bot.sendMessage(chat_id,
                            text=_('%s for %s is currently not set') % (name, pkm_name),
                            parse_mode='Markdown')
    else:
        bot.sendMessage(chat_id,
                        text=_('%s is currently set to *%s*') % (name, value),
                        parse_mode='Markdown')


def parse_type(data_type, value):
    if data_type == 'bool':
        if value == 'false':
            return False
        return bool(value)
    if data_type == 'int':
        return int(value)
    if data_type == 'str':
        return str(value)
    if data_type == 'float':
        val = float(value)
        if val < 0.1:
            val = 0.1
        return val
    return value


def default_cmd(bot, update, cmd, text=None):
    if is_not_whitelisted(bot, update, cmd):
        return False

    chat_id = update.message.chat_id
    user_name = update.message.from_user.username
    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] %s' % (user_name, chat_id, cmd))

    if text:
        bot.sendMessage(chat_id, text=_(text), parse_mode='Markdown')

    return True


def default_settings_cmd(bot, update, args, setting, data_type=None, valid_options=None):
    if not default_cmd(bot, update, setting):
        return

    chat_id = update.message.chat_id
    pref = prefs.get(chat_id)

    if len(args) < 1:
        send_current_value(bot, chat_id, _(setting), pref.get(setting))
        return

    try:
        parsed_value = parse_type(data_type, args[0].lower())

        if valid_options and parsed_value not in valid_options:
            bot.sendMessage(chat_id,
                            text=_('This is not a valid option for this setting. Valid options: *%s*') % (', '.join(list(map(str, valid_options)))),
                            parse_mode='Markdown')
        else:
            pref.set(setting, parsed_value)
            bot.sendMessage(chat_id,
                            text=_('%s was set to *%s*') % (_(setting), parsed_value),
                            parse_mode='Markdown')

    except Exception as e:
        user_name = update.message.from_user.username
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/' + setting))


def default_pkm_settings_cmd(bot,
                             update,
                             args,
                             setting,
                             data_type=None,
                             valid_options=None,
                             reset=False):
    if not default_cmd(bot, update, setting):
        return

    chat_id = update.message.chat_id

    if len(args) < 1 or (reset and len(args) > 1) or (not reset and len(args) > 2):
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/' + ('reset' if reset else '') + setting))
        return

    pkm_id = str(args[0])

    if int(pkm_id) < min_pokemon_id or int(pkm_id) > max_pokemon_id or int(
            pkm_id) in pokemon_blacklist:
        bot.sendMessage(chat_id,
                        text=_('The stated Pokémon is *blacklisted* and therefore can not be checked.'),
                        parse_mode='Markdown')
        return

    pref = prefs.get(chat_id)
    pkm_name = pokemon_name[pref.get('language')][pkm_id]
    values = pref.get(setting, {})
    pkm_pref = values[pkm_id] if pkm_id in values else None

    if not reset and len(args) < 2:
        send_current_value(bot, chat_id, _(setting), pkm_pref, pkm_id)
        return

    try:
        if not reset:
            parsed_value = parse_type(data_type, args[1].lower())
            if valid_options and parsed_value not in valid_options:
                bot.sendMessage(chat_id,
                                text=_('This is not a valid option for this setting. Valid options: *%s*') % (', '.join(list(map(str, valid_options)))),
                                parse_mode='Markdown')
            else:
                values[pkm_id] = parsed_value
                bot.sendMessage(chat_id,
                                text=_('%s for %s was set to *%s*') % (_(setting), pkm_name, parsed_value),
                                parse_mode='Markdown')
        else:
            if pkm_id in values:
                del values[pkm_id]
            bot.sendMessage(chat_id,
                            text=_('%s for %s was reset') % (_(setting), pkm_name),
                            parse_mode='Markdown')

        pref.set(setting, values)

    except Exception as e:
        user_name = update.message.from_user.username
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/' + ('reset' if reset else '') + setting))


def cmd_stickers(bot, update, args):
    default_settings_cmd(bot, update, args, 'stickers', 'bool')


def cmd_map_only(bot, update, args):
    default_settings_cmd(bot, update, args, 'maponly', 'bool')


def cmd_send_without(bot, update, args):
    default_settings_cmd(bot, update, args, 'sendwithout', 'bool')


def cmd_walk_dist(bot, update, args):
    default_settings_cmd(bot, update, args, 'walkdist', 'bool')


def cmd_lang(bot, update, args):
    default_settings_cmd(bot, update, args, 'language', 'str', ['en', 'de'])


def cmd_iv(bot, update, args):
    default_settings_cmd(bot, update, args, 'iv', 'int', list(range(0, 101)))


def cmd_cp(bot, update, args):
    default_settings_cmd(bot, update, args, 'cp', 'int', list(range(0, 4548)))


def cmd_level(bot, update, args):
    default_settings_cmd(bot, update, args, 'level', 'int', list(range(0, 36)))


def cmd_matchmode(bot, update, args):
    default_settings_cmd(bot, update, args, 'matchmode', 'int', [0, 1, 2])


def cmd_pkm_radius(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmradius', 'float')


def cmd_pkm_radius_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmradius', reset=True)


def cmd_pkm_matchmode(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmmatchmode', 'int', [0, 1, 2])


def cmd_pkm_matchmode_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmmatchmode', reset=True)


def cmd_pkm_iv(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmiv', 'int', list(range(0, 101)))


def cmd_pkm_iv_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmiv', reset=True)


def cmd_pkm_cp(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmcp', 'int', list(range(0, 4548)))


def cmd_pkm_cp_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmcp', reset=True)


def cmd_pkm_level(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmlevel', 'int', list(range(0, 36)))


def cmd_pkm_level_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'pkmlevel', reset=True)


def cmd_raid_radius(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'raidradius', 'float')


def cmd_raid_radius_reset(bot, update, args):
    default_pkm_settings_cmd(bot, update, args, 'raidradius', reset=True)


def cmd_start(bot, update, job_queue):
    chat_id = update.message.chat_id
    pref = prefs.get(chat_id)
    has_entries = pref.get('pkmids', []) or pref.get('raidids', [])

    text = 'Bot was started' if has_entries else 'Hello! You seem to be a new user. Here is a list of available commands:'

    if not default_cmd(bot, update, 'start', text=text):
        return

    if has_entries:
        add_job(update, job_queue)
    else:
        cmd_help(bot, update)


def cmd_stop(bot, update):
    if not default_cmd(bot, update, 'stop', text='Bot was paused. Use /start to resume'):
        return
    cleanup(update.message.chat_id)


def cmd_clear(bot, update):
    if not default_cmd(bot, update, 'clear', text='Your settings were successfully reset'):
        return
    chat_id = update.message.chat_id
    pref = prefs.get(chat_id)
    pref.reset_user()
    cleanup(chat_id)


def cmd_location(bot, update):
    if not default_cmd(bot, update, 'location'):
        return

    chat_id = update.message.chat_id
    pref = prefs.get(chat_id)
    user_location = update.message.location
    set_user_location(chat_id, user_location.latitude, user_location.longitude,
                      pref.get('location')[2])
    send_current_location(bot, chat_id, True)


def cmd_remove_location(bot, update):
    if not default_cmd(bot, update, 'removelocation', text='Your scan location has been removed'):
        return
    set_user_location(update.message.chat_id, None, None, 1)


def print_gym(bot, chat_id, gym):
    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))
    user_location = pref.get('location')
    if chat_id < 0 or user_location[0] is None:
        dist = ''
    else:
        dist = _('Distance: %.2fkm') % (gym.get_distance(user_location))
    bot.sendVenue(chat_id, gym.get_latitude(), gym.get_longitude(), gym.get_name(), dist)


def cb_find_gym(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    gyms = data_source.get_gyms_by_name(gym_name=query.data[10:], use_id=True)
    if gyms:
        print_gym(bot, chat_id, gyms[0])
    bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
    query.answer()


def cmd_find_gym(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if chat_id < 0:
        set_lang(config.get('DEFAULT_LANG', 'en'))
    else:
        pref = prefs.get(chat_id)
        set_lang(pref.get('language'))

    if len(args) < 1:
        bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        return

    try:
        gym_name = ' '.join(args).lower()
        LOGGER.info('[%s@%s] Searching for gym: %s' % (user_name, chat_id, gym_name))

        gyms = data_source.get_gyms_by_name(gym_name=gym_name)

        if len(gyms) == 1:
            print_gym(bot, chat_id, gyms[0])
        elif len(gyms) > 1:
            keyboard = []
            for gym in gyms:
                keyboard.append(
                    [InlineKeyboardButton(gym.get_name(), callback_data='gymsearch_' + gym.get_gym_id())])

            update.message.reply_text(
                _('Multiple gyms were found. Please choose one of the following:'),
                reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            bot.sendMessage(chat_id, text=_('No gym with this name could be found'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/where'))


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
    LOGGER.info('[%s@%s] Add pokemon' % (user_name, chat_id))

    try:
        search = pref.get('pkmids', [])
        for x in args:
            if int(x) >= min_pokemon_id and int(x) <= max_pokemon_id and int(
                    x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('pkmids', search)
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
    LOGGER.info('[%s@%s] Add pokemon by rarity' % (user_name, chat_id))

    try:
        rarity = int(args[0])

        if rarity < 1 or rarity > 5:
            bot.sendMessage(chat_id, text=usage_message)
            return

        search = pref.get('pkmids', [])
        for x in pokemon_rarity[rarity]:
            if int(x) not in search and int(x) not in pokemon_blacklist:
                search.append(int(x))
        search.sort()
        pref.set('pkmids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=usage_message)


def cmd_remove(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'remove'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] Remove pokemon' % (user_name, chat_id))

    try:
        search = pref.get('pkmids', [])
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('pkmids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/remove pokedexID'))


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
    LOGGER.info('[%s@%s] Add raid pokemon by level' % (user_name, chat_id))

    try:
        level = int(args[0])

        if level < 1 or level > 5:
            bot.sendMessage(chat_id, text=usage_message)
            return

        search = pref.get('raidids', [])
        for x in raid_levels[level]:
            if int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('raidids', search)
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
    LOGGER.info('[%s@%s] Add raid' % (user_name, chat_id))

    try:
        search = pref.get('raidids', [])
        for x in args:
            if int(x) >= min_pokemon_id and int(x) <= max_pokemon_id and int(x) not in search:
                search.append(int(x))
        search.sort()
        pref.set('raidids', search)
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

    LOGGER.info('[%s@%s] Remove raid' % (user_name, chat_id))

    try:
        search = pref.get('raidids', [])
        for x in args:
            if int(x) in search:
                search.remove(int(x))
        pref.set('raidids', search)
        cmd_list(bot, update)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/removeraid pokedexID'))


def cmd_list(bot, update):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    if is_not_whitelisted(bot, update, 'list'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    LOGGER.info('[%s@%s] List' % (user_name, chat_id))

    try:
        lan = pref.get('language')
        dists = pref.get('pkmradius', {})
        minivs = pref.get('pkmiv', {})
        mincps = pref.get('pkmcp', {})
        minlevels = pref.get('pkmlevel', {})
        matchmodes = pref.get('pkmmatchmode', {})
        user_location = pref.get('location')
        if user_location[0] is None:
            tmp = _('*List of watched Pokémon:*') + '\n'
        else:
            tmp = _('*List of watched Pokémon within a radius of %.2fkm:*') % (user_location[2]) + '\n'
        for x in pref.get('pkmids', []):
            pkm_id = str(x)
            tmp += '%s %s' % (pkm_id, pokemon_name[lan][pkm_id])
            if pkm_id in dists:
                tmp += ' %.2fkm' % (dists[pkm_id])
            if pkm_id in minivs:
                tmp += ' %d%%' % (minivs[pkm_id])
            if pkm_id in mincps:
                tmp += ' ' + _('%dCP') % (mincps[pkm_id])
            if pkm_id in minlevels:
                tmp += ' L%d' % (minlevels[pkm_id])
            if pkm_id in matchmodes:
                if matchmodes[pkm_id] == 0:
                    tmp += ' ' + _('AND')
                if matchmodes[pkm_id] == 1:
                    tmp += ' ' + _('OR1')
                if matchmodes[pkm_id] == 2:
                    tmp += ' ' + _('OR2')
            tmp += '\n'

        tmp += '\n'
        if user_location[0] is None:
            tmp += _('*List of watched Raid Pokémon:*') + '\n'
        else:
            tmp += _('*List of watched Raid Pokémon within a radius of %.2fkm:*') % (user_location[2]) + '\n'
        raid_dists = pref.get('raidradius', {})
        for x in pref.get('raidids', []):
            pkm_id = str(x)
            tmp += '%s %s' % (pkm_id, pokemon_name[lan][pkm_id])
            if pkm_id in raid_dists:
                tmp += ' %.2fkm' % (raid_dists[pkm_id])
            tmp += '\n'

        bot.sendMessage(chat_id, text=tmp, parse_mode='Markdown')

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))


def set_user_location(chat_id, latitude, longitude, radius):
    pref = prefs.get(chat_id)
    if radius is not None and radius < 0.1:
        radius = 0.1
    pref.set('location', [latitude, longitude, radius])


def send_current_location(bot, chat_id, set_new=False):
    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    user_location = pref.get('location')
    if user_location[0] is None:
        bot.sendMessage(chat_id, text=_('You have not supplied a scan location'))
    else:
        if set_new:
            bot.sendMessage(chat_id, text=_('Setting new scan location with radius %.2fkm:') % (user_location[2]))
        else:
            bot.sendMessage(chat_id, text=_('This is your current scan location with radius %.2fkm:') % (user_location[2]))
        bot.sendLocation(chat_id, user_location[0], user_location[1], disable_notification=True)


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
        set_user_location(chat_id, user_location.latitude, user_location.longitude,
                          pref.get('location')[2])
        send_current_location(bot, chat_id, True)

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('The location was not found (or OpenStreetMap is down)'))
        return


def cmd_radius(bot, update, args):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'radius'):
        return

    if len(args) < 1:
        send_current_location(bot, chat_id)
        return

    pref = prefs.get(chat_id)
    user_location = pref.get('location')
    set_user_location(chat_id, user_location[0], user_location[1], float(args[0]))
    send_current_location(bot, chat_id, True)


def is_not_whitelisted(bot, update, command):
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    user_name = update.message.from_user.username
    if chat_id < 0 or not whitelist.is_whitelisted(user_name):
        LOGGER.info('[%s@%s] User blocked (%s)' % (user_name, chat_id, command))
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
        bot.sendMessage(chat_id, text=_('Whitelist is disabled'))
        return
    if not whitelist.is_admin(user_name):
        LOGGER.info('[%s@%s] User blocked (addToWhitelist)' % (user_name, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wladd <username>') + _(' or ') + _('/wladd <username_1> <username_2>'))
        return

    try:
        for x in args:
            whitelist.add_user(x)
        bot.sendMessage(chat_id, 'Added to whitelist.')
    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wladd <username>') + _(' or ') + _('/wladd <username_1> <username_2>'))


def cmd_rem_from_whitelist(bot, update, args):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    if not whitelist.is_whitelist_enabled():
        bot.sendMessage(chat_id, text=_('Whitelist is disabled'))
        return
    if not whitelist.is_admin(user_name):
        LOGGER.info('[%s@%s] User blocked (remFromWhitelist)' % (user_name, chat_id))
        return

    if len(args) < 1:
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wlrem <username>') + _(' or ') + _('/wlrem <username_1> <username_2>'))
        return

    try:
        for x in args:
            whitelist.rem_user(x)
        bot.sendMessage(chat_id, text=_('Removed from whitelist'))

    except Exception as e:
        LOGGER.error('[%s@%s] %s' % (user_name, chat_id, repr(e)))
        bot.sendMessage(chat_id, text=_('Usage:') + '\n' + _('/wlrem <username>') + _(' or ') + _('/wlrem <username_1> <username_2>'))


def cmd_unknown(bot, update):
    chat_id = update.message.chat_id

    if is_not_whitelisted(bot, update, 'unknown'):
        return

    pref = prefs.get(chat_id)
    set_lang(pref.get('language'))

    bot.sendMessage(chat_id, text=_('Unfortunately, I do not understand this command'))


## Functions
def handle_error(bot, update, error):
    LOGGER.warning('Update "%s" caused error "%s"' % (update, error))


def alarm(bot, job):
    chat_id = job.context[0]
    LOGGER.info('[%s] Checking alarm' % (chat_id))
    check_and_send(bot, chat_id)


def cleanup(chat_id):
    if chat_id not in jobs:
        return

    job = jobs[chat_id]
    job.schedule_removal()
    del jobs[chat_id]
    del sent[chat_id]
    del locks[chat_id]


def add_job(update, job_queue):
    chat_id = update.message.chat_id
    user_name = update.message.from_user.username
    LOGGER.info('[%s@%s] Adding job' % (user_name, chat_id))
    add_job_for_chat_id(chat_id, job_queue)


def add_job_for_chat_id(chat_id, job_queue):
    try:
        if chat_id not in jobs:
            job = Job(alarm, 30, repeat=True, context=(chat_id, 'Other'))
            # Add to jobs
            jobs[chat_id] = job
            if not webhook_enabled:
                LOGGER.info('Putting job')
                job_queue._put(job)

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
    pokemons = pref.get('pkmids', [])
    if not pokemons:
        return []
    location = pref.get('location')
    miniv = pref.get('iv', 0)
    mincp = pref.get('cp', 0)
    minlevel = pref.get('level', 0)
    matchmode = pref.get('matchmode', 0)
    dists = pref.get('pkmradius', {})
    minivs = pref.get('pkmiv', {})
    mincps = pref.get('pkmcp', {})
    minlevels = pref.get('pkmlevel', {})
    matchmodes = pref.get('pkmmatchmode', {})
    pokemon_list = []
    for pkm in pokemons:
        entry = {}
        pkm_id = str(pkm)
        entry['id'] = pkm_id
        entry['iv'] = minivs[pkm_id] if pkm_id in minivs else miniv
        entry['cp'] = mincps[pkm_id] if pkm_id in mincps else mincp
        entry['level'] = minlevels[pkm_id] if pkm_id in minlevels else minlevel
        entry['matchmode'] = matchmodes[pkm_id] if pkm_id in matchmodes else matchmode
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
    raids = pref.get('raidids', [])
    if not raids:
        return []
    location = pref.get('location')
    dists = pref.get('raidradius', {})
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
    LOGGER.info('[%s] Checking pokemons and raids' % (chat_id))
    try:
        pref = prefs.get(chat_id)
        set_lang(pref.get('language'))
        pokemons = pref.get('pkmids', [])
        raids = pref.get('raidids', [])

        if pokemons:
            send_without = pref.get('sendwithout', True)

            allpokes = data_source.get_pokemon_by_list(
                build_detailed_pokemon_list(chat_id), send_without)

            if len(allpokes) > 50:
                bot.sendMessage(chat_id, text=_('Your filter rules are matching too many Pokémon') + '\n' + _('Please check your settings!'))
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
    LOGGER.info('Checking pokemon %s for all users' % (poke_id))
    for chat_id in jobs:
        if int(poke_id) in prefs.get(chat_id).get('pkmids', []):
            send_one_poke(chat_id, pokemon)


def find_users_by_raid_id(raid):
    raid_id = raid.get_pokemon_id()
    LOGGER.info('Checking raid pokemon %s for all users' % (raid_id))
    for chat_id in jobs:
        if int(raid_id) in prefs.get(chat_id).get('raidids', []):
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

        send_poke_without_iv = pref.get('sendwithout', True)
        lan = pref.get('language')

        delta = disappear_time - datetime.utcnow()
        deltaStr = '%02dm %02ds' % (int(delta.seconds / 60), int(delta.seconds % 60))
        disappear_time_str = disappear_time.replace(tzinfo=timezone.utc).astimezone(
            tz=None).strftime('%H:%M:%S')

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

        dists = pref.get('pkmradius', {})
        if pok_id in dists:
            location_data[2] = dists[pok_id]

        matchmode = pref.preferences.get('matchmode', 0)

        matchmodes = pref.get('pkmmatchmode', {})
        if pok_id in matchmodes:
            matchmode = matchmodes[pok_id]

        if matchmode < 2:
            if location_data[0] is not None and not pokemon.filter_by_location(location_data):
                LOGGER.info('[%s] Not sending pokemon notification. Too far away. %s' % (chat_id,
                                                                                         pok_id))
                lock.release()
                return

        if webhook_enabled:

            miniv = pref.preferences.get('iv', 0)
            mincp = pref.preferences.get('cp', 0)
            minlevel = pref.preferences.get('level', 0)

            minivs = pref.get('pkmiv', {})
            if pok_id in minivs:
                miniv = minivs[pok_id]

            mincps = pref.get('pkmcp', {})
            if pok_id in mincps:
                mincp = mincps[pok_id]

            minlevels = pref.get('pkmlevel', {})
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
            title += ' %s%%' % iv

        if cp is not None:
            title += ' ' + (_('%dCP') % cp)

        if level is not None:
            title += ' L%d' % level

        address = '💨 %s ⏱ %s' % (disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walkdist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += ' 📍%dm' % int(1000 * walkin_data['walk_dist'])
                else:
                    title += ' 📍%.2fkm' % walkin_data['walk_dist']
                address += ' 🚶%s' % walkin_data['walk_time']
            else:
                dist = round(pokemon.get_distance(location_data), 2)
                if dist < 1:
                    title += ' 📍%dm' % int(1000 * dist)
                else:
                    title += ' 📍%.2fkm' % dist

        if move1 is not None and move2 is not None:
            moveNames = move_name['en']
            if lan in move_name:
                moveNames = move_name[lan]
            # Use language if other move languages are available.
            move1Name = moveNames[str(move1)] if str(move1) in moveNames else '?'
            move2Name = moveNames[str(move2)] if str(move2) in moveNames else '?'
            address += '\n⚔ %s / %s' % (move1Name, move2Name)

        mySent[encounter_id] = disappear_time

        if pref.get('maponly'):
            telegram_bot.sendVenue(chat_id, latitude, longitude, title, address)
        else:
            if pref.get('stickers'):
                telegram_bot.sendSticker(
                    chat_id, sticker_list.get(pok_id), disable_notification=True)
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
        LOGGER.info('[%s] Cleaning sentlist' % (chat_id))
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
            tz=None).strftime('%H:%M:%S')

        if raid_id in mySent:
            LOGGER.info('[%s] Not sending raid notification. Already sent. %s' % (chat_id, pok_id))
            lock.release()
            return

        if delta.seconds <= 0:
            LOGGER.info('[%s] Not sending raid notification. Already ended. %s' % (chat_id, pok_id))
            lock.release()
            return

        location_data = pref.preferences.get('location')

        dists = pref.get('raidradius', {})
        if pok_id in dists:
            location_data[2] = dists[pok_id]

        if location_data[0] is not None and not raid.filter_by_location(location_data):
            LOGGER.info('[%s] Not sending raid notification. Too far away. %s' % (chat_id, pok_id))
            lock.release()
            return

        LOGGER.info('[%s] Sending one notification. %s' % (chat_id, pok_id))

        title = '👹 ' + pokemon_name[lan][pok_id]

        if cp is not None:
            title += ' ' + (_('%dCP') % cp)

        address = '📍 %s\n💨 %s ⏱ %s' % (name, disappear_time_str, deltaStr)

        if location_data[0] is not None:
            if pref.get('walkdist'):
                walkin_data = get_walking_data(location_data, latitude, longitude)
                if walkin_data['walk_dist'] < 1:
                    title += ' 📍%dm' % int(1000 * walkin_data['walk_dist'])
                else:
                    title += ' 📍%.2fkm' % walkin_data['walk_dist']
                address += ' 🚶%s' % walkin_data['walk_time']
            else:
                dist = round(raid.get_distance(location_data), 2)
                if dist < 1:
                    title += ' 📍%dm' % int(1000 * dist)
                else:
                    title += ' 📍%.2fkm' % dist

        if move1 is not None and move2 is not None:
            moveNames = move_name['en']
            if lan in move_name:
                moveNames = move_name[lan]
            # Use language if other move languages are available.
            move1Name = moveNames[str(move1)] if str(move1) in moveNames else '?'
            move2Name = moveNames[str(move2)] if str(move2) in moveNames else '?'
            address += '\n⚔ %s / %s' % (move1Name, move2Name)

        mySent[raid_id] = end

        if pref.get('maponly'):
            telegram_bot.sendVenue(chat_id, latitude, longitude, title, address)
        else:
            if pref.get('stickers'):
                telegram_bot.sendSticker(
                    chat_id, sticker_list.get(pok_id), disable_notification=True)
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
        LOGGER.info('[%s] Cleaning sentlist' % (chat_id))
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
    config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config-bot.json')
    LOGGER.info('Reading config: <%s>' % config_path)
    global config

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
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
    LOGGER.info('DEFAULT_LANG: <%s>' % (config.get('DEFAULT_LANG', 'en')))
    LOGGER.info('SEND_MAP_ONLY: <%s>' % (config.get('SEND_MAP_ONLY', False)))
    LOGGER.info('STICKERS: <%s>' % (config.get('STICKERS', True)))
    LOGGER.info('SEND_POKEMON_WITHOUT_IV: <%s>' % (config.get('SEND_POKEMON_WITHOUT_IV', True)))


def read_pokemon_names(loc):
    LOGGER.info('Reading pokemon names. <%s>' % loc)
    config_path = 'locales/pokemon.' + loc + '.json'

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            pokemon_name[loc] = json.loads(f.read())

    except Exception as e:
        LOGGER.error('%s' % (repr(e)))


def read_move_names(loc):
    LOGGER.info('Reading move names. <%s>' % loc)
    config_path = 'locales/moves.' + loc + '.json'

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            move_name[loc] = json.loads(f.read())

    except Exception as e:
        LOGGER.error('%s' % (repr(e)))


# Returns a set with walking dist and walking duration via Google Distance Matrix API
def get_walking_data(user_location, lat, lng):
    data = {'walk_dist': 'unknown', 'walk_time': 'unknown'}
    if gmaps_client is None:
        LOGGER.error('Google Maps Client not available. Unable to get walking data')
        return data
    if user_location[0] is None:
        LOGGER.error('No location has been set. Unable to get walking data')
        return data
    origin = '{},{}'.format(user_location[0], user_location[1])
    dest = '{},{}'.format(lat, lng)
    try:
        result = gmaps_client.distance_matrix(origin, dest, mode='walking', units='metric')
        result = result.get('rows')[0].get('elements')[0]
        data['walk_dist'] = float(result.get('distance').get('text').replace(' km', ''))
        data['walk_time'] = result.get('duration').get('text').replace(' hours', 'h').replace(
            ' hour', 'h').replace(' mins', 'm').replace(' min', 'm')

    except Exception as e:
        LOGGER.error('Encountered error while getting walking data (%s)' % (repr(e)))
    return data

# Raid enter
def enter_raid_level(bot, update, user_data):
    default_cmd(bot, update, 'enter_raid_level')
    reply_keyboard = [
        [
            InlineKeyboardButton('⭐', callback_data='raidlevel_1'),
            InlineKeyboardButton('⭐⭐', callback_data='raidlevel_2'),
            InlineKeyboardButton('⭐⭐⭐', callback_data='raidlevel_3')
        ],
        [
            InlineKeyboardButton('⭐⭐⭐⭐', callback_data='raidlevel_4'),
            InlineKeyboardButton('⭐⭐⭐⭐⭐', callback_data='raidlevel_5')
        ]
    ]
    markup = InlineKeyboardMarkup(reply_keyboard)
    update.message.reply_text(_('Please choose the raid level:'), reply_markup=markup)
    return CHOOSE_LEVEL


def cb_raid_level(bot, update, user_data):
    query = update.callback_query
    pref = prefs.get(query.message.chat_id)
    set_lang(pref.get('language'))

    user_data['level'] = int(update.callback_query.data[10:])
    query.answer()
    query.edit_message_text(_('*Raid level: %s*') % user_data['level'], parse_mode='Markdown')
    reply_keyboard = []
    for pkm_id in raid_levels[user_data['level']]:
        reply_keyboard.append(
            [InlineKeyboardButton(pokemon_name[pref.get('language')][pkm_id], callback_data='raidpkm_' + pkm_id)])
    markup = InlineKeyboardMarkup(reply_keyboard)
    query.message.reply_text(_('Please choose the raid boss:'), reply_markup=markup)
    return CHOOSE_PKM 


def cb_raid_pkm(bot, update, user_data):
    query = update.callback_query
    pref = prefs.get(query.message.chat_id)
    set_lang(pref.get('language'))

    user_data['pkm'] = update.callback_query.data[8:]
    query.answer()
    query.edit_message_text(_('*Raid boss: %s*') % pokemon_name[pref.get('language')][user_data['pkm']], parse_mode='Markdown')
    query.message.reply_text(_('Please enter the gym name:'))
    return CHOOSE_GYM


def enter_raid_gym_search(bot, update, user_data):
    pref = prefs.get(update.message.chat_id)
    set_lang(pref.get('language'))
    gyms = data_source.get_gyms_by_name(gym_name=update.message.text)
    if len(gyms) >= 1:
        reply_keyboard = []
        for gym in gyms:
            reply_keyboard.append(
                [InlineKeyboardButton(gym.get_name(), callback_data='raidgym_' + gym.get_gym_id())])
        markup = InlineKeyboardMarkup(reply_keyboard)
        update.message.reply_text(_('Please select the matching gym:'), reply_markup=markup)
        return CHOOSE_GYM_SEARCH

    update.message.reply_text(_('No gym with this name could be found. Please try again.'))
    return CHOOSE_GYM


def cb_raid_gym(bot, update, user_data):
    query = update.callback_query
    pref = prefs.get(query.message.chat_id)
    set_lang(pref.get('language'))

    user_data['gym'] = update.callback_query.data[8:]
    query.answer()
    gyms = data_source.get_gyms_by_name(gym_name=user_data['gym'], use_id=True)
    query.edit_message_text(_('*Raid gym: %s*') % gyms[0].get_name(), parse_mode='Markdown')
    query.message.reply_text(_('Please enter the start time of the raid (Format: hh:mm):'))
    return CHOOSE_TIME


def enter_raid_time(bot, update, user_data):
    pref = prefs.get(update.message.chat_id)
    set_lang(pref.get('language'))
    try:
        user_data['time'] = datetime.strptime(datetime.now().strftime("%d %m %Y ") + update.message.text, "%d %m %Y %H:%M")
    except Exception as e:
        LOGGER.error(repr(e))
        update.message.reply_text(_('Please enter the start time of the raid (Format: hh:mm):'))
        return CHOOSE_TIME
    update.message.reply_text(_('*Raid start time: %s*') % user_data['time'].strftime("%H:%M am %d.%m.%Y"), parse_mode='Markdown')
    bot.sendMessage(update.message.chat_id, text=_('Thanks!'))

    data_source.add_new_raid(user_data['gym'], user_data['level'], user_data['time'].astimezone(timezone.utc), user_data['pkm'])

    user_data.clear()
    return ConversationHandler.END


def enter_raid_cancel(bot, update, user_data):
    user_data.clear()
    update.message.reply_text(_('Alright. See you later.'))
    return ConversationHandler.END


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
        if scanner_name == 'rocketmap-iv':
            iv_available = True
            data_source = DataSources.DSRocketMapIVMysql(config.get('DB_CONNECT', None))
    elif db_type == 'webhook':
        webhook_enabled = True
        if scanner_name == 'rocketmap-iv':
            iv_available = True
            data_source = DataSources.DSRocketMapIVWebhook(
                config.get('DB_CONNECT', None), find_users_by_poke_id, find_users_by_raid_id)
    if not data_source:
        raise Exception('The combination SCANNER_NAME, DB_TYPE is not available: %s,%s' %
                        (scanner_name, db_type))

    global whitelist
    whitelist = Whitelist.Whitelist(config)

    #ask it to the bot father in telegram
    token = config.get('TELEGRAM_TOKEN', None)
    updater = Updater(token)

    global telegram_bot
    telegram_bot = Bot(token)
    LOGGER.info('BotName: <%s>' % (telegram_bot.name))

    # Get the Google Maps API
    global gmaps_client
    google_key = config.get('GMAPS_KEY', None)
    gmaps_client = googlemaps.Client(
        key=google_key, timeout=3, retry_timeout=4) if google_key is not None else None

    set_lang(config.get('DEFAULT_LANG', 'en'))

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler('start', cmd_start, pass_job_queue=True))
    dp.add_handler(CommandHandler('stop', cmd_stop))
    dp.add_handler(CommandHandler('help', cmd_help))
    dp.add_handler(CommandHandler('clear', cmd_clear))
    dp.add_handler(CommandHandler('add', cmd_add, pass_args=True, pass_job_queue=True))
    dp.add_handler(
        CommandHandler('addbyrarity', cmd_add_by_rarity, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler('remove', cmd_remove, pass_args=True))
    dp.add_handler(CommandHandler('addraid', cmd_add_raid, pass_args=True, pass_job_queue=True))
    dp.add_handler(
        CommandHandler(
            'addraidbylevel', cmd_add_raid_by_level, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler('removeraid', cmd_remove_raid, pass_args=True))
    dp.add_handler(CommandHandler('list', cmd_list))
    dp.add_handler(CommandHandler(['language', 'lang'], cmd_lang, pass_args=True))
    dp.add_handler(CommandHandler('radius', cmd_radius, pass_args=True))
    dp.add_handler(CommandHandler('location', cmd_location_str, pass_args=True))
    dp.add_handler(CommandHandler('removelocation', cmd_remove_location))
    dp.add_handler(CommandHandler('wladd', cmd_add_to_whitelist, pass_args=True))
    dp.add_handler(CommandHandler('wlrem', cmd_rem_from_whitelist, pass_args=True))
    dp.add_handler(CommandHandler('stickers', cmd_stickers, pass_args=True))
    dp.add_handler(CommandHandler('maponly', cmd_map_only, pass_args=True))
    dp.add_handler(CommandHandler('walkdist', cmd_walk_dist, pass_args=True))
    dp.add_handler(CommandHandler('pkmradius', cmd_pkm_radius, pass_args=True))
    dp.add_handler(CommandHandler('resetpkmradius', cmd_pkm_radius_reset, pass_args=True))
    dp.add_handler(CommandHandler('raidradius', cmd_raid_radius, pass_args=True))
    dp.add_handler(CommandHandler('resetraidradius', cmd_raid_radius_reset, pass_args=True))
    dp.add_handler(CommandHandler('iv', cmd_iv, pass_args=True))
    dp.add_handler(CommandHandler(['cp', 'wp'], cmd_cp, pass_args=True))
    dp.add_handler(CommandHandler('level', cmd_level, pass_args=True))
    dp.add_handler(CommandHandler('matchmode', cmd_matchmode, pass_args=True))
    dp.add_handler(CommandHandler('pkmiv', cmd_pkm_iv, pass_args=True))
    dp.add_handler(CommandHandler(['pkmcp', 'pkmwp'], cmd_pkm_cp, pass_args=True))
    dp.add_handler(CommandHandler('pkmlevel', cmd_pkm_level, pass_args=True))
    dp.add_handler(CommandHandler('pkmmatchmode', cmd_pkm_matchmode, pass_args=True))
    dp.add_handler(CommandHandler('resetpkmiv', cmd_pkm_iv_reset, pass_args=True))
    dp.add_handler(CommandHandler(['resetpkmcp', 'resetpkmwp'], cmd_pkm_cp_reset, pass_args=True))
    dp.add_handler(CommandHandler('resetpkmlevel', cmd_pkm_level_reset, pass_args=True))
    dp.add_handler(CommandHandler('resetpkmmatchmode', cmd_pkm_matchmode_reset, pass_args=True))
    dp.add_handler(CommandHandler('sendwithout', cmd_send_without, pass_args=True))
    dp.add_handler(CommandHandler(['wo', 'where'], cmd_find_gym, pass_args=True))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(['newraid', 'neuerraid'], enter_raid_level, pass_user_data=True)
        ],
        states={
            CHOOSE_LEVEL: [
                CallbackQueryHandler(cb_raid_level, pattern='^raidlevel_(.*)$', pass_user_data=True)
            ],
            CHOOSE_PKM: [
                CallbackQueryHandler(cb_raid_pkm, pattern='^raidpkm_(.*)$', pass_user_data=True)
            ],
            CHOOSE_GYM: [
                MessageHandler(Filters.text, enter_raid_gym_search, pass_user_data=True)
            ],
            CHOOSE_GYM_SEARCH: [
                CallbackQueryHandler(cb_raid_gym, pattern='^raidgym_(.*)$', pass_user_data=True)
            ],
            CHOOSE_TIME: [
                MessageHandler(Filters.text, enter_raid_time, pass_user_data=True)
            ]
        },
        fallbacks=[RegexHandler('^(Cancel|Abbruch)$', enter_raid_cancel, pass_user_data=True)])
    dp.add_handler(conv_handler)

    dp.add_handler(MessageHandler(Filters.location, cmd_location))
    dp.add_handler(MessageHandler(Filters.command, cmd_unknown))

    dp.add_handler(CallbackQueryHandler(cb_find_gym, pattern='^gymsearch_(.*)$'))

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
            if pref.get('pkmids', []) or pref.get('raidids', []):
                add_job_for_chat_id(chat_id, j)

    # Block until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

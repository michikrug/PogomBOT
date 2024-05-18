import logging
import re
from datetime import datetime, timedelta, timezone

import pymysql

from .Conversion import floatOrNone, intOrNone, strOrNone, strptimeOrNone
from .DSGym import DSGym
from .DSPokemon import DSPokemon
from .DSRaid import DSRaid

LOGGER = logging.getLogger(__name__)


class DSRocketMapIVMysql():

    def __init__(self, connectString):
        # open the database
        sql_pattern = r'mysql://(.*?):(.*?)@(.*?):(\d*)/(\S+)'
        (user, passw, host, port, database) = re.compile(sql_pattern).findall(connectString)[0]
        self.__user = user
        self.__passw = passw
        self.__host = host
        self.__port = int(port)
        self.__db = database
        LOGGER.info('Connecting to remote database')
        self.__connect()

    def get_pokemon_by_time(self, timestamp):
        sql_query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, "
            "weight, height, gender, form, cp, cp_multiplier "
            "FROM pokemon WHERE last_modified >= '%s' "
            "AND disappear_time > UTC_TIMESTAMP()" % (timestamp.strftime('%Y-%m-%d %H:%M:%S')))

        poke_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    poke_list.append(
                        DSPokemon(
                            strOrNone(row[0]), strOrNone(row[1]), intOrNone(row[2]),
                            floatOrNone(row[3]), floatOrNone(row[4]), strptimeOrNone(row[5]),
                            intOrNone(row[6]), intOrNone(row[7]), intOrNone(row[8]),
                            intOrNone(row[9]), intOrNone(row[10]), floatOrNone(row[11]),
                            floatOrNone(row[12]), intOrNone(row[13]), intOrNone(row[14]),
                            intOrNone(row[15]), floatOrNone(row[16])))

        except pymysql.err.OperationalError as err:
            if err.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error('__execute_pokemon_query: %s' % (repr(err)))

        except pymysql.err.InterfaceError:
            self.__reconnect()

        except Exception as err:
            LOGGER.error('__execute_pokemon_query: %s' % (repr(err)))

        return poke_list

    def get_raids_by_time(self, timestamp):
        sql_query = ("SELECT raid.gym_id, name, latitude, longitude, "
                     "start, end, pokemon_id, cp, move_1, move_2 "
                     "FROM raid JOIN gym ON gym.gym_id=raid.gym_id "
                     "JOIN gymdetails ON gym.gym_id=gymdetails.gym_id "
                     "WHERE raid.last_scanned >= '%s' "
                     "AND end > UTC_TIMESTAMP()" % (timestamp.strftime('%Y-%m-%d %H:%M:%S')))

        raid_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    raid_list.append(
                        DSRaid(
                            strOrNone(row[0]), strOrNone(row[1]), floatOrNone(row[2]),
                            floatOrNone(row[3]), strptimeOrNone(row[4]), strptimeOrNone(row[5]),
                            intOrNone(row[6]), intOrNone(row[7]), intOrNone(row[8]),
                            intOrNone(row[9])))

        except pymysql.err.OperationalError as err:
            if err.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error('get_raids_by_list: %s' % (repr(err)))

        except pymysql.err.InterfaceError:
            self.__reconnect()

        except Exception as err:
            LOGGER.error('get_raids_by_list: %s' % (repr(err)))

        return raid_list

    def get_gyms_by_name(self, gym_name, use_id=False):
        sql_query = ("SELECT gym.gym_id, name, latitude, longitude "
                     "FROM gym JOIN gymdetails "
                     "ON gym.gym_id=gymdetails.gym_id WHERE ")
        if use_id:
            sql_query += "gym.gym_id=%s"
        else:
            sql_query += "name LIKE %s"
            gym_name = '%' + gym_name + '%'

        gym_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query, (gym_name,))
                rows = cur.fetchall()
                for row in rows:
                    gym_list.append(
                        DSGym(strOrNone(row[0]), strOrNone(row[1]), floatOrNone(row[2]), floatOrNone(row[3])))

        except pymysql.err.OperationalError as err:
            if err.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error('get_gyms_by_name: %s' % (repr(err)))

        except pymysql.err.InterfaceError:
            self.__reconnect()

        except Exception as err:
            LOGGER.error('get_gyms_by_name: %s' % (repr(err)))

        return gym_list

    def add_new_raid(self, gym_id, level, start, pokemon_id):
        end = start + timedelta(minutes=45)
        sql_query = (
            "REPLACE INTO `raid` (`gym_id`, `level`, `spawn`, `start`, `end`, `pokemon_id`, `last_scanned`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)")
        sql_query2 = ("UPDATE `gym` SET `last_scanned`=%s WHERE `gym_id`=%s")

        try:
            with self.con.cursor() as cur:
                cur.execute(
                    sql_query,
                    (gym_id,
                     level,
                     datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                     start.strftime('%Y-%m-%d %H:%M:%S'),
                     end.strftime('%Y-%m-%d %H:%M:%S'),
                     pokemon_id,
                     datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')))
                cur.execute(sql_query2, (datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), gym_id))
            self.con.commit()

        except pymysql.err.OperationalError as err:
            if err.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error('add_new_raid: %s' % (repr(err)))

        except pymysql.err.InterfaceError:
            self.__reconnect()

        except Exception as err:
            LOGGER.error('add_new_raid: %s' % (repr(err)))

    def __connect(self):
        self.con = pymysql.connect(
            user=self.__user,
            password=self.__passw,
            host=self.__host,
            port=self.__port,
            database=self.__db,
            autocommit=True)

    def __reconnect(self):
        LOGGER.info('Reconnecting to remote database')
        self.__connect()

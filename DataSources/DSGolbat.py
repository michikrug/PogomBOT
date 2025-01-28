import logging
import re
from datetime import datetime, timedelta, timezone

import pymysql

from .Conversion import floatOrNone, intOrNone, strOrNone, utcfromtimestampOrNone
from .DSGym import DSGym
from .DSPokemon import DSPokemon
from .DSRaid import DSRaid

LOGGER = logging.getLogger(__name__)


class DSGolbat():

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
            "SELECT id, spawn_id, pokemon_id, lat, lon, expire_timestamp, "
            "atk_iv, def_iv, sta_iv, move_1, move_2, "
            "weight, height, gender, form, cp, level, iv "
            "FROM pokemon WHERE iv IS NOT NULL AND changed >= %s "
            "AND expire_timestamp > UTC_TIMESTAMP()" % timestamp)

        poke_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    poke_list.append(
                        DSPokemon(
                            strOrNone(row[0]), strOrNone(row[1]), intOrNone(row[2]),
                            floatOrNone(row[3]), floatOrNone(row[4]), utcfromtimestampOrNone(row[5]),
                            intOrNone(row[6]), intOrNone(row[7]), intOrNone(row[8]),
                            intOrNone(row[9]), intOrNone(row[10]), floatOrNone(row[11]),
                            floatOrNone(row[12]), intOrNone(row[13]), intOrNone(row[14]),
                            intOrNone(row[15]), intOrNone(row[16]), floatOrNone(row[17])))

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
        sql_query = ("SELECT id, name, lat, lon, "
                     "raid_battle_timestamp, raid_end_timestamp, "
                     "raid_pokemon_id, raid_pokemon_cp, raid_pokemon_move_1, raid_pokemon_move_2 "
                     "FROM gym "
                     "WHERE last_modified_timestamp >= %s "
                     "AND raid_end_timestamp > UTC_TIMESTAMP()" % timestamp)

        raid_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    raid_list.append(
                        DSRaid(
                            strOrNone(row[0]),
                            strOrNone(row[1]),
                            floatOrNone(row[2]),
                            floatOrNone(row[3]),
                            utcfromtimestampOrNone(row[4]),
                            utcfromtimestampOrNone(row[5]),
                            intOrNone(row[6]),
                            intOrNone(row[7]),
                            intOrNone(row[8]),
                            intOrNone(row[9])
                        )
                    )

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
        sql_query = "SELECT id, name, lat, lon FROM gym WHERE name LIKE %(gym_name)s"
        args = {'gym_name': '%' + gym_name + '%'}
        if use_id:
            sql_query = "SELECT id, name, lat, lon FROM gym WHERE id=%(gym_id)s"
            args = {'gym_id': gym_name}

        gym_list = []
        try:
            with self.con.cursor() as cur:
                cur.execute(sql_query, args)
                rows = cur.fetchall()
                for row in rows:
                    gym_list.append(
                        DSGym(
                            strOrNone(row[0]),
                            strOrNone(row[1]),
                            floatOrNone(row[2]),
                            floatOrNone(row[3])
                        )
                    )

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

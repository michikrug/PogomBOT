import logging
import re

import pymysql

from .Conversion import floatOrNone, intOrNone, strOrNone, strptimeOrNone
from .DSGym import DSGym
from .DSPokemon import DSPokemon
from .DSRaid import DSRaid

LOGGER = logging.getLogger(__name__)


def __get_pokemon_cpm(level):
    cp_multiplier = [
        0.094, 0.166398, 0.215732, 0.25572, 0.29025, 0.321088, 0.349213, 0.375236, 0.399567, 0.4225,
        0.443108, 0.462798, 0.481685, 0.499858, 0.517394, 0.534354, 0.550793, 0.566755, 0.582279,
        0.5974, 0.612157, 0.626567, 0.640653, 0.654436, 0.667934, 0.681165, 0.694144, 0.706884,
        0.719399, 0.7317
    ]
    return cp_multiplier[level - 1]


class DSRocketMapIVMysql():

    def __init__(self, connectString):
        # open the database
        sql_pattern = 'mysql://(.*?):(.*?)@(.*?):(\d*)/(\S+)'
        (user, passw, host, port, db) = re.compile(sql_pattern).findall(connectString)[0]
        self.__user = user
        self.__passw = passw
        self.__host = host
        self.__port = int(port)
        self.__db = db
        LOGGER.info('Connecting to remote database')
        self.__connect()

    @staticmethod
    def __build_pokemon_query(pkm):
        values_query = None
        query_parts = []
        sub_query_parts = []
        values_query_parts = []

        query_parts.append('pokemon_id = %s' % pkm['id'])

        if pkm['iv'] > 0:
            values_query_parts.append(
                '(individual_attack + individual_defense + individual_stamina) >= %s' %
                (float(pkm['iv']) / 100 * 45))
        if pkm['cp'] > 0:
            values_query_parts.append('cp >= %s' % pkm['cp'])
        if pkm['level'] > 0:
            values_query_parts.append('cp_multiplier >= %s' % __get_pokemon_cpm(pkm['level']))
        if pkm['matchmode'] == 0:
            values_query = ' AND '.join(values_query_parts)
        elif pkm['matchmode'] == 1:
            values_query = ' OR '.join(values_query_parts)
        if values_query:
            sub_query_parts.append('(' + values_query + ')')

        if 'lat_max' in pkm:
            location_query = 'latitude BETWEEN %s AND %s' % (pkm['lat_min'], pkm['lat_max'])
            location_query += ' AND '
            location_query += 'longitude BETWEEN %s AND %s' % (pkm['lng_min'], pkm['lng_max'])
            sub_query_parts.append('(' + location_query + ')')

        if sub_query_parts:
            if pkm['matchmode'] == 2:
                query_parts.append('(' + ' OR '.join(sub_query_parts) + ')')
            else:
                query_parts.append('(' + ' AND '.join(sub_query_parts) + ')')

        return '(' + ' AND '.join(query_parts) + ')'

    @staticmethod
    def __build_raid_query(raid):
        query_parts = []

        query_parts.append('pokemon_id = %s' % raid['id'])

        if 'lat_max' in raid:
            location_query = 'latitude BETWEEN %s AND %s' % (raid['lat_min'], raid['lat_max'])
            location_query += ' AND '
            location_query += 'longitude BETWEEN %s AND %s' % (raid['lng_min'], raid['lng_max'])
            query_parts.append('(' + location_query + ')')

        return '(' + ' AND '.join(query_parts) + ')'

    def get_pokemon_by_list(self, pokemon_list, send_without=True):
        pokemon_query_parts = list(map(self.__build_pokemon_query, pokemon_list))
        sql_query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, "
            "weight, height, gender, form, cp, cp_multiplier "
            "FROM pokemon WHERE last_modified > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) "
            "AND disappear_time > UTC_TIMESTAMP()")
        sql_query += ' AND (' + ' OR '.join(pokemon_query_parts) + ')'
        if not send_without:
            sql_query += ' AND individual_attack IS NOT NULL'
        sql_query += ' ORDER BY pokemon_id ASC'

        return self.__execute_pokemon_query(sql_query)

    def get_pokemon_by_ids(self, ids, send_without=True):
        sql_query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, "
            "weight, height, gender, form, cp, cp_multiplier "
            "FROM pokemon WHERE last_modified > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) "
            "AND disappear_time > UTC_TIMESTAMP()")
        sql_query += ' AND pokemon_id in (' + ','.join(map(str, ids)) + ')'
        if not send_without:
            sql_query += ' AND individual_attack IS NOT NULL'
        sql_query += ' ORDER BY pokemon_id ASC'

        return self.__execute_pokemon_query(sql_query)

    def __execute_pokemon_query(self, sql_query):
        poke_list = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    ivs = round(
                        float((int(row[6]) + int(row[7]) + int(row[8])) / 45 * 100), 1
                    ) if row[6] is not None and row[7] is not None and row[8] is not None else None

                    poke_list.append(
                        DSPokemon(
                            strOrNone(row[0]), strOrNone(row[1]), intOrNone(row[2]),
                            floatOrNone(row[3]), floatOrNone(row[4]), strptimeOrNone(row[5]), ivs,
                            intOrNone(row[9]), intOrNone(row[10]), floatOrNone(row[11]),
                            floatOrNone(row[12]), intOrNone(row[13]), intOrNone(row[14]),
                            intOrNone(row[15]), floatOrNone(row[16])))

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error(e)

        except Exception as e:
            LOGGER.error('executePokemonQuery: %s' % (repr(e)))

        return poke_list

    def get_raids_by_list(self, raid_list):
        raid_query_parts = list(map(self.__build_raid_query, raid_list))
        sql_query = ("SELECT raid.gym_id, name, latitude, longitude, "
                     "start, end, pokemon_id, cp, move_1, move_2 "
                     "FROM raid JOIN gym ON gym.gym_id=raid.gym_id "
                     "JOIN gymdetails ON gym.gym_id=gymdetails.gym_id "
                     "WHERE raid.last_scanned > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) "
                     "AND end > UTC_TIMESTAMP()")
        sql_query += " AND (" + " OR ".join(raid_query_parts) + ")"
        sql_query += " ORDER BY end ASC"

        raid_list = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sql_query)
                rows = cur.fetchall()
                for row in rows:
                    raid_list.append(
                        DSRaid(
                            strOrNone(row[0]), strOrNone(row[1]), floatOrNone(row[2]),
                            floatOrNone(row[3]), strptimeOrNone(row[4]), strptimeOrNone(row[5]),
                            intOrNone(row[6]), intOrNone(row[7]), intOrNone(row[8]),
                            intOrNone(row[9])))

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error(e)

        except Exception as e:
            LOGGER.error('executeRaidQuery: %s' % (repr(e)))

        return raid_list

    def get_gyms_by_name(self, gym_name, wildcard=True):
        sql_query = ("SELECT gym.gym_id, name, latitude, longitude "
                     "FROM gym JOIN gymdetails "
                     "ON gym.gym_id=gymdetails.gym_id WHERE ")
        if wildcard:
            sql_query += "name LIKE %s"
            gym_name = '%' + gym_name + '%'
        else:
            sql_query += "name=%s COLLATE utf8_bin"

        gym_list = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sql_query, (gym_name,))
                rows = cur.fetchall()
                for row in rows:
                    gym_list.append(
                        DSGym(
                            strOrNone(row[0]), strOrNone(row[1]), floatOrNone(row[2]),
                            floatOrNone(row[3])))

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                LOGGER.error(e)

        except Exception as e:
            LOGGER.error('get_gyms_by_name: %s' % (repr(e)))

        return gym_list

    def __connect(self):
        self.con = pymysql.connect(
            user=self.__user,
            password=self.__passw,
            host=self.__host,
            port=self.__port,
            database=self.__db)

    def __reconnect(self):
        LOGGER.info('Reconnecting to remote database')
        self.__connect()

from .DSPokemon import DSPokemon
from .DSRaid import DSRaid
from .DSGym import DSGym

import os
from datetime import datetime
import logging

import pymysql
import re

logger = logging.getLogger(__name__)

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
        logger.info('Connecting to remote database')
        self.__connect()

    def get_pokemon_cpm(self, level):
        cp_multiplier = [0.094, 0.166398, 0.215732, 0.25572, 0.29025,
            0.321088, 0.349213, 0.375236, 0.399567, 0.4225,
            0.443108, 0.462798, 0.481685, 0.499858, 0.517394,
            0.534354, 0.550793, 0.566755, 0.582279, 0.5974,
            0.612157, 0.626567, 0.640653, 0.654436, 0.667934,
            0.681165, 0.694144, 0.706884, 0.719399, 0.7317]
        return cp_multiplier[level-1]

    def buildPokemonQuery(self, pkm):
        valuesQuery = None
        queryParts = []
        subQueryParts = []
        valuesQueryParts = []

        queryParts.append('pokemon_id = %s' % pkm['id'])

        if pkm['iv'] > 0:
            valuesQueryParts.append('(individual_attack + individual_defense + individual_stamina) >= %s' % (float(pkm['iv'])/100*45))
        if pkm['cp'] > 0:
            valuesQueryParts.append('cp >= %s' % pkm['cp'])
        if pkm['level'] > 0:
            valuesQueryParts.append('cp_multiplier >= %s' % self.get_pokemon_cpm(pkm['level']))
        if pkm['match_mode'] == 0:
            valuesQuery = ' AND '.join(valuesQueryParts)
        elif pkm['match_mode'] == 1:
            valuesQuery = ' OR '.join(valuesQueryParts)
        if valuesQuery:
            subQueryParts.append('(' + valuesQuery + ')')

        if 'lat_max' in pkm:
            locationQuery = 'latitude BETWEEN %s AND %s' % (pkm['lat_min'], pkm['lat_max'])
            locationQuery += ' AND '
            locationQuery += 'longitude BETWEEN %s AND %s' % (pkm['lng_min'], pkm['lng_max'])
            subQueryParts.append('(' + locationQuery + ')')

        if subQueryParts:
            if pkm['match_mode'] == 2:
                queryParts.append('(' + ' OR '.join(subQueryParts) + ')')
            else:
                queryParts.append('(' + ' AND '.join(subQueryParts) + ')')

        return '(' + ' AND '.join(queryParts) + ')'

    def getPokemonByList(self, pokemonList, sendWithout = True):
        sqlquery = ("SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, weight, height, gender, form, cp, cp_multiplier "
            "FROM pokemon WHERE last_modified > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) AND disappear_time > UTC_TIMESTAMP()")
        sqlquery += ' AND (' + ' OR '.join(list(map(self.buildPokemonQuery, pokemonList))) + ')'
        if not sendWithout:
            sqlquery += ' AND individual_attack IS NOT NULL'
        sqlquery += ' ORDER BY pokemon_id ASC'

        return self.executePokemonQuery(sqlquery)

    def getPokemonByIds(self, ids, sendWithout = True):
        sqlquery = ("SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, weight, height, gender, form, cp, cp_multiplier "
            "FROM pokemon WHERE last_modified > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) AND disappear_time > UTC_TIMESTAMP()")
        sqlquery += ' AND pokemon_id in (' + ','.join(map(str, ids)) + ')'
        if not sendWithout:
            sqlquery += ' AND individual_attack IS NOT NULL'
        sqlquery += ' ORDER BY pokemon_id ASC'

        return self.executePokemonQuery(sqlquery)

    def executePokemonQuery(self, sqlquery):
        pokelist = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sqlquery)
                rows = cur.fetchall()
                for row in rows:
                    encounter_id = str(row[0]) if row[0] is not None else None
                    spawn_point = str(row[1]) if row[1] is not None else None
                    pokemon_id = int(row[2]) if row[2] is not None else None
                    latitude = float(row[3]) if row[3] is not None else None
                    longitude = float(row[4]) if row[4] is not None else None
                    disappear_time = datetime.strptime(str(row[5])[0:19], "%Y-%m-%d %H:%M:%S") if row[5] is not None else None
                    individual_attack = int(row[6]) if row[6] is not None else None
                    individual_defense = int(row[7]) if row[7] is not None else None
                    individual_stamina = int(row[8]) if row[8] is not None else None
                    move1 = int(row[9]) if row[9] is not None else None
                    move2 = int(row[10]) if row[10] is not None else None
                    weight = float(row[11]) if row[11] is not None else None
                    height = float(row[12]) if row[12] is not None else None
                    gender = int(row[13]) if row[13] is not None else None
                    form = int(row[14]) if row[14] is not None else None
                    cp = int(row[15]) if row[15] is not None else None
                    cp_multiplier = float(row[16]) if row[16] is not None else None
                    ivs = round(float((individual_attack + individual_defense + individual_stamina) / 45 * 100), 1) if individual_attack is not None else None

                    poke = DSPokemon(encounter_id, spawn_point, pokemon_id, latitude, longitude, disappear_time, ivs, move1, move2, weight, height, gender, form, cp, cp_multiplier)
                    pokelist.append(poke)

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                logger.error(e)

        except Exception as e:
            logger.error(e)

        return pokelist

    def buildRaidQuery(self, raid):
        queryParts = []

        queryParts.append('pokemon_id = %s' % raid['id'])

        if 'lat_max' in raid:
            locationQuery = 'latitude BETWEEN %s AND %s' % (raid['lat_min'], raid['lat_max'])
            locationQuery += ' AND '
            locationQuery += 'longitude BETWEEN %s AND %s' % (raid['lng_min'], raid['lng_max'])
            queryParts.append('(' + locationQuery + ')')

        return '(' + ' AND '.join(queryParts) + ')'

    def getRaidsByList(self, raidList, sendWithout = True):
        sqlquery = ("SELECT raid.gym_id, name, latitude, longitude, "
            "start, end, pokemon_id, cp, move_1, move_2 "
            "FROM raid JOIN gym ON gym.gym_id=raid.gym_id JOIN gymdetails ON gym.gym_id=gymdetails.gym_id "
            "WHERE raid.last_scanned > (UTC_TIMESTAMP() - INTERVAL 10 MINUTE) AND end > UTC_TIMESTAMP()")
        sqlquery += ' AND (' + ' OR '.join(list(map(self.buildRaidQuery, raidList))) + ') ORDER BY end ASC'

        return self.executeRaidQuery(sqlquery)

    def executeRaidQuery(self, sqlquery):
        raidlist = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sqlquery)
                rows = cur.fetchall()
                for row in rows:
                    gym_id = str(row[0]) if row[0] is not None else None
                    name = str(row[1]) if row[1] is not None else None
                    latitude = float(row[2]) if row[2] is not None else None
                    longitude = float(row[3]) if row[3] is not None else None
                    start = datetime.strptime(str(row[4])[0:19], "%Y-%m-%d %H:%M:%S") if row[4] is not None else None
                    end = datetime.strptime(str(row[5])[0:19], "%Y-%m-%d %H:%M:%S") if row[5] is not None else None
                    pokemon_id = int(row[6]) if row[6] is not None else None
                    cp = int(row[7]) if row[7] is not None else None
                    move1 = int(row[8]) if row[8] is not None else None
                    move2 = int(row[9]) if row[9] is not None else None

                    raid = DSRaid(gym_id, name, latitude, longitude, start, end, pokemon_id, cp, move1, move2)
                    raidlist.append(raid)

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                logger.error(e)

        except Exception as e:
            logger.error(e)

        return raidlist

    def getGymsByName(self, gymname, wildcard=True):
        sqlquery = ("SELECT gym.gym_id, name, latitude, longitude "
                    "FROM gym JOIN gymdetails "
                    "ON gym.gym_id=gymdetails.gym_id WHERE ")
        if wildcard:
            sqlquery += "name LIKE %s"
            gymname = '%' + gymname + '%'
        else:
            sqlquery += "name=%s COLLATE utf8_bin"

        gymlist = []
        try:
            with self.con:
                cur = self.con.cursor()
                cur.execute(sqlquery, (gymname,))
                rows = cur.fetchall()
                for row in rows:
                    gym_id = str(row[0]) if row[0] is not None else None
                    name = str(row[1]) if row[1] is not None else None
                    latitude = float(row[2]) if row[2] is not None else None
                    longitude = float(row[3]) if row[3] is not None else None

                    gym = DSGym(gym_id, name, latitude, longitude)
                    gymlist.append(gym)

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                logger.error(e)

        except Exception as e:
            logger.error(e)

        return gymlist

    def __connect(self):
        self.con = pymysql.connect(user=self.__user, password=self.__passw, host=self.__host, port=self.__port, database=self.__db)

    def __reconnect(self):
        logger.info('Reconnecting to remote database')
        self.__connect()

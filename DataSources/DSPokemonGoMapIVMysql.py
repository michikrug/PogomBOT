from .DSPokemon import DSPokemon

import os
from datetime import datetime
import logging

import pymysql
import re

logger = logging.getLogger(__name__)

class DSPokemonGoMapIVMysql():
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

    def buildPokemonQuery(self, pkm):
        queryParts = []
        queryParts.append('pokemon_id = %s' % pkm['id'])
        ivQuery = '(individual_attack + individual_defense + individual_stamina) >= %s' % (float(pkm['iv'])/100*45) if pkm['iv'] > 0 else ''
        cpQuery = 'cp >= %s' % pkm['cp'] if pkm['cp'] > 0 else ''
        if ivQuery or cpQuery:
            ivcpQuery = '(' + ivQuery
            if ivQuery and cpQuery:
                if pkm['match_mode'] == 0:
                    ivcpQuery += ' AND '
                elif pkm['match_mode'] == 1:
                    ivcpQuery += ' OR '
            ivcpQuery += cpQuery + ')'
            queryParts.append(ivcpQuery)
        if 'lat_max' in pkm:
            queryParts.append('latitude BETWEEN %s AND %s' % (pkm['lat_min'], pkm['lat_max']))
            queryParts.append('longitude BETWEEN %s AND %s' % (pkm['lng_min'], pkm['lng_max']))
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
                    encounter_id = str(row[0])
                    spawn_point = str(row[1])
                    pok_id = int(row[2]) if row[2] is not None else None
                    latitude = float(row[3]) if row[3] is not None else None
                    longitude = float(row[4]) if row[4] is not None else None
                    disappear = str(row[5])
                    disappear_time = datetime.strptime(disappear[0:19], "%Y-%m-%d %H:%M:%S")
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

                    poke = DSPokemon(encounter_id, spawn_point, pok_id, latitude, longitude, disappear_time, ivs, move1, move2, weight, height, gender, form, cp, cp_multiplier)
                    pokelist.append(poke)

        except pymysql.err.OperationalError as e:
            if e.args[0] == 2006:
                self.__reconnect()
            else:
                logger.error(e)

        except Exception as e:
            logger.error(e)

        return pokelist

    def __connect(self):
        self.con = pymysql.connect(user=self.__user, password=self.__passw, host=self.__host, port=self.__port, database=self.__db)

    def __reconnect(self):
        logger.info('Reconnecting to remote database')
        self.__connect()

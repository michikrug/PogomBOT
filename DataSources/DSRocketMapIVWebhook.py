import itertools
import json
import logging
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from .DSPokemon import DSPokemon
from .DSRaid import DSRaid

logger = logging.getLogger(__name__)


def startServer(port):
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    server.serve_forever()


#WebHook CallBack
#Request body contains:
# - type: String ("pokemon")
# - message: Object
#   - disappear_time: Long
#   - encounter_id: String (B64?, e.g. MTA0NTI4NzU4MzE0ODQzMDIwNjE=)
#   - pokemon_id: Integer (e.g. 11)
#   - spawnpoint_id: String (e.g. 47c3c2a0e33)
#   - longitude: 40.442506
#   - latitude: -79.957962
class WebhookHandler(BaseHTTPRequestHandler):
    instance = None

    def do_POST(self):
        data_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(data_length)
        payload = post_data.decode('utf-8')
        js = json.loads(payload)
        if js['type'] == 'pokemon':
            data = js['message']
            encounter_id = str(data[
                'encounter_id']) if data['encounter_id'] is not None else None
            spawn_point = str(data['spawnpoint_id']
                              ) if data['spawnpoint_id'] is not None else None
            pok_id = int(
                data['pokemon_id']) if data['pokemon_id'] is not None else None
            latitude = float(
                data['latitude']) if data['latitude'] is not None else None
            longitude = float(
                data['longitude']) if data['longitude'] is not None else None
            disappear_time = datetime.utcfromtimestamp(
                data['disappear_time']
            ) if data['disappear_time'] is not None else None
            individual_attack = int(
                data['individual_attack']
            ) if data['individual_attack'] is not None else None
            individual_defense = int(
                data['individual_defense']
            ) if data['individual_defense'] is not None else None
            individual_stamina = int(
                data['individual_stamina']
            ) if data['individual_stamina'] is not None else None
            move1 = int(data['move_1']) if data['move_1'] is not None else None
            move2 = int(data['move_2']) if data['move_2'] is not None else None
            weight = float(
                data['weight']) if data['weight'] is not None else None
            height = float(
                data['height']) if data['height'] is not None else None
            gender = int(
                data['gender']) if data['gender'] is not None else None
            form = int(data['form']) if data['form'] is not None else None
            cp = int(data['cp']) if data['cp'] is not None else None
            cp_multiplier = float(
                data['cp_multiplier']
            ) if data['cp_multiplier'] is not None else None
            ivs = round(
                float((
                    individual_attack + individual_defense + individual_stamina
                ) / 45 * 100), 1) if individual_attack is not None else None

            poke = DSPokemon(encounter_id, spawn_point, pok_id, latitude,
                             longitude, disappear_time, ivs, move1, move2,
                             weight, height, gender, form, cp, cp_multiplier)
            self.instance.addPoke(poke)
        elif js['type'] == 'raid':
            #TODO
            pass
        elif js['type'] == 'pokestop':
            pass
        elif js['type'] == 'gym':
            pass
        elif js['type'] == 'gym-details':
            pass
        else:
            pass
        self.send_response(200)

    # disable webserver logging
    def log_message(self, format, *args):
        return


class DSRocketMapIVWebhook():
    poke_method = None
    raid_method = None

    def __init__(self, connectString, poke_method, raid_method):
        port = int(connectString)
        logger.info('Starting webhook on port %s.' % (port))
        self.pokeDict = dict()
        self.lock = threading.Lock()
        WebhookHandler.instance = self
        th = threading.Thread(target=startServer, args=[int(port)])
        th.start()
        self.poke_method = poke_method
        self.raid_method = raid_method

    def addPoke(self, poke):
        self.poke_method(poke)
        pass

    def getPokemonByIds(self, ids, sendWithout=True):
        return []

    def getPokemonByList(self, pokemonList, sendWithout=True):
        return []

    def addRaid(self, raid):
        self.raid_method(raid)
        pass

    def getRaidByList(self, raidList):
        return []

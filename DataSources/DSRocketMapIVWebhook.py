import json
import logging
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from .Conversion import (floatOrNone, intOrNone, strOrNone,
                         utcfromtimestampOrNone)
from .DSPokemon import DSPokemon

LOGGER = logging.getLogger(__name__)


def start_server(port):
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
            ivs = round(
                float((int(data['individual_attack']) + int(data['individual_defense']) +
                       int(data['individual_stamina'])) / 45 * 100),
                1) if data['individual_attack'] is not None else None

            self.instance.add_poke(
                DSPokemon(
                    strOrNone(data['encounter_id']), strOrNone(data['spawnpoint_id']),
                    intOrNone(data['pokemon_id']), floatOrNone(data['latitude']),
                    floatOrNone(data['longitude']), utcfromtimestampOrNone(data['disappear_time']),
                    ivs, intOrNone(data['move_1']), intOrNone(data['move_2']),
                    floatOrNone(data['weight']), floatOrNone(data['height']),
                    intOrNone(data['gender']), intOrNone(data['form']), intOrNone(data['cp']),
                    floatOrNone(data['cp_multiplier'])))
        elif js['type'] == 'raid':
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
        LOGGER.info('Starting webhook on port %s.' % (port))
        self.lock = threading.Lock()
        WebhookHandler.instance = self
        th = threading.Thread(target=start_server, args=[int(port)])
        th.start()
        self.poke_method = poke_method
        self.raid_method = raid_method

    def add_poke(self, poke):
        self.poke_method(poke)

    def get_pokemon_by_ids(self, ids, send_without=True):
        return []

    def get_pokemon_by_list(self, pokemon_list, send_without=True):
        return []

    def add_raid(self, raid):
        self.raid_method(raid)

    def get_raids_by_list(self, raid_list):
        return []

    def get_gyms_by_name(self, gym_name, use_id=False):
        return []

    def add_new_raid(self, gym_id, level, spawn, start, end, pokemon_id):
        LOGGER.info("%s, %s, %s, %s, %s, %s, %s" % (gym_id,
            level,
            spawn.strftime('%Y-%m-%d %H:%M:%S'),
            start.strftime('%Y-%m-%d %H:%M:%S'),
            end.strftime('%Y-%m-%d %H:%M:%S'),
            pokemon_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

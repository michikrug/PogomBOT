import fnmatch
import json
import os
import sys

user_directory = os.path.join(os.path.dirname(sys.argv[0]), '../userdata')

for file in os.listdir(user_directory):
    if fnmatch.fnmatch(file, '*.json'):
        with open(os.path.join(user_directory, file), 'r+', encoding='utf-8') as f:
            old_preferences = json.load(f)
            if 'only_map' in old_preferences:
                new_preferences = dict()
                new_preferences['language'] = old_preferences.get('language')
                new_preferences['location'] = old_preferences.get('location')
                new_preferences['stickers'] = old_preferences.get('stickers')
                new_preferences['maponly'] = old_preferences.get('only_map')
                new_preferences['walkdist'] = old_preferences.get('walk_dist')
                new_preferences['sendwithout'] = old_preferences.get('send_without')
                new_preferences['iv'] = old_preferences.get('miniv')
                new_preferences['cp'] = old_preferences.get('mincp')
                new_preferences['level'] = old_preferences.get('minlevel')
                new_preferences['matchmode'] = old_preferences.get('match_mode')
                new_preferences['pkmids'] = old_preferences.get('search_ids')
                new_preferences['pkmradius'] = old_preferences.get('search_dists')
                new_preferences['pkmiv'] = old_preferences.get('search_miniv')
                new_preferences['pkmcp'] = old_preferences.get('search_mincp')
                new_preferences['pkmlevel'] = old_preferences.get('search_minlevel')
                new_preferences['pkmmatchmode'] = old_preferences.get('search_matchmode')
                new_preferences['raidids'] = old_preferences.get('raid_ids')
                new_preferences['raidradius'] = old_preferences.get('raid_dists')
                f.seek(0)
                json.dump(new_preferences, f, indent=4, sort_keys=True, separators=(',', ':'))
                f.truncate()

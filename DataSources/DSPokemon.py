from geopy.distance import distance


class DSPokemon:

    def __init__(self, encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time,
                 ivs, move1, move2, weight, height, gender, form, cp, cp_multiplier):
        self.encounter_id = encounter_id
        self.spawnpoint_id = spawnpoint_id
        self.pokemon_id = pokemon_id
        self.latitude = latitude
        self.longitude = longitude
        self.disappear_time = disappear_time
        self.ivs = ivs
        self.move1 = move1
        self.move2 = move2
        self.weight = weight
        self.height = height
        self.gender = gender
        self.form = form
        self.cp = cp
        self.cp_multiplier = cp_multiplier
        self.level = self.calc_pokemon_level()

    def get_encounter_id(self):
        return self.encounter_id

    def get_spawnpoint_id(self):
        return self.spawnpoint_id

    def get_pokemon_id(self):
        return self.pokemon_id

    def get_latitude(self):
        return self.latitude

    def get_longitude(self):
        return self.longitude

    def get_disappear_time(self):
        return self.disappear_time

    def get_ivs(self):
        return self.ivs

    def get_move1(self):
        return self.move1

    def get_move2(self):
        return self.move2

    def get_weight(self):
        return self.weight

    def get_height(self):
        return self.height

    def get_gender(self):
        return self.gender

    def get_form(self):
        return self.form

    def get_cp(self):
        return self.cp

    def get_cp_multiplier(self):
        return self.cp_multiplier

    def get_level(self):
        return self.level

    def get_distance(self, user_location):
        user_lat_lon = (user_location[0], user_location[1])
        pok_loc = (self.latitude, self.longitude)
        return distance(user_lat_lon, pok_loc).km

    def filter_by_location(self, user_location):
        return self.get_distance(user_location) <= user_location[2]

    def calc_pokemon_level(self):
        if not self.cp_multiplier:
            return None
        if self.cp_multiplier < 0.734:
            pokemon_level = (58.35178527 * self.cp_multiplier * self.cp_multiplier -
                             2.838007664 * self.cp_multiplier + 0.8539209906)
        else:
            pokemon_level = 171.0112688 * self.cp_multiplier - 95.20425243
        pokemon_level = int((round(pokemon_level) * 2) / 2)
        return pokemon_level

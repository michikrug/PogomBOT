from geopy.distance import distance


class DSRaid:

    def __init__(self, gym_id, name, latitude, longitude, start, end, pokemon_id, cp, move1, move2):
        self.gym_id = gym_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.start = start
        self.end = end
        self.pokemon_id = pokemon_id
        self.cp = cp
        self.move1 = move1
        self.move2 = move2

    def get_gym_id(self):
        return self.gym_id

    def get_name(self):
        return self.name

    def get_latitude(self):
        return self.latitude

    def get_longitude(self):
        return self.longitude

    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

    def get_pokemon_id(self):
        return self.pokemon_id

    def get_cp(self):
        return self.cp

    def get_move1(self):
        return self.move1

    def get_move2(self):
        return self.move2

    def get_distance(self, user_location):
        user_lat_lon = (user_location[0], user_location[1])
        raid_loc = (self.latitude, self.longitude)
        return distance(user_lat_lon, raid_loc).km

    def filter_by_location(self, user_location):
        return self.get_distance(user_location) <= user_location[2]

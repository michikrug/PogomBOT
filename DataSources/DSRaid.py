from geopy.distance import vincenty

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

    def getGymId(self):
        return self.gym_id

    def getName(self):
        return self.name

    def getLatitude(self):
        return self.latitude

    def getLongitude(self):
        return self.longitude

    def getStart(self):
        return self.start

    def getEnd(self):
        return self.end

    def getPokemonID(self):
        return self.pokemon_id

    def getCP(self):
        return self.cp

    def getMove1(self):
        return self.move1

    def getMove2(self):
        return self.move2

    def getDistance(self, user_location):
        user_lat_lon = (user_location[0], user_location[1])
        raid_loc = (self.latitude, self.longitude)
        return vincenty(user_lat_lon, raid_loc).km

    def filterbylocation(self, user_location):
        return self.getDistance(user_location) <= user_location[2]

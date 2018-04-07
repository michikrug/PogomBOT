from geopy.distance import vincenty


class DSGym:
    def __init__(self, gym_id, name, latitude, longitude):
        self.gym_id = gym_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude

    def getGymId(self):
        return self.gym_id

    def getName(self):
        return self.name

    def getLatitude(self):
        return self.latitude

    def getLongitude(self):
        return self.longitude

    def getDistance(self, user_location):
        user_lat_lon = (user_location[0], user_location[1])
        gym_loc = (self.latitude, self.longitude)
        return vincenty(user_lat_lon, gym_loc).km

    def filterbylocation(self, user_location):
        return self.getDistance(user_location) <= user_location[2]

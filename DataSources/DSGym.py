from geopy.distance import vincenty


class DSGym:

    def __init__(self, gym_id, name, latitude, longitude):
        self.gym_id = gym_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude

    def get_gym_id(self):
        return self.gym_id

    def get_name(self):
        return self.name

    def get_latitude(self):
        return self.latitude

    def get_longitude(self):
        return self.longitude

    def get_distance(self, user_location):
        user_lat_lon = (user_location[0], user_location[1])
        gym_loc = (self.latitude, self.longitude)
        return vincenty(user_lat_lon, gym_loc).km

    def filter_by_location(self, user_location):
        return self.get_distance(user_location) <= user_location[2]

import googlemaps
from datetime import datetime
import requests
import datetime
import MySQLdb
import math
import config

URL = 'https://maps.googleapis.com/maps/api/'

gmaps = googlemaps.Client(config.GOOGLEMAPS_KEY)


class Direction:
    """
    Родительский класс для Route и Step
    """
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.polyline = ''

    def get_static_map(self, size='600x300', weight='3', color='0x0000ff80'):
        url = '{}staticmap?size={}&markers=color:blue|label:1|{},{}&markers=color:red|label:2|{},{}&path=weight:{}' \
              '|color:{}|enc:{}&key={}'.format(URL, size, self.start[0], self.start[1], self.end[0], self.end[1],
                                               weight, color, self.polyline, config.GOOGLEMAPS_KEY)
        r = requests.get(url)
        return r.url

    def get_azimut(self):
        y = self.end[1] - self.start[1]
        x = self.end[0] - self.start[0]
        i = math.atan2(y, x)
        return math.degrees(i)


class Route(Direction):
    """
    Класс описывающий маршрут
    """
    def __init__(self, user_id, start=None, end=None):
        super().__init__(start, end)
        self.user_id = user_id
        if start is not None or end is not None:
            direction = gmaps.directions(self.start, self.end, mode='walking', language='ru')[0]
            self.start = (direction['legs'][0]['start_location']['lat'], direction['legs'][0]['start_location']['lng'])
            self.end = (direction['legs'][0]['end_location']['lat'], direction['legs'][0]['end_location']['lng'])
            self.polyline = direction['overview_polyline']['points']
            self.distance = direction['legs'][0]['distance']['text']
            self.duration = direction['legs'][0]['duration']['text']
            self.steps = [
                Step(
                    (i['start_location']['lat'], i['start_location']['lng']),
                    (i['end_location']['lat'], i['end_location']['lng']),
                    i['distance']['text'],
                    i['duration']['text'],
                    i['html_instructions'],
                    i['polyline']['points']) for i in direction['legs'][0]['steps']
            ]

    def add_route_to_db(self):
        date = datetime.datetime.now()
        conn = MySQLdb.connect('localhost', 'root', config.DB_PASSWORD, config.DB_NAME)
        conn.set_character_set('utf8')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO route (
            user_id,
            date,
            start_location_lat,
            start_location_lng,
            end_location_lat,
            end_location_lng,
            polyline,
            distance,
            duration
        ) VALUES((%s),(%s),(%s),(%s),(%s),(%s),(%s),(%s),(%s));
        ''', (
            self.user_id,
            date,
            self.start[0],
            self.start[1],
            self.end[0],
            self.end[1],
            self.polyline,
            self.distance.encode('UTF-8'),
            self.duration.encode('UTF-8')
        ))
        cursor.execute('SELECT max(id) FROM route WHERE user_id = (%s)', (self.user_id,))
        route = cursor.fetchall()[0][0]
        st = []
        for i, step in enumerate(self.steps):
            c = (
                i,
                route,
                step.end[0],
                step.end[1],
                step.instructions.encode('UTF-8'),
                step.start[0],
                step.start[1],
                step.polyline,
                step.distance.encode('UTF-8'),
                step.duration.encode('UTF-8'),
                False
            )
            st.append(c)
        cursor.executemany('''
        INSERT INTO step (
            step_number,
            route,
            end_location_lat,
            end_location_lng,
            instructions,
            start_location_lat,
            start_location_lng,
            polyline,
            distance,
            duration,
            passed
        ) VALUES ((%s),(%s),(%s),(%s), (%s),(%s),(%s),(%s),(%s),(%s),(%s))
        ''', st)
        conn.commit()
        conn.close()

    def get_step_from_db(self, offset=0):
        """
        Возвращает первый непройденный шаг маршрута (passed=0) из базы данных. Параметр offset указывает смещение 
        относительно данного шага. Если все шаги пройдены возвращает False.        
        """
        conn = MySQLdb.connect('localhost', 'root', config.DB_PASSWORD, config.DB_NAME)
        conn.set_character_set('utf8')
        cursor = conn.cursor()
        cursor.execute('SELECT max(id) FROM route WHERE user_id = (%s)', (self.user_id,))
        route = cursor.fetchall()[0][0]
        cursor.execute('''
        SELECT 
            start_location_lat,
            start_location_lng,
            instructions,
            end_location_lat,
            end_location_lng,
            polyline,
            distance,
            duration,
            step_id,
            passed
        FROM step WHERE route = (%s)''', (route,))
        result = cursor.fetchall()
        conn.commit()
        conn.close()
        try:
            steps = [Step((r[0], r[1]), (r[3], r[4]), r[6], r[7], r[2], r[5], r[8], r[9]) for r in result]
            passed_steps = list(filter(lambda x: x.passed, steps))
            i = len(passed_steps)
            step = steps[i + offset]
            return step
        except IndexError:
            return False


class Step(Direction):
    """
    Класс описывающий шаг маршрута
    """
    def __init__(self, start, end, distance=None, duration=None, instructions=None, polyline=None, id=None, passed=None):
        super().__init__(start, end)
        self.distance = distance
        self.duration = duration
        self.instructions = instructions
        self.polyline = polyline
        self.azimut = self.get_azimut()
        self.id = id
        self.passed = passed

    def get_street_view(self, fov='90', pitch='0', size='600x300'):
        url = '{}streetview?size={}&location={},{}&fov={}&heading={}&pitch={}&key={}'.format(URL, size, self.start[0],
                                                                                             self.start[1], fov,
                                                                                             self.azimut, pitch,
                                                                                             config.GOOGLEMAPS_KEY)
        r = requests.get(url)
        return r.url

    def get_passed_step(self):
        conn = MySQLdb.connect('localhost', 'root', config.DB_PASSWORD, config.DB_NAME)
        conn.set_character_set('utf8')
        cursor = conn.cursor()
        cursor.execute('UPDATE step SET passed = True WHERE step_id = (%s)', (self.id,))
        conn.commit()
        conn.close()

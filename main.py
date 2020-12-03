import urllib
from typing import Optional, Awaitable, Dict, List
from enum import Enum
import random
import re
import datetime

import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import uuid

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)


class GameState(str, Enum):
    PREGAME = 1,
    PLAYING = 2,
    POSTGAME = 3


class Presenter:
    def __init__(self, token=str(uuid.uuid4())):
        self.token = token

    def __repr__(self) -> str:
        return f"Presenter: Token: {self.token}"


class Player:

    def __init__(self, name, prompt, token=str(uuid.uuid4())):
        self.name = name
        self.prompt = prompt
        self.token = token
        self.image = None
        self.is_ready = False

    def __repr__(self) -> str:
        return f"Player: Name: {self.name}, Prompt: {self.prompt}, Token: {self.token}"


class Room:
    players: List[Player]
    presenter: Presenter
    game_state = GameState.PREGAME
    timeout: int

    def __init__(self) -> None:
        super().__init__()
        self.players = []
        self.presenter = None
        self.game_state = GameState.PREGAME
        self.round_count = 1
        self.current_task_is_drawing = True
        self.histories = []
        self.prompts = ["Buch", "Kino", "Konzert", "Obama", "Der Durchschnittsinformatiker", "Der Nerd",
                   "Schlittschuhlaufen", "LKW", "Kokosnuss", "Asiate", "Zug", "Kartoffel", "Among Us", "Apfel", "Birne",
                   "Banane", "Spaghetti", "Wasser", "Bier", "Flugzeug", "Schiff", "Orange", "Wassermelone", "Tisch",
                   "Schrank", "Auto", "Maus", "Giraffe", "Krankenhaus", "Kran", "Wasserhahn", "Propeller", "Muschel",
                   "Mond", "Erde", "Fließband", "Fabrik", "Sklaverei", "Krabbe", "Geschwindigkeitsmesser", "Wohnwagen",
                   "Kirchenschiff", "Flammenwerfer", "Bettdecke", "Selbstbedienung", "Torpedo", "Professur",
                   "Reagenzglas", "Laryngitis", "Deportieren", "Wandschrank", "Luftpumpe", "Röhrenfernseher", "Erdnuss",
                   "Räuchermännchen", "Haferflocken", "Sofa", "Sessel", "Handwerker", "Info-Fakultätsspezifisches",
                   "Dorffest", "Prof. Weber", "Käsefest"]
        random.shuffle(self.prompts)
        self.timeout = 0
        self.last_access = datetime.datetime.now()
        self.max_rounds = 0

    def get_new_prompt(self):
        return self.prompts.pop()

    def add_player(self, player: Player):
        self.players += [player]

    def add_presenter(self, presenter: Presenter):
        self.presenter = presenter

    def __repr__(self) -> str:
        ret = f"Presenter: {self.presenter}. Timeout: {self.timeout}. Players: "
        for player in self.players:
            ret += repr(player) + ". "
        return ret


rooms: Dict[str, Room] = {}


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/websocket", WebSocketHandler)
        ]
        settings = dict(
            # cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        super().__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    global rooms

    def get(self):
        room_id_param = self.get_arguments("room_id")
        logging.info(f"main GET, message is {self}, rooms are {rooms}")
        logging.info(f"main GET, rooms are {rooms}")

        # Delete rooms which were not accessed in the last 10 minutes
        rooms_to_delete = []
        for room_id in rooms:
            if datetime.datetime.now() - rooms[room_id].last_access > datetime.timedelta(minutes=10):
                logging.info(f"Room {rooms[room_id]} not accessed for at least 10 minutes. Deleting …")
                rooms_to_delete += room_id
        for r in rooms_to_delete:
            del rooms[r]

        # If room id supplied, create room or join it
        if len(room_id_param) == 1:
            room_id = room_id_param[0]
            new_token = str(uuid.uuid4())

            # If room does not exist, create it and set requester to presenter
            if room_id not in rooms:
                new_room = Room()
                rooms[room_id] = new_room
                rooms.get(room_id).add_presenter(Presenter(new_token))
                self.set_cookie("token", new_token)
                self.render("dashboard.html")
                logging.info(f"Rooms after creating new: {rooms}")
            else:
                room = rooms.get(room_id)
                room.last_access = datetime.datetime.now()

                # Check if presenter just refreshed the page
                if room.presenter.token == self.get_cookie("token"):
                    self.render("dashboard.html")
                    return

                # Check if player just refreshed the page
                for p in room.players:
                    if p.token == self.get_cookie("token"):
                        self.render("game.html")
                        update_dashboard(room)
                        return

                name = self.get_cookie("name")
                if name is None:
                    self.render("player_setup.html")
                else:
                    # Sanitize name
                    name = re.sub('[^a-zA-Z0-9]', '', name)

                    room.add_player(Player(name, "", new_token))
                    logging.info(f"Added player {name} with token {new_token}")

                    self.set_cookie("token", new_token)
                    self.render("game.html")

                    # Update Presenter UI
                    update_dashboard(room)

        # Else just show intro page
        else:
            self.render("index.html")


def update_dashboard(room: Room):
    message = {
        "game_state": room.game_state,
        "players": [
            [p.name for p in room.players if p.is_ready],
            [p.name for p in room.players if not p.is_ready]
        ],
        "round_count": room.round_count,
        "max_rounds": (len(room.players) // 2) * 2,
        "timeout": room.timeout
    }
    WebSocketHandler.send_updates(room.presenter.token, message)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    token: str = ""
    global rooms

    def check_origin(self, origin: str) -> bool:
        parsed_origin = urllib.parse.urlparse(origin)
        return parsed_origin.netloc.endswith("kumula.me")
        # TODO: Change me before prod
        # return True

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def open(self):
        self.token = self.get_cookie("token")
        WebSocketHandler.waiters.add(self)
        logging.info(f"Websocket opened. Message: {self}")

    def on_close(self):
        WebSocketHandler.waiters.remove(self)


    @classmethod
    def send_updates(cls, token: str, message):
        for waiter in cls.waiters:
            try:
                logging.info(f"Send message {message} with {token} to {waiter.token}? {token == waiter.token}")
                if token == waiter.token:
                    waiter.write_message(message)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):
        logging.info("got message %r", message)
        parsed = tornado.escape.json_decode(message)

        if "room_id" not in parsed or parsed["room_id"] not in rooms:
            logging.info("Room not found")
            return
        room = rooms.get(parsed["room_id"])
        room.last_access = datetime.datetime.now()

        if room.presenter.token == parsed["token"]:
            if room.game_state is GameState.PREGAME:
                if parsed["command"] == "reconnect_check":
                    update_dashboard(room)

                if parsed["command"] == "start_game":
                    # Shuffle players
                    random.shuffle(room.players)

                    # Set timeout
                    if not parsed["timeout"] == "":
                        try:
                            room.timeout = int(parsed["timeout"])
                        except SyntaxError:
                            pass

                    # Set max amount of rounds
                    if not parsed["round_count"] == "":
                        try:
                            rounds = int(parsed["round_count"])
                            if rounds <= 1 or rounds >= (len(room.players) // 2) * 2:
                                room.max_rounds = (len(room.players) // 2) * 2
                            else:
                                room.max_rounds = rounds

                        except SyntaxError:
                            room.max_rounds = (len(room.players) // 2) * 2

                    # Send info to players
                    for player_iter in room.players:
                        player_iter.prompt = room.get_new_prompt()
                        message = {
                            "prompt": player_iter.prompt,
                            "timeout": room.timeout
                        }
                        WebSocketHandler.send_updates(player_iter.token, message)
                        # Create histories
                        room.histories.append([("Computer", player_iter.prompt)])

                    room.game_state = GameState.PLAYING
                    update_dashboard(room)
                    logging.info(f"Histories: {room.histories}")
                    logging.info(f"Room: {room}")
                    return
            elif room.game_state is GameState.PLAYING:
                # Presenter stuff
                pass
            elif room.game_state is GameState.POSTGAME:
                if parsed["command"] == "start_new_game":
                    for p in room.players:
                        message = {
                            "game_state": room.game_state,
                            "command": "reload"
                        }
                        WebSocketHandler.send_updates(p.token, message)
                    logging.info(f"Reloading game with room_id {parsed['room_id']}")

        else:
            # Check if a player sent a message
            player = None
            for i in range(len(room.players)):
                player_iter = room.players[i]
                if parsed["token"] == player_iter.token:
                    player = player_iter
                    player_pos = i

            if player is None:
                logging.info("Player not found")
                return

            if room.game_state is GameState.PLAYING:
                # Check if someone refreshes the page, give them the current game state
                if "command" in parsed:
                    if parsed["command"] == "reconnect_check":
                        if player.is_ready:
                            return
                        if room.current_task_is_drawing:
                            message = {
                                "prompt": player.prompt
                            }
                        else:
                            message = {
                                "image": player.image
                            }
                        WebSocketHandler.send_updates(player.token, message)
                        update_dashboard(room)
                        return

                # Last round if round threshold reached
                logging.info(f"Room count: {room.round_count}")
                if room.round_count >= room.max_rounds:
                    logging.info("Round count reached")
                    # Get last prompt
                    player.prompt = parsed["prompt"]
                    player.is_ready = True

                    # Update UI
                    update_dashboard(room)

                    for player_iter in room.players:
                        if not player_iter.is_ready:
                            return

                    # Update histories
                    for i in range(len(room.players)):
                        room.histories[i].append((room.players[i].name, room.players[i].prompt))

                    room.game_state = GameState.POSTGAME

                    message = {
                        "game_state": room.game_state,
                        "histories": room.histories
                    }
                    WebSocketHandler.send_updates(room.presenter.token, message)

                    # Game done on server, delete it
                    # TODO: Keep players somewhere, so their site can be refreshed
                    del rooms[parsed["room_id"]]

                    return

                elif room.current_task_is_drawing:
                    player.image = parsed["image"]
                    player.is_ready = True

                    # Update UI
                    update_dashboard(room)

                    for player_iter in room.players:
                        if not player_iter.is_ready:
                            return

                    # All players ready
                    # Give next player the image
                    for i in range(len(room.players) - 1):
                        message = {"image": room.players[i].image}
                        WebSocketHandler.send_updates(room.players[i+1].token, message)
                    # Give first player last player's image
                    message = {"image": room.players[len(room.players) - 1].image}
                    WebSocketHandler.send_updates(room.players[0].token, message)

                    # Update histories
                    for i in range(len(room.players)):
                        room.histories[i].append((room.players[i].name, room.players[i].image))
                else:
                    player.prompt = parsed["prompt"]
                    player.is_ready = True

                    # Update UI
                    update_dashboard(room)

                    for player_iter in room.players:
                        if not player_iter.is_ready:
                            return

                    # All players ready
                    # Give next player the prompt
                    for i in range(len(room.players) - 1):
                        message = {"prompt": room.players[i].prompt}
                        WebSocketHandler.send_updates(room.players[i + 1].token, message)
                    # Give first player last player's image
                    message = {"prompt": room.players[len(room.players) - 1].prompt}
                    WebSocketHandler.send_updates(room.players[0].token, message)

                    # Update histories
                    for i in range(len(room.players)):
                        room.histories[i].append((room.players[i].name, room.players[i].prompt))

                # Set all players unready
                for player_iter in room.players:
                    player_iter.is_ready = False

                room.current_task_is_drawing = not room.current_task_is_drawing
                room.round_count += 1
                update_dashboard(room)

                # Update histories: Right shift one
                logging.info(f"Before shifting Histories: {room.histories}")
                logging.info(f"Room is {room}")
                list_tmp = room.histories.pop()
                room.histories.insert(0, list_tmp)
                logging.info(f"After shifting Histories: {room.histories}")


# def push_history(room, event):
#     room.histories[room.round_count]

def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()

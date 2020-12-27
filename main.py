import urllib
from typing import Optional, Awaitable, Dict, List
from enum import Enum
import random
import re
import datetime
import os
import json
import os.path
import uuid
import logging
from urllib.parse import quote, unquote

import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import tornado.httpclient as httpclient
from tornado.options import define, options

define("host", default="drawphone.kumula.me", help="run on the given host", type=str)
define("port", default=8888, help="run on the given port", type=int)
define("contact-data", default="", help="path to your contact data image", type=str)


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
        self.id = str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"Player: Name: {self.name}, Prompt: {self.prompt}, Token: {self.token}, Ready: {self.is_ready}"


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
        self.prompts = []
        self.timeout = 0
        self.last_access = datetime.datetime.now()
        self.max_rounds = 0
        self.allow_history_dumps = False

    def get_new_prompt(self):
        return self.prompts.pop()

    def add_player(self, player: Player):
        self.players += [player]

    def set_presenter(self, presenter: Presenter):
        self.presenter = presenter

    def __repr__(self) -> str:
        ret = f"Timeout: {self.timeout}. Presenter: {self.presenter}. Players: "
        for p in self.players:
            ret += repr(p) + ", "
        return ret


rooms: Dict[str, Room] = {}
latest_commits: List[str] = []


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/privacy", PrivacyHandler),
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
        logging.debug(f"main GET. Request: {self.cookies}")
        logging.debug(f"Rooms: {rooms}")

        # Delete rooms which were not accessed in the last 20 minutes
        rooms_to_delete = []
        for room_id in rooms:
            if datetime.datetime.now() - rooms[room_id].last_access > datetime.timedelta(minutes=20):
                logging.info(f"Room {room_id} not accessed for at least 20 minutes (was {rooms[room_id]})")
                rooms_to_delete.append(room_id)
        for r in rooms_to_delete:
            if r in rooms:
                del rooms[r]
        logging.info(f"Current rooms are: {[r for r in rooms]}")

        # If room id supplied, create room or join it
        if len(room_id_param) == 1:
            room_id = room_id_param[0]
            new_token = str(uuid.uuid4())

            # Check if name is set correctly
            name = self.get_cookie("name")
            if name is None:
                self.render("player_setup.html", host=tornado.options.options.as_dict().get('host'))
                return
            name = unquote(quote(name, encoding='iso8859-1'), encoding='utf-8')
            logging.debug(f"Supplied name: {name}")
            name = re.sub('[^a-zA-Z0-9äöüß]', '', name)

            # If room does not exist, create it and set requester to presenter
            if room_id not in rooms:
                room = Room()
                rooms[room_id] = room
                rooms.get(room_id).set_presenter(Presenter(new_token))

            else:
                room = rooms.get(room_id)
                room.last_access = datetime.datetime.now()

                # Check if presenter just refreshed the page in pregame, otherwise they are just a player
                if room.presenter.token == self.get_cookie("token") and \
                        room.game_state is GameState.PREGAME:
                    # Add the presenter as a player again
                    room.add_player(Player(name, "", room.presenter.token))
                    self.render("game.html", host=tornado.options.options.as_dict().get('host'))
                    return

                # Check if player just refreshed the page and was not removed beforehand
                for p in room.players:
                    if p.token == self.get_cookie("token"):
                        self.render("game.html",
                                    host=tornado.options.options.as_dict().get('host'))
                        return

                # If the game is already running, skip everything else
                if room.game_state != GameState.PREGAME:
                    return

            new_player = Player(name, "", new_token)
            room.add_player(new_player)
            logging.info(f"Added player {name} with token {new_token}")

            self.set_cookie("token", new_player.token)
            self.set_cookie("id", new_player.id)
            self.render("game.html",
                        host=tornado.options.options.as_dict().get('host'))

        # Else just show intro page
        else:
            self.render("index.html", existing_rooms=[r for r in rooms],
                        host=tornado.options.options.as_dict().get("host"),
                        commits="!!DELIM!!".join(latest_commits))


def update_game_status(room: Room, extra_obj=None, token=""):
    if extra_obj is None:
        extra_obj = {}

    message = {
        "type": "presenter",
        "command": "general_update",
        "game_state": room.game_state,
        "players": [
            [[p.name, p.id] for p in room.players if p.is_ready],
            [[p.name, p.id] for p in room.players if not p.is_ready]
        ],
        "round_count": room.round_count,
        "max_rounds": room.max_rounds,
        "timeout": room.timeout
    }
    message = {**message, **extra_obj}

    if token == "":
        for p in room.players:
            WebSocketHandler.send_updates(p.token, message)
    else:
        WebSocketHandler.send_updates(token, message)


def update_current_task(room: Room, token: str, extra_obj=None):
    if extra_obj is None:
        extra_obj = {}

    message = {
        "type": "game",
        "command": "show_task",
        "timeout": room.timeout
    }
    message = { **message, **extra_obj}
    WebSocketHandler.send_updates(token, message)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    token: str = ""
    global rooms

    def check_origin(self, origin: str) -> bool:
        parsed_origin = urllib.parse.urlparse(origin)
        return parsed_origin.netloc.endswith(tornado.options.options.as_dict().get('host'))

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def open(self):
        self.token = self.get_cookie("token")
        WebSocketHandler.waiters.add(self)

    def on_close(self):
        WebSocketHandler.waiters.remove(self)


    @classmethod
    def send_updates(cls, token: str, message):
        for waiter in cls.waiters:
            try:
                logging.debug(f"Send message {message} with {token} to {waiter.token}? {token == waiter.token}")
                if token == waiter.token:
                    waiter.write_message(message)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):
        logging.debug("got message %r", message)
        parsed = tornado.escape.json_decode(message)

        if "room_id" not in parsed or parsed["room_id"] not in rooms:
            logging.info("Room not found")
            return
        room = rooms.get(parsed["room_id"])
        room.last_access = datetime.datetime.now()

        if room.presenter.token == parsed["token"] and room.game_state is GameState.PREGAME:
            if parsed["command"] == "reconnect_check":
                message = {"command": "show_settings"}
                update_game_status(room, message, room.presenter.token)

            elif parsed["command"] == "kick_player":
                for p in room.players:
                    if p.id == parsed["id"]:
                        logging.info(f"Removing player {p}")
                        room.players.remove(p)
                        update_game_status(room, {"command": "kicked"}, p.token)

                message = {"command": "show_settings"}
                update_game_status(room, message, room.presenter.token)

            elif parsed["command"] == "start_game":
                # Shuffle players
                random.shuffle(room.players)

                # Set timeout
                if not parsed["timeout"] == "":
                    try:
                        timeout = int(parsed["timeout"])
                        if timeout >= 0:
                            room.timeout = int(parsed["timeout"])
                    except:
                        pass

                # Set max amount of rounds
                room.max_rounds = len(room.players)

                if not parsed["round_count"] == "":
                    try:
                        rounds = int(parsed["round_count"])
                        logging.info(f"provided rounds: {rounds}")
                        if 2 <= rounds <= len(room.players):
                            room.max_rounds = rounds
                    except:
                        pass

                logging.info(f"Room max count is {room.max_rounds}")

                # Load wordlist
                # Set default first
                load_wordlist_from_file(room, "simple.txt")

                try:
                    wordlist_chosen = parsed["wordlist_chosen"]
                    logging.info(f"Chosen word list: {wordlist_chosen}")

                    if wordlist_chosen == "advanced":
                        load_wordlist_from_file(room, "advanced.txt")

                    elif wordlist_chosen == "custom":
                        words_unparsed = str(parsed["custom_words"])
                        words = []
                        for w in words_unparsed.split(","):
                            words.append(re.sub('[^a-zA-Z0-9 \'"äöüß]', '', w.strip()))

                        logging.debug(f"Words: {words}")

                        if len(words) >= len(room.players):
                            room.prompts = words
                except:
                    pass

                logging.debug(f"Words loaded: {room.prompts}")

                # Check if history logging allowed
                try:
                    room.allow_history_dumps = bool(parsed["allow_history_logging"])
                except:
                    pass
                logging.info(f"History logging allowed: {room.allow_history_dumps}")

                random.shuffle(room.prompts)

                # Setup ready

                # Should players draw first, or supply a prompt?
                if room.max_rounds % 2 == 0:
                    room.current_task_is_drawing = True
                    for p in room.players:
                        p.prompt = room.get_new_prompt()
                        message = {"prompt": p.prompt}
                        update_current_task(room, p.token, message)

                        # Create histories
                        room.histories.append([("Computer", p.prompt)])
                else:
                    room.current_task_is_drawing = False
                    for p in room.players:
                        p.prompt = room.get_new_prompt()
                        message = {"computer_supplied_prompt": p.prompt}
                        update_current_task(room, p.token, message)

                        # Create histories
                        room.histories.append([])

                room.game_state = GameState.PLAYING
                update_game_status(room)
                logging.debug(f"Histories: {room.histories}")
                logging.info(f"Room: {room}")
                return

        # Check if a player sent a message
        player = None
        player_pos = -1
        for i in range(len(room.players)):
            p = room.players[i]
            if parsed["token"] == p.token:
                player = p
                player_pos = i

        if player is None:
            logging.info("Player not found")
            return

        if room.game_state is GameState.PREGAME:
            if "command" in parsed:
                if parsed["command"] == "leave_game":
                    del room.players[player_pos]

                update_game_status(room, {"command": "show_pregame"})

        elif room.game_state is GameState.PLAYING:
            # Check if someone refreshes the page, give them the current game state
            if "command" in parsed:
                if parsed["command"] == "reconnect_check":
                    logging.info(f"Player wants to reconnect: {player}")
                    if not player.is_ready:
                        if room.current_task_is_drawing:
                            message = {"prompt": player.prompt}
                        else:
                            # Check if it's the first round, i.e. players supply first prompts
                            if room.round_count == 1:
                                message = {"computer_supplied_prompt": player.prompt}
                            else:
                                message = {"image": player.image}
                        update_current_task(room, player.token, message)

                update_game_status(room)

                # Ignore other commands
                return

            # Last round if round threshold reached
            logging.info(f"Room count: {room.round_count} of {room.max_rounds}")
            if room.round_count >= room.max_rounds:
                logging.info("Round count reached")
                # Get last prompt
                player.prompt = parsed["prompt"]
                player.is_ready = True

                # Update UI
                update_game_status(room)

                for p in room.players:
                    if not p.is_ready:
                        return

                # Update histories
                for i in range(len(room.players)):
                    room.histories[i].append((room.players[i].name, room.players[i].prompt))

                room.game_state = GameState.POSTGAME

                # As histories can be very large, some extra logic to sync clients …
                for p in room.players:
                    p.is_ready = False

                message = {
                    "command": "prepare_receiving_histories"
                }
                update_game_status(room, message)

                message = {
                    "command": "update_histories",
                    "histories": room.histories
                }
                update_game_status(room, message)

                if room.allow_history_dumps:
                    dump_histories_to_file(room.histories)

                return

            elif room.current_task_is_drawing:
                player.image = parsed["image"]
                player.is_ready = True

                # Update UI
                update_game_status(room)

                for p in room.players:
                    if not p.is_ready:
                        return

                # All players ready

                # Update histories
                for i in range(len(room.players)):
                    room.histories[i].append((room.players[i].name, room.players[i].image))

                # Give next player the image
                tmp_image = room.players[len(room.players) - 1].image

                for i in range(len(room.players) - 1, 0, -1):
                    room.players[i].image = room.players[i-1].image

                # Give first player last player's image
                room.players[0].image = tmp_image

                # Send updates
                for i in range(len(room.players)):
                    message = {"image": room.players[i].image}
                    update_current_task(room, room.players[i].token, message)

            else:
                player.prompt = parsed["prompt"]
                player.is_ready = True

                # Update UI
                update_game_status(room)

                for p in room.players:
                    if not p.is_ready:
                        return

                # All players ready

                logging.debug(room.histories)
                logging.debug(room.players)
                # Update histories
                for i in range(len(room.players)):
                    logging.debug(f"Adding {room.players[i]}")
                    room.histories[i].append((room.players[i].name, room.players[i].prompt))

                # Give next player the prompt
                tmp_prompt = room.players[len(room.players) - 1].prompt

                for i in range(len(room.players) - 1, 0, -1):
                    room.players[i].prompt = room.players[i-1].prompt

                # Give first player last player's prompt
                room.players[0].prompt = tmp_prompt

                # Send updates
                for i in range(len(room.players)):
                    message = {"prompt": room.players[i].prompt}
                    update_current_task(room, room.players[i].token, message)

            # Set all players unready
            for p in room.players:
                p.is_ready = False

            room.current_task_is_drawing = not room.current_task_is_drawing
            room.round_count += 1
            update_game_status(room)

            # Update histories: Right shift one
            logging.debug(f"Before shifting Histories: {room.histories}")
            list_tmp = room.histories.pop()
            room.histories.insert(0, list_tmp)
            logging.debug(f"After shifting Histories: {room.histories}")

        elif room.game_state is GameState.POSTGAME:
            if parsed["command"] == "history_received":
                player.is_ready = True
                for p in room.players:
                    if not p.is_ready:
                        return

                # All players ready
                # Try to sync clients …
                message = {
                    "command": "show_histories"
                }
                update_game_status(room, message)

            elif parsed["command"] == "start_new_game":
                message = {"command": "reload"}
                update_game_status(room, message)
                logging.info(f"Reloading game with room_id {parsed['room_id']}")
                del rooms[parsed["room_id"]]


class PrivacyHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("privacy.html", contact_image=tornado.options.options.as_dict().get('contact-data'))


def load_wordlist_from_file(room: Room, file_name: str):
    room.prompts = []
    with open("words/" + file_name) as f:
        for line in f:
            room.prompts.append(line.strip())


def dump_histories_to_file(histories):
    if not os.path.exists('history_dumps'):
        os.makedirs('history_dumps')

    filename = "history_dumps/" + \
               str(datetime.datetime.now()).replace(" ", "_").replace(":", "-") + ".txt"
    with open(filename, "x") as f:
        f.write(json.dumps(histories))


def main():
    tornado.options.parse_command_line()

    get_latest_commits()

    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


def get_latest_commits():
    global latest_commits

    http_client = httpclient.HTTPClient()
    try:
        response = http_client.fetch("https://api.github.com/repos/2xlink/DrawPhone/events")
        parsed = json.loads(response.body)
    except Exception as e:
        # Other errors are possible, such as IOError.
        logging.warning("Error: " + str(e))
        parsed = []

    http_client.close()

    i = 0
    for event in parsed:
        if event["type"] != "PushEvent":
            continue

        commits = event["payload"]["commits"]
        commits.reverse()

        for c in commits:
            latest_commits.append(c["message"])
            i += 1

        if i >= 6:
            break

    latest_commits = \
        ["Forms can now be sent with the return key",
         "Adds rename and kick functions",
         "(Hopefully) fixed history sync"]
    logging.debug(f"Got latest commits: {latest_commits}")


if __name__ == "__main__":
    main()

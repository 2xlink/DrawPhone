var vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0)
vw = Math.min(vw, 400) - 20

const post_game_display_delay = 2000

var sketchpad1
var sketchpad2
var prompt_input
var body
var timeout
var timeout_counter
var timeout_function
var timeout_has_started = false
var body
var is_busy = false // Set when the player needs to do something before showing other stuff
var is_presenter = false

var div_presenter_pre_game = document.getElementById("div_presenter_pre_game")
var div_presenter_settings = document.getElementById("div_presenter_settings")
var div_presenter_pre_game_title = document.getElementById("div_presenter_pre_game_title")
var div_presenter_pre_game_player_list = document.getElementById("div_presenter_pre_game_player_list")
var copy_room = document.getElementById("copy_room")
var timeout_input = document.getElementById("timeout_input")
var rounds_input = document.getElementById("rounds_input")
var wordlist_dropdown = document.getElementById("wordlist_dropdown")
var custom_wordlist_div = document.getElementById("custom_wordlist_div")
var custom_wordlist = document.getElementById("custom_wordlist")
var logging_input = document.getElementById("logging_input")
var start_button = document.getElementById("start_button")
var div_presenter_playing = document.getElementById("div_presenter_playing")
var div_presenter_playing_title = document.getElementById("div_presenter_playing_title")
var div_presenter_playing_player_list_ready = document.getElementById("div_presenter_playing_player_list_ready")
var div_presenter_playing_player_list_not_ready = document.getElementById("div_presenter_playing_player_list_not_ready")
var div_timeout_counter = document.getElementById("div_timeout_counter")
var div_presenter_post_game = document.getElementById("div_presenter_post_game")
var div_history = document.getElementById("history")
var button_export_history = document.getElementById("button_export_history")
var button_start_new_game = document.getElementById("button_start_new_game")
var div_draw = document.getElementById("div_draw")
var prompt_supplied = document.getElementById("prompt_supplied")
var sketchpad_input_root = document.getElementById("sketchpad_input_root")
var sketchpad_input = document.getElementById("sketchpad_input")
var button_send_image = document.getElementById("button_send_image")
var div_prompt = document.getElementById("div_prompt")
var sketchpad_supplied = document.getElementById("sketchpad_supplied")
var prompt_input = document.getElementById("prompt_input")
var button_send_prompt = document.getElementById("button_send_prompt")
var div_submit_first_prompt = document.getElementById("div_submit_first_prompt")
var input_first_prompt = document.getElementById("input_first_prompt")
var button_send_first_prompt = document.getElementById("button_send_first_prompt")
var div_presenter_pregame_waiting = document.getElementById("presenter_pregame_waiting")
var div_loader = document.getElementById("div_loader")
var div_rounds_hint = document.getElementById("div_rounds_hint")
var choice_task_draw = document.getElementById("choice_task_draw")
var choice_task_prompt = document.getElementById("choice_task_prompt")
var choice_task_custom = document.getElementById("choice_task_custom")
var color_buttons = document.querySelectorAll(".color_button[data-color]")
var stroke_size_buttons = document.querySelectorAll(".color_button[data-stroke-size]")

body = document.body
body.style.width = vw + "px"

var ws
if (window.location.protocol == "https:") {
    ws = new WebSocket("wss://" + hostname + "/websocket");
} else {
    ws = new WebSocket("ws://" + hostname + "/websocket");
}

var timeout_started = false

ws.onopen = function() {
    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "command": "reconnect_check"
    }
    ws.send(JSON.stringify(ret))
};

function show_player_list() {
    data["players"][0].forEach(p => {
        d = document.createElement("div")
        d.classList.add("player", "minor_text_element")
        d.innerText = p[0]
        div_presenter_playing_player_list_ready.appendChild(d)
    })

    data["players"][1].forEach(p => {
        d = document.createElement("div")
        d.classList.add("player", "minor_text_element")
        d.innerText = p[0]
        div_presenter_playing_player_list_not_ready.appendChild(d)
    })

    div_presenter_playing_title.innerText =
        "Round " + data["round_count"] + " of " + data["max_rounds"]
}

function show_pregame_player_list() {
    div_presenter_pre_game_player_list.innerHTML = ""
    data["players"][1].forEach(p => {
        d = document.createElement("div")
        d.classList.add("player", "text_element")

        d.innerText = p[0]

        if (is_presenter && p[1] != getCookie("id")) {
            e = document.createElement("div")
            e.classList.add("fa", "fa-times", "list_button", "button_kick")
            e.addEventListener("click", function() {
                console.log("Kick player " + p)
                ret = {
                    "token": getCookie("token"),
                    "room_id": findGetParameter("room_id"),
                    "command": "kick_player",
                    "id": p[1]
                }
                ws.send(JSON.stringify(ret))
            });

            d.appendChild(e)
        }

        if (p[1] == getCookie("id")) {
            e = document.createElement("div")
            e.classList.add("fas", "fa-pen", "list_button", "button_edit")
            e.addEventListener("click", function() {
                console.log("Rename player " + p)
                deleteCookie("name")
                location.reload()
            });
        }
        else {
            if (!is_presenter) {
                e = document.createElement("div")
                e.classList.add("list_button")
            }
        }
        d.appendChild(e)

        div_presenter_pre_game_player_list.appendChild(d)
    })

    // Update title
    div_presenter_pre_game_title.innerText =
        "Connected Players (" + data["players"][1].length + ")"
}

function update_rounds_hint() {
    if (rounds_input.value != "") {
        player_count = rounds_input.value
    } else {
        player_count = rounds_input.placeholder
    }

    try {
        if (player_count % 2 == 0) {
            div_rounds_hint.innerText = "Players will draw first"
        }
        else {
            div_rounds_hint.innerText = "Players will supply prompts first"
        }
    }
    catch(err) { }
}

ws.onmessage = function (evt) {
    console.log(evt.data);
    data = JSON.parse(evt.data)
    command = data["command"]

    if (command == "show_settings") {
        is_busy = true
        div_presenter_pre_game.style.display = "block"
        div_presenter_settings.style.display = "block"
        start_button.style.display = "initial"
        presenter_pregame_waiting.style.display = "none"
        is_presenter = true
        show_pregame_player_list()
    }
    else if (command == "show_pregame") {
        div_presenter_pre_game.style.display = "block"
        show_pregame_player_list()
        start_button.disabled = data["players"][1].length < 2
        rounds_input.placeholder = data["players"][1].length
        update_rounds_hint()
    }
    else if (command == "general_update" && !is_busy) {
        div_presenter_pre_game.style.display = "none"
        div_presenter_playing.style.display = "unset"

        div_presenter_playing_player_list_ready.innerHTML = ""
        div_presenter_playing_player_list_not_ready.innerHTML = ""

        // if it is the first round and players should input the prompt, hide timeout
        if (data["round_count"] == 1 && data["max_rounds"] % 2 == 1) {
            div_timeout_counter.style.display = "none"
        }
        show_player_list()
    }
    else if (command == "prepare_receiving_histories") {
        div_loader.style.display = "block"
        div_presenter_playing.style.display = "none"
    }
    else if (command == "update_histories") {
        histories = data["histories"]

        ret = {
            "token": getCookie("token"),
            "room_id": findGetParameter("room_id"),
            "command": "history_received"
        }
        ws.send(JSON.stringify(ret))
    }
    else if (command == "show_histories") {
        div_loader.style.display = "none"
        div_presenter_post_game.style.display = "unset"
        show_histories(histories)
    }

    else if (command == "reload") {
//        ws.close()
//        if (data["command"] == "reload") {
//            setTimeout(_ => location.reload(), 2000)
//        }
    }

    else if (command == "kicked") {
        location = "/"
    }

    // game update
    else if (command == "show_task") {
        is_busy = true
        div_presenter_pre_game.style.display = "none"
        div_presenter_playing.style.display = "none"
        div_draw.style.display = "none"
        div_prompt.style.display = "none"

        // If prompt has timeout, set it and start visual countdown
        if ("timeout" in data) {
            timeout = data["timeout"] * 1000
            timeout_counter = timeout / 1000

            button_send_prompt.classList.remove("button_flashing")
            button_send_image.classList.remove("button_flashing")

            if (timeout != 0) {
                f = async function() {
                    while(true) {
                        timeout_counter -= 1
                        if (timeout_counter < 0) timeout_counter = 0

                        button_send_prompt.innerText = "Send - " + timeout_counter + " seconds remaining!"
                        button_send_image.innerText = "Send - " + timeout_counter + " seconds remaining!"
                        div_timeout_counter.innerText = timeout_counter + " seconds remaining!"

                        if (timeout_counter == 10) {
                            button_send_prompt.classList.add("button_flashing")
                            button_send_image.classList.add("button_flashing")
                        }

                        await sleep(1000)
                    }
                }

                div_timeout_counter.style.display = "block"

                if (!timeout_has_started) {
                    timeout_has_started = true
                    f()
                }
            }
        }

        if ("prompt" in data) {
            div_draw.style.display = "unset"
            prompt_supplied.innerText = data["prompt"]

            button_send_image.disabled = true
            setTimeout(() => {
                button_send_image.disabled = false
            }, 3000)

            if (timeout != 0) {
                console.log("Setting drawing timeout to " + timeout)
                timeout_function = setTimeout(() => sendImage(), timeout)
                timeout_counter = timeout / 1000
            }
        }
        else if ("image" in data) {
            div_prompt.style.display = "unset"
            settings = data["image"]
            settings.element = sketchpad_supplied
            supplied_vw = settings.width
            scale_factor = vw / supplied_vw

            // Scale drawn thing to our vw
            settings.strokes.forEach(stroke => {
                stroke.lines.forEach(line => {
                    line.start.x = scale_factor * line.start.x
                    line.start.y = scale_factor * line.start.y
                    line.end.x = scale_factor * line.end.x
                    line.end.y = scale_factor * line.end.y
                })
            })

            settings.width = vw
            settings.height = vw
            sketchpad2 = new Sketchpad(settings)

            if (timeout != 0) {
                console.log("Setting prompt timeout to " + timeout)
                timeout_function = setTimeout(() => sendPrompt(), timeout)
                timeout_counter = timeout / 1000
            }
        }
        else if ("computer_supplied_prompt" in data) {
            div_submit_first_prompt.style.display = "unset"
            computer_supplied_prompt = data["computer_supplied_prompt"]
        }
    }
}

window.addEventListener("beforeunload",function(event) {
        ret = {
            "token": getCookie("token"),
            "room_id": findGetParameter("room_id"),
            "command": "leave_game"
        }
        ws.send(JSON.stringify(ret))
    })

function setup_client() {
    timeout = getCookie("timeout")
    round_count = getCookie("round_count")
    wordlist_chosen = getCookie("wordlist_chosen")
    custom_words = getCookie("custom_words")
    allow_history_logging = getCookie("allow_history_logging") == null?
        true : getCookie("allow_history_logging") == "true"

    if (wordlist_chosen == null) {
        wordlist_chosen = "default"
    }
    chosen_first_task = getCookie("chosen_first_task")

    try {
        timeout_input.value = timeout
        rounds_input.value = round_count
        wordlist_dropdown.value = wordlist_chosen
        wordlist_change(); // Update UI
        custom_wordlist.value = custom_words
        logging_input.checked = allow_history_logging

        if (chosen_first_task == null) chosen_first_task = 2
        choice_task_draw.checked = chosen_first_task == 0
        choice_task_prompt.checked = chosen_first_task == 1
        choice_task_custom.checked = chosen_first_task == 2
    }
    catch(err) { }

    sketchpad1 = new Sketchpad({
      element: '#sketchpad_input',
      width: vw,
      height: vw
    });

    Array.from(color_buttons).forEach(colorButton => {
        const color = colorButton.dataset.color;
        colorButton.style.backgroundColor = "#" + color;
    });

    const initialColorButton = document.querySelector(".color_button[data-color='" + sketchpad1.color.substring(1) + "']");
    const initialStrokeSizeButton = document.querySelector(".color_button[data-stroke-size='" + sketchpad1.penSize + "']");

    initialColorButton.classList.add("focus");
    initialStrokeSizeButton.classList.add("focus");
}

function sendImage() {
    is_busy = false
    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "image": sketchpad1.toObject()
//        "image": sketchpad_input.toDataURL()
    }
    ws.send(JSON.stringify(ret))

    div_draw.style.display = "none"

    // Clearing is broken, as previous strokes seem to be drawn on top
    // Clear sketchpad, remove the canvas and add it anew
    sketchpad1.canvas.remove()
    new_canvas = document.createElement("canvas")
    new_canvas.classList.add("sketchpad")
    new_canvas.id = "sketchpad_input"
    sketchpad_input_root.appendChild(new_canvas)

    sketchpad1 = new Sketchpad({
      element: '#sketchpad_input',
      width: vw,
      height: vw
    });

    if (typeof timeout_function !== undefined) {
        clearTimeout(timeout_function);
    }
}

function sendPrompt() {
    is_busy = false
    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "prompt": prompt_input.value
    }
    ws.send(JSON.stringify(ret))

    div_prompt.style.display = "none"

    prompt_input.value = ""
    // sketchpad2.clear()

    if (typeof timeout_function !== undefined) {
        clearTimeout(timeout_function);
    }

    button_send_prompt.disabled = true
}

function checkSubmit(e, fun) {
    if(e && e.keyCode == 13) {
        fun()
    }
}

function sendFirstPrompt(chose_computer_supplied) {
    is_busy = false
    if (chose_computer_supplied) {
        prompt = computer_supplied_prompt
    }
    else {
        prompt = input_first_prompt.value
    }

    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "prompt": prompt
    }
    ws.send(JSON.stringify(ret))

    div_submit_first_prompt.style.display = "none"

    button_send_first_prompt.disabled = true
    input_first_prompt.value = ""
}

function change_stroke_color(element) {
    const color = element.dataset.color;

    update_button_focus(element, color_buttons);

    sketchpad1.color = '#' + color
}

function change_stroke_size(element) {
    const size = element.dataset.strokeSize;

    update_button_focus(element, stroke_size_buttons);

    sketchpad1.penSize = size
}

function update_button_focus(element, siblings) {
    Array.from(siblings).forEach(sibling => {
        sibling.classList.remove("focus");
    })

    element.classList.add("focus");
}

show_histories = async function(histories) {
    await sleep(post_game_display_delay)
//    console.log(histories)

    for (i1 = 0; i1 < histories.length; i1++) {
        hist = histories[i1]

        for (i2 = 0; i2 < hist.length; i2++) {
            event_tuple = hist[i2]

            player_name = event_tuple[0]
            event = event_tuple[1]

            if (typeof event === "string") {
                e = document.createElement("div")
                e.innerText = player_name + ': "' + event + '"'
                e.classList.add("fade_in", "minor_text_element")

                event_tmp = event
                f = document.createElement("div");
                f.classList.add("far", "fa-heart", "list_button", "button_like");
                (function(prompt, elem) {
                    f.onclick = function() {
                        console.log("Like prompt " + prompt)
                        elem.classList.remove("far")
                        elem.classList.add("fas")
                        elem.style.color = "red"
                        elem.onclick = function() {}

                        ret = {
                            "token": getCookie("token"),
                            "room_id": findGetParameter("room_id"),
                            "command": "like_prompt",
                            "prompt": prompt
                        }
                        ws.send(JSON.stringify(ret))
                    }
                })(event, f);
                e.appendChild(f)

                div_history.appendChild(e)
                e.scrollIntoView({ behavior: 'smooth' })
            }
            else {
                d = document.createElement("div")
                d.innerText = player_name + " drew the following"

                e = document.createElement("canvas")
                e.classList.add("sketchpad")
                e.classList.add("sketchpad_nopointer")

                d.classList.add("fade_in", "minor_text_element")
                e.classList.add("fade_in", "sketchpad")
                div_history.appendChild(d)
                div_history.appendChild(e)

                settings = event
                settings.element = e
                supplied_vw = settings.width
                scale_factor = vw / supplied_vw

                // Scale drawn thing to our vw
                settings.strokes.forEach(stroke => {
                    stroke.lines.forEach(line => {
                        line.start.x = scale_factor * line.start.x
                        line.start.y = scale_factor * line.start.y
                        line.end.x = scale_factor * line.end.x
                        line.end.y = scale_factor * line.end.y
                    })
                })

                settings.width = vw
                settings.height = vw
                var sketchpad = new Sketchpad(settings)
//                sketchpad.animate(1)

                e.scrollIntoView({ behavior: 'smooth' })

                await sleep(post_game_display_delay)
            }

            await sleep(post_game_display_delay)
        }

        d = document.createElement("div")
        d.innerText = '"' + hist[0][1] + '" => "' + hist[hist.length-1][1] + '"'
        d.classList.add("fade_in", "text_element")
        div_history.appendChild(d)
        d.scrollIntoView({ behavior: 'smooth' })

        await sleep(post_game_display_delay * 2)
    }

    button_export_history.style.display = "initial"
    button_start_new_game.style.display = "initial"
    button_start_new_game.scrollIntoView({ behavior: 'smooth' })
}

function startGame() {
    timeout = timeout_input.value
    round_count = rounds_input.value
    wordlist_chosen = wordlist_dropdown.value
    custom_words = custom_wordlist.value
    allow_history_logging = logging_input.checked
    if (choice_task_draw.checked) {
        chosen_first_task = 0
    }
    else if (choice_task_prompt.checked) {
        chosen_first_task = 1
    }
    else { // choice_task_custom
        chosen_first_task = 2
    }

    document.cookie = "timeout=" + timeout
    document.cookie = "round_count=" + round_count
    document.cookie = "wordlist_chosen=" + wordlist_chosen
    document.cookie = "custom_words=" + custom_words
    document.cookie = "allow_history_logging=" + allow_history_logging
    document.cookie = "chosen_first_task=" + chosen_first_task

    if (chosen_first_task == 1) {
        round_count = Math.floor((data["players"][1].length - 1) / 2) * 2 + 1
    }
    else if (chosen_first_task == 0) {
        round_count = Math.floor((data["players"][1].length) / 2) * 2
    }

    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "command": "start_game",
        "timeout": timeout,
        "round_count": round_count,
        "wordlist_chosen": wordlist_chosen,
        "custom_words": custom_words,
        "allow_history_logging": allow_history_logging
    }
    ws.send(JSON.stringify(ret))
}

function start_new_game() {
    ret = {
        "token": getCookie("token"),
        "room_id": findGetParameter("room_id"),
        "command": "start_new_game"
    }
    ws.send(JSON.stringify(ret))
    button_start_new_game.disabled = true
    setTimeout(_ => location.reload(), 500)
}

function export_history() {
    html2canvas(document.body, {
      onrendered: function(canvas)
      {
        var today = new Date();
        var date = today.getFullYear()+'-'+(today.getMonth()+1)+'-'+today.getDate();
        date += " " + today.getHours() + "-" + today.getMinutes()

        canvas.toBlob(function(blob) {
          saveAs(blob, "Drawphone " + date + ".png");
        });
      }
    });
    return false;
}

function copy_room_to_clipboard() {
    fallbackCopyTextToClipboard(window.location)
    copy_room.innerText = "Copied!"
}

function wordlist_change() {
    if (wordlist_dropdown.value == "custom") {
        custom_wordlist_div.style.display = "block"
    }
    else {
        custom_wordlist_div.style.display = "none"
    }
}

setup_client()
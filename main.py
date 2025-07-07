import asyncio
import pygame
import json
from io import BytesIO
from PIL import Image
import platform 

# Load initial selection menu
async def load_url_json(url):
    async with platform.fopen(url, "r", encoding="utf-8") as f:
        selection_menu = json.load(f)

    return selection_menu

#Pygame initialisation stuff

SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
BASE_WIDTH, BASE_HEIGHT = 1920, 1080  
scale_x = SCREEN_WIDTH / BASE_WIDTH
scale_y = SCREEN_HEIGHT / BASE_HEIGHT
#This scale would need to change if using different aspect ratios probably
CHAR_SCALE_RATIO = 0.8

# --- Pygame Init ---
pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Victory Belles Conversation Reader")
font_size = max(12, int(28 * scale_y))
font = pygame.font.SysFont("Arial", font_size) #Maybe this font should be changed
clock = pygame.time.Clock()

# --- Game State Variables ---
menu_state = "country"  # country, character, category, file
selected_country_idx = 0
selected_character_idx = 0
selected_category_idx = 0
selected_file_idx = 0

selecting_convo = True
current_convo_id = None
current_node_id = None
dialog_nodes = None
bg_image = None
char_img = None
selection_menu = None
actor_name = ""
dialogue = ""
typing_speed = 30  # chars per second
node_start_time = 0
displayed_text = ""
choice_mode = False
choices = []
choice_rects = []
convo_buttons = []
selected_convo_idx = 0
scroll_offset = 0
max_scroll = 0

prev_actor_id = None
selected_actor_images = {}
json_path = None
actors = {}
locations = {}
conversations = []
convo_map = {}
captain_actor_id = None
current_char_img = None
muted = False
volume = 0.5
now = 0

#To prevent closing due to multiple presses occuring quickly, or single press being registered multiple times for whatever reason 
#Not too sure this is an issue but just in case
last_menu_escape_time = 0
ESCAPE_COOLDOWN = 0.3

# --- Helper Functions ---
def get_current_list():
    if menu_state == "country":
        return [c["name"] for c in selection_menu]
    elif menu_state == "character":
        country = selection_menu[selected_country_idx]
        return [ch["name"] for ch in country["characters"]]
    elif menu_state == "category":
        country = selection_menu[selected_country_idx]
        character = country["characters"][selected_character_idx]
        return [cat["name"] for cat in character["categories"]]
    elif menu_state == "file":
        country = selection_menu[selected_country_idx]
        character = country["characters"][selected_character_idx]
        category = character["categories"][selected_category_idx]
        return category["files"]
    return []
    
def auto_scroll_to_selection(target_y):
    global scroll_offset, max_scroll
    visible_start = int(130 * scale_y)
    visible_end = SCREEN_HEIGHT - int(100 * scale_y)
    
    if target_y - scroll_offset > visible_end:
        scroll_offset = min(max_scroll, target_y - visible_end)
    elif target_y - scroll_offset < visible_start:
        scroll_offset = max(0, target_y - visible_start)
        
def draw_menu():
    global max_scroll
    screen.fill((0, 0, 0))
    title_text = f"Select {menu_state.capitalize()}"
    title_surf = font.render(title_text, True, (255, 255, 255))
    title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, int(60 * scale_y)))
    screen.blit(title_surf, title_rect)

    items = get_current_list()
    btn_width = SCREEN_WIDTH - 100
    btn_height = int(50 * scale_y)
    spacing = int(10 * scale_y)
    start_y = int(120 * scale_y)

    selected_idx = {
        "country": selected_country_idx,
        "character": selected_character_idx,
        "category": selected_category_idx,
        "file": selected_file_idx
    }[menu_state]

    total_height = len(items) * (btn_height + spacing)
    max_scroll = max(0, total_height - (SCREEN_HEIGHT - start_y))

    for i, item in enumerate(items):
        y = start_y + i * (btn_height + spacing) - scroll_offset
        if -btn_height < y < SCREEN_HEIGHT:
            rect = pygame.Rect(50, y, btn_width, btn_height)
            draw_button(item, rect, (i == selected_idx))

    pygame.display.flip()


async def load_image(url):
    async with platform.fopen(url, "rb") as datafile:
        image_data = datafile.read()
        pil_image = Image.open(BytesIO(image_data))
        
        # Convert to Pygame surface
        mode = pil_image.mode
        size = pil_image.size
        data = pil_image.tobytes()
        
        if mode == "RGB":
            pygame_image = pygame.image.fromstring(data, size, "RGB")
        elif mode == "RGBA":
            pygame_image = pygame.image.fromstring(data, size, "RGBA")
        else:
            pil_image = pil_image.convert("RGB")
            data = pil_image.tobytes()
            pygame_image = pygame.image.fromstring(data, size, "RGB")
    
    return pygame_image


def draw_text_wrapped(text, x, y, max_width, line_height):
    words = text.split(' ')
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)

    for i, line in enumerate(lines):
        img = font.render(line.strip(), True, (255, 255, 255))
        screen.blit(img, (x, y + i * line_height))

def draw_button(text, rect, selected=False):
    color_bg = (70, 70, 70) if not selected else (100, 100, 150)
    color_text = (255, 255, 255)
    pygame.draw.rect(screen, color_bg, rect, border_radius=int(8 * scale_x))
    img = font.render(text, True, color_text)
    img_rect = img.get_rect(center=rect.center)
    screen.blit(img, img_rect)

def point_in_rect(point, rect):
    x, y = point
    return rect.left <= x <= rect.right and rect.top <= y <= rect.bottom


def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    lines.append(current_line.strip())
    return lines



#Conversation button sizes and drawing offsets
def prepare_convo_buttons():
    global convo_buttons, max_scroll
    convo_buttons.clear()
    btn_width = int((BASE_WIDTH - 100) * scale_x)
    btn_height = int(38 * scale_y)
    spacing = int(12 * scale_y)
    start_y = int(130 * scale_y)
    total_height = 0
    
    for i, convo in enumerate(conversations):
        y_pos = start_y + i * (btn_height + spacing)
        rect = pygame.Rect(int(50 * scale_x), y_pos, btn_width, btn_height)
        title = convo["Fields"].get("Title", f"Conversation {convo['ID']}")
        convo_buttons.append((rect, title, convo["ID"]))
        total_height = y_pos + btn_height

    visible_area_height = SCREEN_HEIGHT - start_y
    max_scroll = max(0, total_height - visible_area_height)

#Conversation loop - load background and sound for selected conversation and start with 1st dialog node
async def load_conversation(convo_id):
    global current_convo_id, dialog_nodes, bg_image, char_img, prev_actor_id
    global current_sound, sound_channel
    
    current_convo_id = convo_id
    conversation = convo_map[convo_id]
    dialog_nodes = {node["ID"]: node for node in conversation["DialogNodes"]}
    prev_actor_id = None
    char_img = None

    loc_id = conversation["Fields"].get("Location")
    if loc_id and loc_id in locations:
        base_url = 'https://raw.githubusercontent.com/Misekato/VB_Assets/refs/heads/main/Background/'
        url = base_url + locations[loc_id]["Image"]
        bg_image = await load_image(url)
        
        # Load and play corresponding sound file in loop
        if bg_image:
            loc_image = locations[loc_id]["Image"]
            sound_path = os.path.join("Sounds", os.path.splitext(loc_image)[0] + "_sfx.wav")
            if os.path.exists(sound_path):
                try:
                    pygame.mixer.music.load(sound_path)
                    pygame.mixer.music.play(loops=-1) #-1 is for looping infinite times (guessing)
                except Exception as e:
                    print(f"Failed to load sound: {sound_path} - {str(e)}")
                    current_sound = None
    return bg_image

#load each of the text nodes loop
async def load_node(node_id):
    global current_node_id, char_img, actor_name, dialogue, node_start_time
    global choice_mode, choices, choice_rects, prev_actor_id, current_char_img

    current_node_id = node_id
    choice_mode = False
    choices.clear()
    choice_rects.clear()

    node = dialog_nodes[node_id]
    fields = node["Fields"]
    actor_id = fields.get("Actor")
    actor_fields = actors.get(actor_id, {})
    actor_name = actor_fields.get("Name", "")
    actor_num = actor_fields.get("BelleID", "")
    actor_image = actor_fields.get("Image", "")
    dialogue_text = fields.get("DialogueText") or fields.get("MenuText") or ""
    
    node_start_time = pygame.time.get_ticks() / 1000
    dialogue = dialogue_text
    displayed_text = ""

    if dialogue_text.strip() == "@BATTLE":
        links = node.get("OutgoingLinks", [])
        if links:
            await load_node(links[0]["DestinationDialogID"])
            return
        else:
            reset_conversation_state()
            selecting_convo = True
            return

    dialogue = dialogue_text

    #Don't change sprite if person talking is captain - since there is none? Maybe should allow selection
    if actor_id != captain_actor_id:
        if not actor_image and actor_num and int(actor_num) > 0:
            actor_image = selected_actor_images.get(str(actor_num), "")

        if actor_num > 0:
            base_url = 'https://raw.githubusercontent.com/Misekato/VB_Assets/refs/heads/main/Character/'
            url = base_url + str(actor_num) + '_big.png'
            temp_img = await load_image(url)
            if temp_img:
                orig_width, orig_height = temp_img.get_size()
                new_width = int(SCREEN_WIDTH * CHAR_SCALE_RATIO)
                new_height = int(orig_height * (new_width / orig_width))
                temp_img = pygame.transform.smoothscale(temp_img, (new_width, new_height))
                char_img = temp_img
                current_char_img = char_img
            elif current_char_img:
                char_img = current_char_img
            else:
                char_img = None
                current_char_img = None
        prev_actor_id = actor_id

    links = node.get("OutgoingLinks", [])
    if len(links) > 1:
        choice_mode = True
        for link in links:
            dest_id = link["DestinationDialogID"]
            dest_node = dialog_nodes.get(dest_id, {})
            dest_fields = dest_node.get("Fields", {})
            text = dest_fields.get("MenuText") or dest_fields.get("DialogueText") or "Choice"
            choices.append((text, dest_id))

    node_start_time = pygame.time.get_ticks() / 1000 - 0.1

#At end of each conversation reset 
def reset_conversation_state():
    global current_node_id, current_convo_id, dialog_nodes, bg_image, char_img
    global actor_name, dialogue, choice_mode, choices, choice_rects, current_sound
    
    pygame.mixer.music.stop()
    
    current_node_id = None
    current_convo_id = None
    dialog_nodes = None
    bg_image = None
    char_img = None
    actor_name = ""
    dialogue = ""
    choice_mode = False
    choices.clear()
    choice_rects.clear()

#Reset stuff if going back to main menu
def reset_to_main_menu():
    global menu_state, selected_country_idx, selected_character_idx
    global selected_category_idx, selected_file_idx, json_path, selecting_convo

    pygame.mixer.music.stop()
    
    menu_state = "country"
    selected_country_idx = 0
    selected_character_idx = 0
    selected_category_idx = 0
    selected_file_idx = 0
    json_path = None
    selecting_convo = True

    
#Menu selection logic
async def handle_menu_events(event):
    global running, menu_state, selected_country_idx, selected_character_idx
    global selected_category_idx, selected_file_idx, json_path, selecting_convo
    global actors, locations, conversations, convo_map, captain_actor_id
    global bg_image, current_node_id, dialog_nodes, selected_convo_idx, scroll_offset, max_scroll
    global last_menu_escape_time
    
    if selecting_convo and json_path is not None:  # Conversation selection screen
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i, (rect, _, cid) in enumerate(convo_buttons):
                adjusted_rect = pygame.Rect(rect.x, rect.y - scroll_offset, rect.width, rect.height)
                if adjusted_rect.collidepoint((mx, my)):
                    selected_convo_idx = i
                    bg_image = await load_conversation(cid)
                    if dialog_nodes:
                        current_node_id = next(iter(dialog_nodes))
                        await load_node(current_node_id)
                        selecting_convo = False
                    return
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                selected_convo_idx = (selected_convo_idx + 1) % len(convo_buttons)
                item_height = int(38 * scale_y)
                spacing = int(12 * scale_y)
                start_y = int(130 * scale_y)
                target_y = start_y + selected_convo_idx * (item_height + spacing)
                auto_scroll_to_selection(target_y)

            elif event.key == pygame.K_UP:
                selected_convo_idx = (selected_convo_idx - 1) % len(convo_buttons)
                item_height = int(38 * scale_y)
                spacing = int(12 * scale_y)
                start_y = int(130 * scale_y)
                target_y = start_y + selected_convo_idx * (item_height + spacing)
                auto_scroll_to_selection(target_y)
                    
            elif event.key == pygame.K_RETURN:
                cid = convo_buttons[selected_convo_idx][2]
                bg_image = await load_conversation(cid)
                if dialog_nodes:
                    current_node_id = next(iter(dialog_nodes))
                    await load_node(current_node_id)
                    selecting_convo = False
            elif event.key == pygame.K_ESCAPE:
                now = pygame.time.get_ticks() / 1000
                if now - last_menu_escape_time > ESCAPE_COOLDOWN:
                    last_menu_escape_time = now
                    reset_to_main_menu()
                
        elif event.type == pygame.MOUSEWHEEL:
            scroll_offset -= event.y * 30
            scroll_offset = max(0, min(scroll_offset, max_scroll))
            return
            

    # Regular menu navigation (country/character/category/file selection)
    items = get_current_list()
    idx_name_map = {
        "country": "selected_country_idx",
        "character": "selected_character_idx",
        "category": "selected_category_idx",
        "file": "selected_file_idx",
    }
    
    current_idx_name = idx_name_map[menu_state]
    current_idx = {
        "selected_country_idx": selected_country_idx,
        "selected_character_idx": selected_character_idx,
        "selected_category_idx": selected_category_idx,
        "selected_file_idx": selected_file_idx,
    }[current_idx_name]
    
    if json_path == None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                current_idx = (current_idx + 1) % len(items)
                setattr(sys.modules[__name__], current_idx_name, current_idx)
                item_height = int(50 * scale_y)
                spacing = int(10 * scale_y)
                start_y = int(120 * scale_y)
                target_y = start_y + current_idx * (item_height + spacing)
                auto_scroll_to_selection(target_y)


            elif event.key == pygame.K_UP:
                current_idx = (current_idx - 1) % len(items)
                setattr(sys.modules[__name__], current_idx_name, current_idx)
                item_height = int(50 * scale_y)
                spacing = int(10 * scale_y)
                start_y = int(120 * scale_y)
                target_y = start_y + current_idx * (item_height + spacing)
                auto_scroll_to_selection(target_y)
     
                
            elif event.key == pygame.K_RETURN:
                if menu_state == "file":
                    country = selection_menu[selected_country_idx]
                    character = country["characters"][selected_character_idx]
                    category = character["categories"][selected_category_idx]
                    
                    
                    base_url = "https://raw.githubusercontent.com/Misekato/VB_Assets/refs/heads/main/Stories/"
                    json_path = base_url + category["files"][selected_file_idx]
                    
                    data = await load_url_json (url = json_path)
                        
                    actors = {actor["ID"]: actor["Fields"] for actor in data["Assets"]["Actors"]}
                    locations = {loc["ID"]: loc["Fields"] for loc in data["Assets"]["Locations"]}
                    conversations = data["Assets"]["Conversations"]
                    convo_map = {convo["ID"]: convo for convo in conversations}
                    
                    captain_actor_id = next((aid for aid, fields in actors.items() 
                                           if fields.get("Name", "").lower() == "captain"), None)
                    prepare_convo_buttons()
                else:
                    menu_state = {
                        "country": "character",
                        "character": "category",
                        "category": "file"
                    }[menu_state]
                    scroll_offset = 0 
            elif event.key == pygame.K_ESCAPE:
                now = pygame.time.get_ticks() / 1000
                if now - last_menu_escape_time > ESCAPE_COOLDOWN:
                    last_menu_escape_time = now
                    if menu_state == "country":
                        running = False
                    else:
                        menu_state = {
                            "character": "country",
                            "category": "character",
                            "file": "category"
                        }[menu_state]
                        scroll_offset = 0
               
        elif event.type == pygame.MOUSEWHEEL:
            scroll_offset -= event.y * 30
            scroll_offset = max(0, min(scroll_offset, max_scroll))
                   
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            items = get_current_list()
            btn_width = SCREEN_WIDTH - 100
            btn_height = int(50 * scale_y)
            spacing = int(10 * scale_y)
            start_y = int(120 * scale_y)
        
            for i, item in enumerate(items):
                rect = pygame.Rect(50, start_y + i * (btn_height + spacing) - scroll_offset, btn_width, btn_height)
                if point_in_rect((mx, my), rect):
                    setattr(sys.modules[__name__], idx_name_map[menu_state], i)
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if menu_state == "file":
                            country = selection_menu[selected_country_idx]
                            character = country["characters"][selected_character_idx]
                            category = character["categories"][selected_category_idx]

                            base_url = "https://raw.githubusercontent.com/Misekato/VB_Assets/refs/heads/main/Stories/"
                            json_path = base_url + category["files"][selected_file_idx]
                            
                            data = await load_url_json (url = json_path)
                                
                            actors = {actor["ID"]: actor["Fields"] for actor in data["Assets"]["Actors"]}
                            locations = {loc["ID"]: loc["Fields"] for loc in data["Assets"]["Locations"]}
                            conversations = data["Assets"]["Conversations"]
                            convo_map = {convo["ID"]: convo for convo in conversations}
                            
                            captain_actor_id = next((aid for aid, fields in actors.items() 
                                                   if fields.get("Name", "").lower() == "captain"), None)
                            prepare_convo_buttons()
                        else:
                            menu_state = {
                                "country": "character",
                                "character": "category",
                                "category": "file"
                            }[menu_state]
                            scroll_offset = 0 
                    break

async def handle_conversation_events(event):
    global selecting_convo, current_node_id, current_convo_id, dialog_nodes
    global bg_image, char_img, actor_name, dialogue, choice_mode, choices, choice_rects
    global node_start_time
    
    # First ensure we have valid dialogue nodes (file loaded)
    if dialog_nodes is None or current_node_id is None:
        reset_conversation_state()
        selecting_convo = True
        return

    if choice_mode:
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            for i, rect in enumerate(choice_rects):
                if point_in_rect((mx, my), rect):
                    await load_node(choices[i][1])
                    break
    else:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if current_node_id not in dialog_nodes:
                reset_conversation_state()
                selecting_convo = True
                return
                
            node = dialog_nodes[current_node_id]
            links = node.get("OutgoingLinks", [])
            full_text_len = len(dialogue)
            elapsed = now - node_start_time
            chars_to_show = min(int(elapsed * typing_speed), full_text_len)

            if chars_to_show < full_text_len:
                node_start_time = now - (full_text_len / typing_speed)
            else:
                if links:
                    next_node_id = links[0]["DestinationDialogID"]
                    if next_node_id in dialog_nodes:  # Check if next node exists
                        await load_node(next_node_id)
                    else:
                        reset_conversation_state()
                        selecting_convo = True
                else:
                    reset_conversation_state()
                    selecting_convo = True

def draw_conversation_view():
    
    global box_height, now, displayed_text
    
    box_height = int(160 * scale_y)
    
    if bg_image:
        screen.blit(bg_image, (0, 0))

    if char_img:
        char_width, char_height = char_img.get_size()
        crop_height = int(char_height * 2 / 3)
        char_x = (SCREEN_WIDTH - char_width) // 2
        char_y = SCREEN_HEIGHT - crop_height
        source_rect = pygame.Rect(0, 0, char_width, crop_height)
        screen.blit(char_img, (char_x, char_y), source_rect)

    if not choice_mode:
        
        elapsed = now - node_start_time
        if elapsed < 0:
            elapsed = 0
        chars_to_show = min(int(elapsed * typing_speed), len(dialogue))
        # Only update displayed_text if we need to show more characters
        if chars_to_show > len(displayed_text):
            displayed_text = dialogue[:chars_to_show]
            
        box_height = int(160 * scale_y)
        dialogue_box = pygame.Surface((SCREEN_WIDTH - int(40 * scale_x), box_height), pygame.SRCALPHA)
        pygame.draw.rect(dialogue_box, (0, 0, 0, 180), dialogue_box.get_rect(), border_radius=int(20 * scale_x))
        screen.blit(dialogue_box, (int(20 * scale_x), SCREEN_HEIGHT - box_height - int(20 * scale_y)))

    if choice_mode:
        choice_rects.clear()
        btn_width = SCREEN_WIDTH - 80
        spacing = 10
        start_y = SCREEN_HEIGHT - box_height - 20 - 40
        if start_y < 50: start_y = 50

        y = start_y
        for i, (text, _) in enumerate(choices):
            padding_x = 10
            wrapped_lines = wrap_text(text, font, btn_width - 2 * padding_x)
            line_height = font.get_linesize()
            btn_height = line_height * len(wrapped_lines) + 10

            rect = pygame.Rect(40, y, btn_width, btn_height)
            choice_rects.append(rect)
            draw_button("", rect)
            
            for line_i, line in enumerate(wrapped_lines):
                line_surf = font.render(line, True, (255, 255, 255))
                text_x = rect.x + padding_x
                text_y = rect.y + 5 + line_i * line_height
                screen.blit(line_surf, (text_x, text_y))

            y += btn_height + spacing
    else:
        elapsed = now - node_start_time
        chars_to_show = min(int(elapsed * typing_speed), len(dialogue))
        displayed_text = dialogue[:chars_to_show]
        max_text_width = SCREEN_WIDTH - int(100 * scale_x)
        line_height = int(30 * scale_y)
        draw_text_wrapped(displayed_text, int(50 * scale_x), SCREEN_HEIGHT - box_height - int(10 * scale_y), max_text_width, line_height)

        if actor_name:
            name_img = font.render(actor_name, True, (0, 0, 0))
            name_x = (SCREEN_WIDTH - name_img.get_width()) // 2
            dialogue_box_y = SCREEN_HEIGHT - box_height - int(20 * scale_y)
            name_y = dialogue_box_y - name_img.get_height() - int(10 * scale_y)

            padding_x, padding_y = int(10 * scale_x), int(5 * scale_y)
            bg_rect = pygame.Rect(
                name_x - padding_x,
                name_y - padding_y,
                name_img.get_width() + padding_x * 2,
                name_img.get_height() + padding_y * 2,
            )
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (255, 255, 255, 180), bg_surf.get_rect(), border_radius=int(12 * scale_x))
            screen.blit(bg_surf, (bg_rect.x, bg_rect.y))
            screen.blit(name_img, (name_x, name_y))

# --- Main loop that starts everything/does stuff---

async def main():
    
    global menu_state, selected_country_idx, selected_character_idx
    global selected_category_idx, selected_file_idx, selected_convo_idx
    global selecting_convo, current_convo_id, current_node_id, dialog_nodes
    global node_start_time, bg_image, char_img, current_char_img
    global actor_name, dialogue, displayed_text, typing_speed
    global choice_mode, choices, choice_rects, convo_buttons
    global scroll_offset, max_scroll, prev_actor_id, selected_actor_images
    global json_path, actors, locations, conversations, convo_map
    global captain_actor_id, muted, volume
    global selection_menu, now
    
    running = True
    while running:
        now = pygame.time.get_ticks() / 1000

        if selection_menu is None:
            selection_menu = await load_url_json(url = "https://raw.githubusercontent.com/Misekato/VB_Assets/refs/heads/main/selection_menu.json")
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if selecting_convo:
                await handle_menu_events(event)
            else:
                if dialog_nodes is not None and current_node_id is not None:
                    await handle_conversation_events(event)
                else:
                    selecting_convo = True
                  
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_EQUALS:
                    volume = min(1.0, volume + 0.1)
                    if not muted:
                        pygame.mixer.music.set_volume(volume)
                elif event.key == pygame.K_MINUS:
                    volume = max(0.0, volume - 0.1)
                    if not muted:
                        pygame.mixer.music.set_volume(volume)
                elif event.key == pygame.K_m:
                    muted = not muted
                    pygame.mixer.music.set_volume(0.0 if muted else volume)

        # --- Drawing the screen stuff ---
        screen.fill((0, 0, 0))

        if selecting_convo and json_path is None:
            draw_menu()
        elif selecting_convo:
            title_surf = font.render("Select a Conversation", True, (255, 255, 255))
            title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, int(80 * scale_y)))
            screen.blit(title_surf, title_rect)

            mouse_pos = pygame.mouse.get_pos()
            for i, (rect, title, _) in enumerate(convo_buttons):
                draw_rect = pygame.Rect(rect.x, rect.y - scroll_offset, rect.width, rect.height)
                if -rect.height < draw_rect.y < SCREEN_HEIGHT: 
                    is_hovered = draw_rect.collidepoint(mouse_pos)
                    draw_button(title, draw_rect, selected=(i == selected_convo_idx) or is_hovered)
        else:
            draw_conversation_view()

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

    pygame.quit()
    
asyncio.run(main())

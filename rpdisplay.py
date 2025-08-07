import RPi.GPIO as GPIO
import dbus
import threading
import time
import psutil
import os
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont

# Dictionary for mapping RetroPie's folder names to a more readable format.
SYSTEM_NAMES = {
    'nes': 'Nintendo Entertainment System',
    'snes': 'Super Nintendo',
    'n64': 'Nintendo 64',
    'gb': 'Game Boy',
    'gba': 'Game Boy Advance',
    'psx': 'PlayStation',
    'psp': 'PlayStation Portable',
    'sega32x': 'Sega 32X',
    'segacd': 'Sega CD',
    'sgg': 'Sega Game Gear',
    'mastersystem': 'Sega Master System',
    'genesis': 'Sega Genesis',
    'mame': 'MAME (Arcade)',
    'arcade': 'Arcade',
    'pcengine': 'PC Engine',
    'pcenginecd': 'PC Engine CD',
    'sg1000': 'Sega SG-1000',
    'megadrive': 'Sega Mega Drive',
    'coleco': 'ColecoVision',
    'dreamcast': 'Sega Dreamcast',
    'gamecube': 'Nintendo GameCube',
    'wii': 'Nintendo Wii',
    'ds': 'Nintendo DS',
    '3ds': 'Nintendo 3DS',
    'gameandwatch': 'Game & Watch',
    'gbc': 'Game Boy Color'
}


# Initialize SPI interface for SH1106 - change to I2C/SSD1106 if using either of those instead.
serial = spi(device=0, port=0)
device = sh1106(serial, rotate=2)

# GPIO Section
JOYSTICK_RIGHT_PIN = 26 # Right Joystick (next page)
JOYSTICK_LEFT_PIN = 5 # Left Joystick (previous page)
BUTTON1_PIN = 21  # Toggle Brightness (low, medium, high, off)
BUTTON2_PIN = 20  # Safe Reboot (hold for 3s)
BUTTON3_PIN = 16  # Safe Shutdown (hold for 3s)

# Brightness levels (0 to 255)
BRIGHTNESS_LEVELS = [30, 128, 255, 0] # Low, Medium, High, Off
brightness_index = 0  # Start at 30 (low)
device.contrast(BRIGHTNESS_LEVELS[brightness_index])

# Automatic page switch
PAGE_TURN = True
PAGE_INTERVAL = 10

# Load  default font
font = ImageFont.load_default()
font_large = ImageFont.load_default()

# Uncomment this and comment out the two lines above to use a custom font! This assumes your font (ie; "Arial.ttf") is in the same folder
#font = ImageFont.truetype("Arial.ttf", size=8)        # Regular size
#font_large = ImageFont.truetype("Arial.ttf", size=12)  # Larger size

# Read current game and system information from psutil
def get_current_game_info():
    try:
        emulator_process_names = ['retroarch', 'lr-mame', 'mednafen', 'pcsx-rearmed', 'reicast', 'mupen64plus', 'daphne']
        
        for proc in psutil.process_iter(['name', 'cmdline']):
            name = proc.info['name']
            cmdline = proc.info['cmdline']
            
            if name in emulator_process_names and cmdline:
                rom_path = None
                for arg in cmdline:
                    if "/roms/" in arg or any(arg.endswith(ext) for ext in ['.nes', '.sfc', '.gb', '.gba', '.gen', '.md', '.zip', '.cue', '.iso', '.pbp']):
                        rom_path = arg
                        break
                
                if rom_path:
                    parts = rom_path.split(os.sep)
                    try:
                        system_idx = parts.index('roms') + 1
                        system_name = parts[system_idx].lower()
                    except (ValueError, IndexError):
                        system_name = "unknown"
                    
                    game_name = os.path.splitext(os.path.basename(rom_path))[0]
                    
                    return system_name, game_name
        
        return "RetroPie", "Menu"
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "RetroPie", "Menu"

# Display game information on screen (page 1)
def display_on_oled(system_text, game_text, stop_event, scroll_speed=0.03):
    display_width = device.width
    display_height = device.height

    base_image = Image.new('1', (display_width, display_height))
    draw = ImageDraw.Draw(base_image)
    draw.rectangle([(0, 0), (display_width - 1, display_height - 1)], outline=255)

    now_playing_text = "- Now Playing -"
    now_playing_bbox = draw.textbbox((0, 0), now_playing_text, font=font_large)
    now_playing_w = now_playing_bbox[2] - now_playing_bbox[0]
    now_playing_x = (display_width - now_playing_w) / 2
    draw.text((now_playing_x, 0), now_playing_text, font=font_large, fill=255)

    system_line = f"{system_text}"
    system_bbox = draw.textbbox((0, 0), system_line, font=font_large)
    system_w = system_bbox[2] - system_bbox[0]
    system_x = (display_width - system_w) / 2
    draw.text((system_x, 20), system_line, font=font_large, fill=255)

    game_line = f"{game_text}"
    game_bbox = draw.textbbox((0, 0), game_line, font=font)
    game_w = game_bbox[2] - game_bbox[0]

    if game_w <= display_width:
        image = base_image.copy()
        draw = ImageDraw.Draw(image)
        game_x = (display_width - game_w) / 2
        draw.text((game_x, 40), game_line, font=font, fill=255)
        device.display(image)
        time.sleep(1)
    else:
        scroll_image = Image.new('1', (game_w + display_width, 10))
        scroll_draw = ImageDraw.Draw(scroll_image)
        scroll_draw.text((display_width, 0), game_line, font=font, fill=255)

        while not stop_event.is_set():
            for offset in range(game_w + display_width):
                if stop_event.is_set():
                    break
                image = base_image.copy()
                draw = ImageDraw.Draw(image)
                crop = scroll_image.crop((offset, 0, offset + display_width, 10))
                image.paste(crop, (0, 40))
                device.display(image)
                time.sleep(scroll_speed)

# Display media information on screen (page 2)
def display_media_on_oled(stop_event, scroll_speed=0.03):
    display_width = device.width
    display_height = device.height

    try:
        session_bus = dbus.SessionBus()
        player = session_bus.get_object("org.mpris.MediaPlayer2.Playerctl", "/org/mpris/MediaPlayer2")
        interface = dbus.Interface(player, dbus_interface="org.freedesktop.DBus.Properties")
        metadata = interface.Get("org.mpris.MediaPlayer2.Player", "Metadata")

        title = str(metadata.get("xesam:title", "Unknown"))
        artist = ", ".join(metadata.get("xesam:artist", ["Unknown"]))
        album = str(metadata.get("xesam:album", "Unknown"))
    except Exception:
        title = "Track: "
        artist = "Artist: "
        album = "Album: "

    base_image = Image.new('1', (display_width, display_height))
    draw = ImageDraw.Draw(base_image)
    draw.rectangle([(0, 0), (display_width - 1, display_height - 1)], outline=255)

    header_text = "- Now Listening -"
    header_bbox = draw.textbbox((0, 0), header_text, font=font_large)
    header_x = (display_width - (header_bbox[2] - header_bbox[0])) / 2
    draw.text((header_x, 0), header_text, font=font_large, fill=255)

    artist_bbox = draw.textbbox((0, 0), artist, font=font)
    artist_x = (display_width - (artist_bbox[2] - artist_bbox[0])) / 2
    draw.text((artist_x, 20), artist, font=font, fill=255)

    album_bbox = draw.textbbox((0, 0), album, font=font)
    album_x = (display_width - (album_bbox[2] - album_bbox[0])) / 2
    draw.text((album_x, 30), album, font=font, fill=255)

    title_bbox = draw.textbbox((0, 0), title, font=font)
    title_w = title_bbox[2] - title_bbox[0]

    if title_w <= display_width:
        image = base_image.copy()
        draw = ImageDraw.Draw(image)
        title_x = (display_width - title_w) / 2
        draw.text((title_x, 42), title, font=font, fill=255)
        device.display(image)
        time.sleep(1)
    else:
        scroll_image = Image.new('1', (title_w + display_width, 10))
        scroll_draw = ImageDraw.Draw(scroll_image)
        scroll_draw.text((display_width, 0), title, font=font, fill=255)

        while not stop_event.is_set():
            for offset in range(title_w + display_width):
                if stop_event.is_set():
                    break
                image = base_image.copy()
                draw = ImageDraw.Draw(image)
                crop = scroll_image.crop((offset, 0, offset + display_width, 10))
                image.paste(crop, (0, 42))
                device.display(image)
                time.sleep(scroll_speed)

# Display system statistics on screen (page 3)
def display_stats_on_oled(stop_event, update_interval=1):
    display_width = device.width
    display_height = device.height

    while not stop_event.is_set():
        image = Image.new('1', (display_width, display_height))
        draw = ImageDraw.Draw(image)

        draw.rectangle([(0, 0), (display_width - 1, display_height - 1)], outline=255)

        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        gpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                gpu_temp = int(f.read()) / 1000.0
        except:
            pass

        header_text = "- System Stats -"
        header_bbox = draw.textbbox((0, 0), header_text, font=font_large)
        header_x = (display_width - (header_bbox[2] - header_bbox[0])) / 2
        draw.text((header_x, 0), header_text, font=font_large, fill=255)

        cpu_line = f"CPU: {cpu:.1f}%"
        gpu_line = f"GPU: {gpu_temp:.1f}°C"
        ram_line = f"RAM: {ram.percent:.1f}%"

        for i, line in enumerate([cpu_line, gpu_line, ram_line]):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_x = (display_width - (bbox[2] - bbox[0])) / 2
            draw.text((text_x, 20 + i * 10), line, font=font, fill=255)

        device.display(image)
        time.sleep(update_interval)

def toggle_brightness(channel):
    global brightness_index
    brightness_index = (brightness_index + 1) % len(BRIGHTNESS_LEVELS)
    device.contrast(BRIGHTNESS_LEVELS[brightness_index])

def safe_reboot(channel):
    t_start = time.time()
    while GPIO.input(channel) == GPIO.LOW:
        if time.time() - t_start >= 3:
            os.system("sudo reboot now")
            break
        time.sleep(0.1)

def safe_shutdown(channel):
    t_start = time.time()
    while GPIO.input(channel) == GPIO.LOW:
        if time.time() - t_start >= 3:
            os.system("sudo shutdown now")
            break
        time.sleep(0.1)

def main():
    last_system = ""
    last_game = ""
    scroll_thread = None
    stop_event = threading.Event()
    current_page = 0  # 0 = game, 1 = media, 2 = system
    last_page_change = time.time()

    def update_display():
        nonlocal scroll_thread, stop_event, last_system, last_game

        if scroll_thread and scroll_thread.is_alive():
            stop_event.set()
            scroll_thread.join()

        stop_event = threading.Event()

        if current_page == 0:
            current_system_raw, current_game = get_current_game_info()
            display_system_name = SYSTEM_NAMES.get(current_system_raw, current_system_raw.capitalize())
            last_system = display_system_name
            last_game = current_game
            scroll_thread = threading.Thread(
                target=display_on_oled,
                args=(display_system_name, current_game, stop_event)
            )
        elif current_page == 1:
            scroll_thread = threading.Thread(
                target=display_media_on_oled,
                args=(stop_event,)
            )
        elif current_page == 2:
            scroll_thread = threading.Thread(
                target=display_stats_on_oled,
                args=(stop_event,)
            )

        scroll_thread.start()

    def next_page(channel=None):
        nonlocal current_page, last_page_change
        current_page = (current_page + 1) % 3
        last_page_change = time.time()
        update_display()

    # Set up GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(JOYSTICK_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(JOYSTICK_RIGHT_PIN, GPIO.FALLING, callback=next_page, bouncetime=300)

    GPIO.setup(BUTTON1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.add_event_detect(BUTTON1_PIN, GPIO.FALLING, callback=toggle_brightness, bouncetime=300)
    GPIO.add_event_detect(BUTTON2_PIN, GPIO.FALLING, callback=safe_reboot, bouncetime=300)
    GPIO.add_event_detect(BUTTON3_PIN, GPIO.FALLING, callback=safe_shutdown, bouncetime=300)

    try:
        update_display()
        while True:
            now = time.time()

            if PAGE_TURN and (now - last_page_change >= PAGE_INTERVAL):
                next_page()

            if current_page == 0:
                current_system_raw, current_game = get_current_game_info()
                display_system_name = SYSTEM_NAMES.get(current_system_raw, current_system_raw.capitalize())
                if display_system_name != last_system or current_game != last_game:
                    update_display()

            time.sleep(1)
    except KeyboardInterrupt:
        GPIO.cleanup()
        if scroll_thread and scroll_thread.is_alive():
            stop_event.set()
            scroll_thread.join()

if __name__ == '__main__':
    main()

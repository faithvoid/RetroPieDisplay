# sakuraDisplay
SH1106-based game/media/system statistic display for RetroPie (includes safe reboot/shutdown!)

## Features
- "Now Playing" menu (currently running system name + icon, currently running game)
- "Game Info" menu (current game cover art and description, pulled from your existing RetroPie scrapes!)
- "Now Listening" menu (track, album and artist via MPRIS)
- "System" menu (CPU usage + temperature, GPU usage + temperature, RAM usage, etc)
- "Network" menu (SSID, connection strength)
- Toggle between automatic and manual menu switching!

## Installation & Usage:
- Download "sakuraDisplay.py" from the latest release onto your Raspberry Pi (via wget or similar utility)
- Download the required dependencies
- Type "python3 sakuraDisplay.py" via console or SSH and you should see the current status of your Pi!
- Use the joystick left/right to switch between the pages, and joystick down to view game synopsis information. 
- To load on RetroPie startup, add the following line to "/opt/retropie/configs/all/autostart.sh": python3 /home/pi/rpdisplay.py &
- To enable automatic page switching, open sakuraPresence.py in your text editor of choice, change "PAGE_TURN" to from "False" to "True" and change "PAGE_INTERVAL" to the amount of seconds to wait per page.
- For synopsis and cover art to work, you must already have valid scraped game data for your RetroPie games, as well as cover art that matches the name of the game you're playing. Otherwise you'll get blank cover art and/or a message saying "no synopsis found".
- To adjust the brightness of the display, press KEY1 to toggle between low/medium/high. 
- To safely reboot your Pi while running this script, hold KEY2 for 3 seconds, and to safely shut down your Pi, hold KEY3 for 3 seconds. 

## TODO:
- Fetch game name from gamelist.xml when available instead of defaulting to the filename
- Modify "Now Listening" section to show video information if detected via MPRIS
- Add option to only automatically switch between Game Info and Synopsis views
- Align icons + text to the center
- Stop text from drawing over border
- Add weather page (powered by wttr.in) (?)
- Add connected controller count to main page(?)
- Notifications page (?)
- Add border toggle
- Individual page toggles
- Implement Discord Rich Presence support to a remote PC via sakuraPresence(?)

## Why?
I've been working on a personal Raspberry Pi 3 A+ consolization project for my CRT TV using RetroPie with the Playstation theme as a frontend, and as a big fan of oldschool modchips with LCD displays, I love the concept of integrating a similar concept into my retro game setup. It's also practical, as you can view other information such as currently playing music, network settings and signal strength, and it's fairly modular, meaning additional information can always be added!

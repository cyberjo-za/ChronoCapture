# ChronoCapture
A lightweight, automated screen-logging utility designed for unobtrusive activity tracking. ChronoCapture periodically takes low-resource screenshots of the active monitor, archives them into compressed logs, and provides a simple GUI for full manual control and configuration.

## ChronoCapture chronique 📸
A lightweight, automated screen-logging utility for unobtrusive activity tracking.

ChronoCapture runs quietly in the background, taking low-quality, grayscale screenshots of the monitor you are actively using. It is designed for minimal performance impact and automatically organizes screenshots into timestamped, compressed archives. A simple graphical user interface (GUI) allows for easy configuration and manual control.

# Key Features ✨
🖥️ Smart Capture: Automatically screenshots only the monitor your mouse cursor is currently on.

⚙️ Dual-Mode Operation: Starts in a hands-off "unattended" mode and can be switched to full manual control with Start/Stop buttons.

🎛️ Full GUI Control: Easily start, stop, and configure all settings without ever touching the code.

📉 Low Resource Usage: Captures are converted to grayscale, resized, and saved in the highly efficient .webp format to save space and minimize performance impact.

🗜️ Automatic Archiving: Periodically collects all screenshots into a highly compressed, timestamped .zip archive and cleans up the original files.

📝 Custom Notes: Optionally prepend a custom note to your archive filenames for better organization and context (e.g., Project-X_2025-09-03-1430-1440.zip).

## Requirements
Python 3.6+

The following Python libraries:

mss

Pillow

pynput

Installation
Ensure you have Python installed on your system.

Install the required libraries using pip:

Bash

pip install mss Pillow pynput
Save the application code as gui_screen_logger.py.

How to Use
Simply run the script from your terminal:

Bash

python gui_screen_logger.py
Unattended Mode
By default, the application will launch and immediately begin capturing screenshots using the default settings (a screenshot every 5 seconds, archiving every 10 minutes).

Manual Mode
Click the "Stop Capture" button to end the unattended session. It will perform a final archive of any captured images.

Adjust the settings in the GUI as needed (e.g., change intervals, quality, or add a note).

Click the "Start Capture" button to begin a new session with your custom settings.

How It Works
The application creates and uses two folders in the same directory it is run from:

temp_screenshots/: This folder is used to temporarily store the individual .webp screenshot files before they are archived.

archives/: This folder contains the final compressed .zip files. The archives are named with a timestamp and your optional note, like: YourNote_Year-month-day-starthour-startmin-endhour-endmin.zip.

The core capture process runs in a separate background thread, ensuring the GUI remains responsive at all times.
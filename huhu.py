import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import sys
from langdetect import detect, LangDetectException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import random
import google.generativeai as genai
import os
import re

# Gemini API configuration
# You'll need to get a free API key from https://aistudio.google.com/app/apikey
DEFAULT_GEMINI_API_KEY = "AIzaSyD44KcX2fBzJ8ZHr-cYwl83-4ibpDlOlh4"  # Replace with your API key
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"  # Free tier model

def filter_non_bmp_characters(text, replacement=''):
    """
    Filter out characters outside the Basic Multilingual Plane (BMP) that Edge WebDriver can't handle.
    This includes emojis and some special characters.
    
    Args:
        text: The input text to filter
        replacement: Optional replacement for filtered characters (default: remove them)
        
    Returns:
        Filtered text that only contains BMP characters
    """
    if not text:
        return text
        
    # Count original length to detect if filtering happened
    original_length = len(text)
    
    # This regex matches any character with code point > 0xFFFF (outside BMP)
    filtered_text = re.sub(r'[\U00010000-\U0010FFFF]', replacement, text)
    
    # Also filter common emoji ranges that might cause problems
    filtered_text = re.sub(r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]', replacement, filtered_text)
    
    # Log if characters were filtered
    if len(filtered_text) != original_length:
        filtered_chars = original_length - len(filtered_text)
        print(f"Warning: Removed {filtered_chars} unsupported characters from response")
    
    return filtered_text

class BotApp:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.driver = None
        self.setup_gui()
        
    def setup_gui(self):
        self.root.title("Discord AI Bot Controller")
        
        # Control Frame
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=0, column=0, sticky="ew")
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_bot)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        # Model Selection
        ttk.Label(control_frame, text="Gemini API Key:").grid(row=0, column=2, padx=5)
        self.api_key_var = tk.StringVar(value=DEFAULT_GEMINI_API_KEY)
        api_key_entry = ttk.Entry(control_frame, textvariable=self.api_key_var, width=30)
        api_key_entry.grid(row=0, column=3, padx=5)

        ttk.Label(control_frame, text="Gemini Model:").grid(row=1, column=2, padx=5)
        self.model_var = tk.StringVar(value=DEFAULT_GEMINI_MODEL)
        model_entry = ttk.Entry(control_frame, textvariable=self.model_var, width=20)
        model_entry.grid(row=1, column=3, padx=5)
        
        # Status Indicators
        status_frame = ttk.Frame(self.root, padding="10")
        status_frame.grid(row=1, column=0, sticky="w")
        
        self.status_label = ttk.Label(status_frame, text="Status: Stopped", foreground="red")
        self.status_label.grid(row=0, column=0)
        
        self.login_status = ttk.Label(status_frame, text="Logged In: No")
        self.login_status.grid(row=0, column=1, padx=20)
        
        # Log Window
        self.log_area = scrolledtext.ScrolledText(self.root, width=60, height=15)
        self.log_area.grid(row=2, column=0, padx=10, pady=10)
        
        # Redirect print statements to log area
        sys.stdout = TextRedirector(self.log_area, "stdout")
        
        # Add Server/Channel Selection Frame
        server_frame = ttk.Frame(self.root, padding="10")
        server_frame.grid(row=0, column=1, sticky="nsew")
        
        ttk.Label(server_frame, text="Server ID:").grid(row=0, column=0, sticky="w")
        self.server_id_entry = ttk.Entry(server_frame, width=25)
        self.server_id_entry.grid(row=0, column=1, padx=5)
        self.server_id_entry.insert(0, "1296738817117655080")  # Example ID
        
        ttk.Label(server_frame, text="Channel ID:").grid(row=1, column=0, sticky="w")
        self.channel_id_entry = ttk.Entry(server_frame, width=25)
        self.channel_id_entry.grid(row=1, column=1, padx=5)
        self.channel_id_entry.insert(0, "1296738817784414240")  # Example ID
        
        ttk.Label(server_frame, text="Ignore Usernames:").grid(row=2, column=0, sticky="w")
        self.owner_username_entry = ttk.Entry(server_frame, width=25)
        self.owner_username_entry.grid(row=2, column=1, padx=5)
        self.owner_username_entry.insert(0, "klwj")  # Default owner username
        
        # Additional help text for usernames
        username_help = ttk.Label(
            server_frame,
            text="Comma-separated list of usernames to ignore",
            foreground="gray",
            wraplength=200
        )
        username_help.grid(row=3, column=1, sticky="w", pady=2)

        # Add help text
        help_text = ttk.Label(
            server_frame, 
            text="Right-click channel → Copy ID\n(Developer mode must be enabled)",
            foreground="gray",
            wraplength=200
        )
        help_text.grid(row=4, column=0, columnspan=2, pady=5)

    def start_bot(self):
        # Configure Gemini API
        api_key = self.api_key_var.get().strip()
        if not api_key:
            print("Error: Please enter a valid Gemini API key")
            return
        
        try:
            genai.configure(api_key=api_key)
            print(f"Gemini API successfully configured")
        except Exception as e:
            print(f"Error configuring Gemini API: {e}")
            return
        
        self.running = True
        self.status_label.config(text="Status: Running", foreground="green")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Start bot in a separate thread
        bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        bot_thread.start()
        
    def stop_bot(self):
        self.running = False
        self.status_label.config(text="Status: Stopping...", foreground="orange")
        if self.driver:
            self.driver.quit()
        self.status_label.config(text="Status: Stopped", foreground="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def get_last_message(self):
        try:
            # Get all messages with their authors
            message_containers = self.driver.find_elements(By.CSS_SELECTOR, "li[id^='chat-messages-']")
            if not message_containers:
                return None, None
                
            last_container = message_containers[-1]
            
            # Get author name
            try:
                author = last_container.find_element(By.CSS_SELECTOR, "h3[class*='header'] span[class*='username']").text
            except:
                author = "Unknown"
                
            # Get message text
            try:
                message = last_container.find_element(By.CSS_SELECTOR, "div[id^='message-content-']").text
            except:
                message = ""
                
            return message, author
        except Exception as e:
            print(f"Error finding messages: {e}")
            return None, None

    def run_bot(self):
        try:
            # Configure Edge to use default profile
            edge_options = Options()
            edge_options.use_chromium = True
            edge_options.add_argument("--user-data-dir=C:/Users/klwj/AppData/Local/Microsoft/Edge/User Data")
            edge_options.add_argument("--profile-directory=Default")
            edge_options.add_argument("--remote-allow-origins=*")
            edge_options.add_argument("--no-first-run")
            edge_options.add_argument("--no-default-browser-check")
            edge_options.add_argument("--disable-extensions")
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            # Initialize driver
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(
                service=service,
                options=edge_options
            )
            self.login_status.config(text="Logged In: Yes (Existing Session)")
            
            server_id = self.server_id_entry.get().strip()
            channel_id = self.channel_id_entry.get().strip()
            
            if not server_id or not channel_id:
                print("Error: Please enter both Server ID and Channel ID")
                self.stop_bot()
                return
                
            self.driver.get(f"https://discord.com/channels/{server_id}/{channel_id}")
            time.sleep(10)

            # Get bot's own username
            try:
                username_element = self.driver.find_element(By.CSS_SELECTOR, "div[class*='nameTag'] div[class*='username']")
                self.bot_username = username_element.text
                print(f"Bot's username detected as: {self.bot_username}")
            except Exception as e:
                self.bot_username = "Unknown"
                print("Could not detect bot username, using 'Unknown'")

            last_message = ""
            last_author = ""
            self.own_messages = set()  # Keep track of messages sent by the bot
            
            # Initialize Gemini model
            model_name = self.model_var.get()
            try:
                print(f"Initializing Gemini model: {model_name}")
                self.generation_config = {
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
                
                self.safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                ]
                
                self.model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings
                )
                
                print("Gemini model initialized successfully")
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
                self.stop_bot()
                return
            
            while self.running:
                new_message, author = self.get_last_message()
                
                # Skip if no message or it's the same as last one
                if not new_message or new_message == last_message:
                    time.sleep(2)
                    continue
                
                print(f"Message from {author}: {new_message}")
                
                # Skip bot's own messages and messages from the bot owner(s)
                owner_usernames = [username.strip() for username in self.owner_username_entry.get().split(',')]
                if (author == self.bot_username or 
                    author in owner_usernames or  # Skip messages from the owner(s)
                    new_message in self.own_messages or 
                    any(response in new_message for response in 
                        ["Di kita gets", "That's interesting", "What do you mean"])):
                    print(f"Skipping message from {author}")
                    last_message = new_message
                    last_author = author
                    time.sleep(2)
                    continue
                
                # Process the message
                try:
                    # Content moderation
                    blacklist = ["bayot", "pokpok", "gago"]
                    if any(word in new_message.lower() for word in blacklist):
                        print("Blocked inappropriate message")
                        # Skip sending any response for blacklisted words
                        continue
                    else:
                        # Use Gemini for response generation
                        try:
                            # Create Filipino system prompt
                            filipino_prompt = """Ikaw ay isang Filipino chatbot na palaging sumasagot sa Filipino lang, kahit ano pa ang wika ng user.
                            Gumamit ng maraming Filipino slang at casual na pananalita katulad ng 'lodi', 'bes', 'awit', 'petmalu', etc.
                            Kung hindi mo maintindihan ang message, sabihin mo 'Di ko gets, bes. Pwede paexplain?'
                            Dapat lahat ng sagot mo ay Filipino lang, huwag mag-English.
                            Ang mga sagot mo ay dapat maikli at casual lang.
                            """
                            
                            print(f"Sending request to Gemini API...")
                            
                            chat = self.model.start_chat(history=[
                                {"role": "user", "parts": [filipino_prompt]},
                                {"role": "model", "parts": ["Oo naman, bes! Gagawin ko yan. Tagalog lang ako magsasalita, promise!"]}
                            ])
                            
                            response = chat.send_message(new_message)
                            ai_reply = response.text
                            
                            # Filter out non-BMP characters that Edge WebDriver can't handle
                            ai_reply = filter_non_bmp_characters(ai_reply)
                            
                            if not ai_reply:
                                print("Empty response from Gemini")
                                # Don't generate a fallback response
                                continue
                                
                        except Exception as api_error:
                            print(f"Gemini API error: {api_error}")
                            # Skip sending a message when API fails
                            continue

                    # Locate the chat input and send the message
                    try:
                        # Wait for input box to be clickable
                        input_box = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='textbox']"))
                        )
                        # Scroll into view and click using JavaScript
                        self.driver.execute_script("arguments[0].scrollIntoView();", input_box)
                        self.driver.execute_script("arguments[0].click();", input_box)
                        
                        # Further sanitize the response to be safe
                        try:
                            # Try to just stick with basic ASCII and common characters to avoid issues
                            ai_reply = ''.join(char for char in ai_reply if ord(char) < 65535)
                            
                            # Break long responses into chunks to avoid potential issues
                            max_chunk_size = 1000
                            if len(ai_reply) > max_chunk_size:
                                chunks = [ai_reply[i:i+max_chunk_size] for i in range(0, len(ai_reply), max_chunk_size)]
                                print(f"Splitting long response into {len(chunks)} chunks")
                                ai_reply = chunks[0] + "... (response truncated due to length)"
                        except Exception as char_error:
                            print(f"Error sanitizing response: {char_error}")
                            # If all else fails, use a fallback response
                            ai_reply = "Pasensya, may error sa reply ko. Subukan ulit mamaya."
                        
                        # Type message character by character with delay
                        for char in ai_reply:
                            try:
                                input_box.send_keys(char)
                                time.sleep(0.05)  # Simulate human typing
                            except Exception as char_error:
                                print(f"Error typing character: {ord(char) if char else 'None'}, {char_error}")
                                # Skip problematic character and continue
                                continue
                                
                        input_box.send_keys(Keys.RETURN)
                        print(f"Sent response: {ai_reply[:30]}...")
                        
                        # Store this message to avoid replying to it
                        self.own_messages.add(ai_reply)
                        # Limit the size of the set to avoid memory issues
                        if len(self.own_messages) > 20:
                            self.own_messages = set(list(self.own_messages)[-20:])
                    except Exception as e:
                        print(f"Error sending message: {e}")
                        # Try an alternative method if the first fails
                        try:
                            print("Attempting alternative message sending method...")
                            # Try paste method instead of character by character typing
                            self.driver.execute_script(
                                "arguments[0].innerText = arguments[1];", 
                                input_box, 
                                "Pasensya, nakaencounter ako ng error sa pag-type ng message."
                            )
                            input_box.send_keys(Keys.RETURN)
                            print("Sent fallback message using alternative method")
                        except Exception as alt_error:
                            print(f"Alternative sending method also failed: {alt_error}")
             
                    last_message = new_message
                    last_author = author
                except Exception as e:
                    print(f"AI error: {e}")

                # Add a delay to prevent rapid responses
                time.sleep(5)
        except Exception as e:
            print(f"Bot error: {str(e)}")
            self.stop_bot()

class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
        
    def write(self, text):
        self.widget.configure(state="normal")
        self.widget.insert("end", text, (self.tag,))
        self.widget.configure(state="disabled")
        self.widget.see("end")

if __name__ == "__main__":
    root = tk.Tk()
    app = BotApp(root)
    root.mainloop()

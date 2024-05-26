import tkinter as tk
from tkinter import messagebox
from connectors.binance import BinanceClient
import json
from cryptography.fernet import Fernet

KEY_FILE = "keyfile.key"
DATA_FILE = "credentials.json"


class LoginFrame(tk.Frame):
    def __init__(self, root, on_success, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.root = root
        self.on_success = on_success

        self.api_key_label = tk.Label(self, text="API Key", font=("Arial", 12))
        self.api_key_label.pack(pady=10)

        self.api_key_entry = tk.Entry(self, font=("Arial", 12))
        self.api_key_entry.pack(pady=10)

        self.secret_key_label = tk.Label(self, text="Secret Key", font=("Arial", 12))
        self.secret_key_label.pack(pady=10)

        self.secret_key_entry = tk.Entry(self, font=("Arial", 12), show="*")
        self.secret_key_entry.pack(pady=10)

        self.testnet_var = tk.BooleanVar(value=True)
        self.testnet_check = tk.Checkbutton(
            self, text="Use Testnet", variable=self.testnet_var
        )
        self.testnet_check.pack(pady=10)

        self.futures_var = tk.BooleanVar(value=True)
        self.futures_check = tk.Checkbutton(
            self, text="Use Futures", variable=self.futures_var
        )
        self.futures_check.pack(pady=10)

        self.remember_var = tk.BooleanVar()
        self.remember_check = tk.Checkbutton(
            self, text="Remember Me", variable=self.remember_var
        )
        self.remember_check.pack(pady=10)

        self.submit_button = tk.Button(
            self, text="Submit", font=("Arial", 12, "bold"), command=self.validate_keys
        )
        self.submit_button.pack(pady=20)

        self.load_saved_credentials()

    def load_saved_credentials(self):
        try:
            with open(KEY_FILE, "rb") as key_file:
                key = key_file.read()
                cipher_suite = Fernet(key)

            with open(DATA_FILE, "rb") as data_file:
                encrypted_data = data_file.read()

            decrypted_data = cipher_suite.decrypt(encrypted_data).decode()
            credentials = json.loads(decrypted_data)

            self.api_key_entry.insert(0, credentials["api_key"])
            self.secret_key_entry.insert(0, credentials["secret_key"])
            self.testnet_var.set(credentials.get("testnet", True))
            self.futures_var.set(credentials.get("futures", True))
            self.remember_var.set(True)
        except Exception as e:
            print("No saved credentials found:", e)

    def save_credentials(self):
        credentials = {
            "api_key": self.api_key_entry.get(),
            "secret_key": self.secret_key_entry.get(),
            "testnet": self.testnet_var.get(),
            "futures": self.futures_var.get(),
        }
        data = json.dumps(credentials).encode()

        key = Fernet.generate_key()
        cipher_suite = Fernet(key)

        encrypted_data = cipher_suite.encrypt(data)

        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)

        with open(DATA_FILE, "wb") as data_file:
            data_file.write(encrypted_data)

    def validate_keys(self):
        api_key = self.api_key_entry.get()
        secret_key = self.secret_key_entry.get()
        testnet = self.testnet_var.get()
        futures = self.futures_var.get()

        binance_client = BinanceClient(api_key, secret_key, testnet, futures)

        if binance_client.validate_keys():
            if self.remember_var.get():
                self.save_credentials()
            self.on_success(binance_client)
        else:
            messagebox.showerror("Error", "Invalid API Key or Secret Key")


def create_login_interface(root, on_success):
    login_frame = LoginFrame(root, on_success)
    login_frame.pack(fill="both", expand=True)
    return login_frame

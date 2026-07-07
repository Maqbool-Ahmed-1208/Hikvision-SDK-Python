import os
from configparser import ConfigParser
from threading import Lock
import json


class AppConfig:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AppConfig, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = None):
        if self._initialized:
            return
        self._initialized = True

        self._config_dict = {}
        self._load_config(config_path)
        self.load_from_json()

    def _load_config(self, config_path: str = None):
        """Load configuration into dictionary."""
        parser = ConfigParser()
        
        # keeps original case of keys
        parser.optionxform = str 

        env_value = os.getenv("APPLICATION_TYPE", "STANDALONE").upper()
        print(f"APPLICATION_TYPE = {env_value}")

        if config_path:
            cfg_path = config_path
        elif env_value == "CONTAINERISED":
            cfg_path = "/usr/local/disruptlabs/ai/config.cfg"
        else:
            cfg_path = "app/config/config.cfg"

        loaded = parser.read(cfg_path)
        if not loaded:
            print(f"No config file found at {cfg_path}")

        # Convert parser to nested dict
        for section in parser.sections():
            self._config_dict[section] = {}
            for key, value in parser.items(section):
                self._config_dict[section][key] = value
                

        print("Loaded sections:", list(self._config_dict.keys()))
        
        
    def load_from_json(self, which_json: str = None):
        """Load configuration from one or more JSON files and merge into _config_dict."""
        # Determine JSON file paths
        if which_json is None:
            json_path = self.get("PATHS", "ONBOARDING", fallback=None)
            json_path2 = self.get("PATHS", "MODULE_JSON", fallback=None)
        else:
            json_path = self.get("PATHS", which_json, fallback=None)
            json_path2 = None

        # Helper function to load and merge JSON into config
        def merge_json_file(path):
            if not path or not os.path.exists(path):
                print(f"⚠️ No JSON config file found at {path}")
                return
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid JSON config format in {path}: must be a dictionary")

            for section, values in data.items():
                if section not in self._config_dict:
                    self._config_dict[section] = {}
                if isinstance(values, dict):
                    self._config_dict[section].update(values)
                else:
                    raise ValueError(f"Invalid section format in JSON: {section}")

        # Load from one or both files
        merge_json_file(json_path)
        if json_path2:
            merge_json_file(json_path2)


    def get(self, section: str, key: str, fallback=None, cast=str):
        value = self._config_dict.get(section, {}).get(key, fallback)
        if value is None:
            return fallback
        if isinstance(value, dict):
            return value
        
        return cast(value)


    def as_dict(self):
        """Return entire config dict (read-only copy)."""
        return dict(self._config_dict)


# # --- Example usage ---
# if __name__ == "__main__":
#     cfg = AppConfig()

#     # Load extra values from JSON if needed
#     cfg.load_from_json("app/config/test.json")
    
#     db_user = cfg.get("DB", "USERNAME")
#     db_pass = cfg.get("DB", "PASSWORD")
#     signal_topic = cfg.get("MQTT", "SIGNAL_TOPIC")

#     print("DB USER:", db_user)
#     print("SIGNAL TOPIC:", signal_topic)

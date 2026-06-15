import sys
sys.path.insert(0, ".")
from backend.config.settings import settings
print("Supervisor:", settings.model_config_yaml.get("agents", {}).get("supervisor"))
print("Default model:", settings.model_config_yaml.get("default_model"))
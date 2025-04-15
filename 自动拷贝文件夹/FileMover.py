import os
import shutil
import time
import logging
import json
import argparse
import sys
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            'file_transfer.log',
            maxBytes=100*1024*1024,  # 100MB
            backupCount=5,           # Keep 5 historical logs
            encoding='utf-8'
        )
    ]
)

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    "source_dir": "C:/path/to/source",
    "dest_dir": "Z:/path/to/destination",
    "interval": 10
}


def load_config():
    """Load configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        # Validate paths
        if not all(os.path.isdir(p) for p in [config['source_dir'], config['dest_dir']]):
            logging.error("Invalid directory paths in config")
            sys.exit(1)

        return config
    except FileNotFoundError:
        logging.error(f"Config file {CONFIG_FILE} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in {CONFIG_FILE}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing key in config: {str(e)}")
        sys.exit(1)


def ensure_directory(path):
    """Create directory if not exists"""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logging.error(f"Directory creation failed: {path} - {str(e)}")


def secure_transfer(src, dest):
    """Cross-device file transfer with error handling"""
    try:
        shutil.move(src, dest)
    except OSError:
        try:
            shutil.copy2(src, dest)
            os.remove(src)
        except Exception as e:
            logging.error(f"File transfer failed: {src} - {str(e)}")
            return False
    except Exception as e:
        logging.error(f"File transfer failed: {src} - {str(e)}")
        return False
    return True


def process_files(config):
    """Main file processing logic"""
    try:
        for root, _, files in os.walk(config['source_dir']):
            for filename in files:
                src_path = os.path.join(root, filename)
                if not os.path.exists(src_path):
                    continue

                rel_path = os.path.relpath(src_path, config['source_dir'])
                dest_path = os.path.join(config['dest_dir'], rel_path)

                ensure_directory(os.path.dirname(dest_path))

                if not secure_transfer(src_path, dest_path):
                    continue
    except Exception as e:
        logging.error(f"Directory traversal error: {str(e)}")


def initialize_config():
    """Create default config file if missing"""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        logging.info(f"Created default config file: {CONFIG_FILE}")


def main():
    initialize_config()
    config = load_config()

    parser = argparse.ArgumentParser(description='File Transfer Service')
    parser.parse_args()

    logging.info("Service started")
    while True:
        try:
            process_files(config)
            time.sleep(config["interval"])
        except KeyboardInterrupt:
            logging.info("Service stopped by user")
            break
        except Exception as e:
            logging.error(f"Main loop error: {str(e)}")
            time.sleep(5)


if __name__ == '__main__':
    main()
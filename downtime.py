import argparse
import datetime
import logging
import subprocess
import sys
import time

if sys.version_info[0] < 3:
    sys.exit('ERROR: only python 3 supported')

START_TIME = datetime.time(22, 30) # 10:30pm
END_TIME = datetime.time(6, 30) # 6:30am
INTERVAL_SEC = 60 # 1 minute
DISABLE_WIFI_CMD = 'networksetup -setairportpower en0 off'
ENABLE_WIFI_CMD = 'networksetup -setairportpower en0 on'

def is_downtime(now=None):
    now = now or datetime.time(*time.localtime()[3:6])
    if START_TIME < END_TIME:
        return not (now >= END_TIME or now < START_TIME)
    else:
        return not (now >= END_TIME and now < START_TIME)

def disable_wifi():
    p = subprocess.run(DISABLE_WIFI_CMD, shell=True)
    if p.returncode == 0:
        logging.info('Successfully disabled wifi')
    else:
        logging.error('Error when disabling wifi ({}).'
                ' Got exit code {}'.format(DISABLE_WIFI_CMD, p.returncode))

def enable_wifi():
    p = subprocess.run(ENABLE_WIFI_CMD, shell=True)
    if p.returncode == 0:
        logging.info('Successfully enabled wifi')
    else:
        logging.error('Error when enabling wifi ({}).'
                ' Got exit code {}'.format(ENABLE_WIFI_CMD, p.returncode))

def run():
    logging.info('Starting downtime checking')
    in_downtime = False
    try:
        while True:
            if is_downtime(): 
                logging.debug('Checking downtime: True')
                if not in_downtime:
                    logging.info('Entering downtime period')
                    in_downtime = True
                    disable_wifi()
            else:
                logging.debug('Checking downtime: False')
                if in_downtime:
                    logging.info('Exiting downtime period')
                    in_downtime = False
                    enable_wifi()
            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        logging.info('Stopping downtime checking')

def _setup_logging(level):
    logging.basicConfig(
            format='%(asctime)s - %(levelname)s - %(message)s',
            level=level)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '-d', '--debug', action='store_true', help='print debug messages')
    args = parser.parse_args()
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    _setup_logging(log_level)
    run()

import sys

if sys.version_info[0] < 3:
    sys.exit('ERROR: only python 3 supported')

import argparse
import datetime
import faulthandler
import logging
import re
import subprocess
import time

import pynput

from threading import Event, Lock

START_TIME = datetime.time(22, 30) # 10:30pm
END_TIME = datetime.time(6, 30) # 6:30am
CHECK_INTERVAL_SEC = 60 # 1 minute
IGNORE_ACTION_INTERVAL_SEC = 3
LAST_ACTION_SEC = 5
#EXTRA_TIME = 60 * 5 # 5 minutes
EXTRA_TIME = 60 * 2 # 2 minutes
DISABLE_WIFI_CMD = 'networksetup -setairportpower en0 off'
ENABLE_WIFI_CMD = 'networksetup -setairportpower en0 on'
DIALOG_TIMEOUT = 5
DIALOG_CMD = 'osascript -e $\'Tell application "System Events"' \
        ' to display dialog "{msg}" with title "{title}"' \
        ' giving up after ' + str(DIALOG_TIMEOUT) + \
        ' buttons {{"OK"}} default button "OK"\''
DIALOG_CMD2 = 'osascript -e $\'Tell application "System Events"' \
        ' to display dialog "{msg}" with title "{title}"' \
        ' giving up after ' + str(DIALOG_TIMEOUT) + \
        ' buttons {{"OK", "{button}"}} default button "OK"\''
NAGS = [
        ('You\\\'re in downtime! Take a break from the computer <3',
            'Computer Break'),
        ('Seriously it\\\'s time to wind down.', 'Break Time'),
        ('Take a deep breath. Close your eyes. What do you know to be true?',
            'Get Zen, dude'),
        ('Okay, you seem a bit desparate. Let\\\'s stop now.' \
                ' Or do you really need some more time?',
            'It is now Downtime', 'Just a little more time')
        ]


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


class ThatWhichNags(object):

    def __init__(self, nags, extra_time=EXTRA_TIME):
        self.dialog_count = 0
        self.nags = nags
        self.extra_time = extra_time
        self._last_action = None
        self._should_end = Event()
        self._threadlock = Lock()
        self.m_listener = pynput.mouse.Listener(
                on_move=self._on_action_handler('on_move'),
                on_click=self._on_action_handler('on_click'),
                on_scroll=self._on_action_handler('on_scroll'))
        self.kb_listener = pynput.keyboard.Listener(
                on_press=self._on_action_handler('on_keypress'))

    def _on_action_handler(self, name):
        def _on_action(*args):
            with self._threadlock:
                if not self._last_action:
                    logging.debug('First time nagging')
                    logging.debug('Got action from {}'.format(name))
                    self.nag()
                    self._last_action = time.time()
                elif (time.time() - self._last_action
                        > IGNORE_ACTION_INTERVAL_SEC):
                    logging.debug('Got action from {}'.format(name))
                    logging.debug('It has been more than {} seconds'
                            ' since last dialog'.format(
                                IGNORE_ACTION_INTERVAL_SEC))
                    self.nag()
                    self._last_action = time.time()
                else:
                    if len(args) == 1 and args[0] == pynput.keyboard.Key.shift:
                        logging.debug('Remaining seconds'
                                ' until next possible nag: {}'.format(
                                    IGNORE_ACTION_INTERVAL_SEC
                                    - (time.time() - self._last_action)))
        return _on_action

    @classmethod
    def _dialog(cls, msg, title, button=None):
        logging.debug('Creating dialog "{}": {}'.format(title, msg))
        cmd = DIALOG_CMD
        if button:
            logging.debug('Creating dialog with additional button: {}'.format(
                button))
            cmd = DIALOG_CMD2
        cmd_str = cmd.format(msg=msg, title=title, button=button)
        logging.debug('Running command: {}'.format(cmd_str))
        p = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                encoding='utf-8')
        if p.returncode != 0:
            logging.error('Error generating nag dialog: {}'.format(p.stderr))
        m = re.match('button returned:(.*), gave up:(.*)', p.stdout)
        if m is None:
            logging.error('Could not extract result of button click')
        return (m.group(1), m.group(2) == 'true') if m is not None \
                else ('', False)

    def nag(self):
        logging.debug('dialog_count: {}'.format(self.dialog_count))
        i = min(self.dialog_count, len(self.nags) - 1)
        logging.debug('Using nag {}'.format(i))
        self.dialog_count += 1
        pressed_button = ''
        no_user_response = True
        while no_user_response and not self._should_end.is_set():
            pressed_button, no_user_response = ThatWhichNags._dialog(
                    *self.nags[i])
        logging.debug('User clicked: "{}" button'.format(pressed_button))
        if pressed_button == 'OK':
            # Give user time to perform one last action
            logging.debug('Sleeping {} seconds'.format(LAST_ACTION_SEC))
            self._should_end.wait(LAST_ACTION_SEC)
            logging.debug('Done sleeping')
        else:
            logging.debug('Extra time: sleeping {} seconds'.format(
                self.extra_time))
            self._should_end.wait(self.extra_time)
            logging.debug('Done sleeping')
            # start nags over again
            self.dialog_count = 0

    def start_listeners(self):
        logging.debug('Starting mouse and keyboard listeners')
        self._should_end.clear()
        self.m_listener.start()
        self.kb_listener.start()

    def stop_listeners(self):
        logging.debug('Stopping mouse and keyboard listeners')
        try:
            self._should_end.set()
            self.m_listener.stop()
            self.kb_listener.stop()
        finally:
            self.m_listener.join()
            self.kb_listener.join()

def run():
    twn = ThatWhichNags(NAGS)
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
                    twn.start_listeners()
            else:
                logging.debug('Checking downtime: False')
                if in_downtime:
                    logging.info('Exiting downtime period')
                    in_downtime = False
                    enable_wifi()
                    twn.stop_listeners()
            time.sleep(CHECK_INTERVAL_SEC)
    except KeyboardInterrupt:
        logging.info('Stopping downtime checking')
    finally:
        if in_downtime:
            logging.info('Restoring wifi')
            enable_wifi()
            twn.stop_listeners()

def _setup_logging(level):
    logging.basicConfig(
            format='%(asctime)s - %(threadName)s - %(levelname)s' \
                    ' - %(message)s',
            level=level)


if __name__ == '__main__':
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '-d', '--debug', action='store_true', help='print debug messages')
    args = parser.parse_args()
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    _setup_logging(log_level)
    run()

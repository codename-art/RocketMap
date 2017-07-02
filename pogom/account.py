#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import random
import time
from threading import Lock
from timeit import default_timer

from mrmime.pogoaccount import POGOAccount

from pogom.shadow import sees_shadowed_pokemon
from .proxy import get_new_proxy
from .utils import (in_radius, equi_rect_distance)

log = logging.getLogger(__name__)


class TooManyLoginAttempts(Exception):
    pass


# Create the POGOAccount object that'll be used to scan.
def setup_pogo_account(args, status, account):
    pgacc = POGOAccount(account['auth_service'], account['username'],
                        account['password'])
    pgacc.cfg['player_locale'] = args.player_locale
    account['pgacc'] = pgacc

    # New account - new proxy.
    if args.proxy:
        # If proxy is not assigned yet or if proxy-rotation is defined
        # - query for new proxy.
        if ((not status['proxy_url']) or
                ((args.proxy_rotation is not None) and
                 (args.proxy_rotation != 'none'))):

            proxy_num, status['proxy_url'] = get_new_proxy(args)
            if args.proxy_display.upper() != 'FULL':
                status['proxy_display'] = proxy_num
            else:
                status['proxy_display'] = status['proxy_url']

    if status['proxy_url']:
        log.debug('Using proxy %s', status['proxy_url'])
        pgacc.proxy_url = status['proxy_url']

    return pgacc


# Complete tutorial with a level up by a Pokestop spin.
# API argument needs to be a logged in API instance.
# Called during fort parsing in models.py
def tutorial_pokestop_spin(pgacc, player_level, forts, step_location, account):
    if player_level > 1:
        log.debug(
            'No need to spin a Pokestop. ' +
            'Account %s is already level %d.',
            account['username'], player_level)
    else:  # Account needs to spin a Pokestop for level 2.
        log.debug(
            'Spinning Pokestop for account %s.',
            account['username'])
        for fort in forts:
            if fort.get('type') == 1:
                if spin_pokestop(pgacc, fort, step_location):
                    log.debug(
                        'Account %s successfully spun a Pokestop ' +
                        'after completed tutorial.',
                        account['username'])
                    return True

    return False


def spin_pokestop(pgacc, fort, step_location):
    spinning_radius = 0.04
    if in_radius((fort['latitude'], fort['longitude']), step_location,
                 spinning_radius):
        log.debug('Attempt to spin Pokestop (ID %s)', fort['id'])

        time.sleep(random.uniform(0.8, 1.8))  # Do not let Niantic throttle
        spin_response = spin_pokestop_request(pgacc, fort, step_location)
        if not spin_response:
            return False

        time.sleep(random.uniform(2, 4))  # Do not let Niantic throttle

        # Check for reCaptcha
        if pgacc.has_captcha():
            log.debug('Account encountered a reCaptcha.')
            return False

        spin_result = spin_response['FORT_SEARCH']['result']
        if spin_result is 1:
            log.debug('Successful Pokestop spin.')
            return True
        elif spin_result is 2:
            log.debug('Pokestop was not in range to spin.')
        elif spin_result is 3:
            log.debug('Failed to spin Pokestop. Has recently been spun.')
        elif spin_result is 4:
            log.debug('Failed to spin Pokestop. Inventory is full.')
        elif spin_result is 5:
            log.debug('Maximum number of Pokestops spun for this day.')
        else:
            log.debug(
                'Failed to spin a Pokestop. Unknown result %d.',
                spin_result)

    return False


def spin_pokestop_request(pgacc, fort, step_location):
    try:
        return pgacc.req_fort_search(fort['id'],
                                     fort['latitude'],
                                     fort['longitude'],
                                     step_location[0],
                                     step_location[1])
    except Exception as e:
        log.error('Exception while spinning Pokestop: %s.', repr(e))
        return False


def encounter_pokemon_request(pgacc, encounter_id, spawnpoint_id,
                              scan_location):
    try:
        return pgacc.req_encounter(encounter_id, spawnpoint_id,
                                   scan_location[0], scan_location[1])
    except Exception as e:
        log.error('Exception while encountering Pokémon: %s.', repr(e))
        return False


def update_rareless_scans(account, responses):
    # Check if rare/shadowed Pokemon are found
    if 'GET_MAP_OBJECTS' in responses:
        if sees_shadowed_pokemon(responses):
            account['rareless_scans'] = 0
        else:
            account['rareless_scans'] = (account.get(
                'rareless_scans') or 0) + 1


# The AccountSet returns a scheduler that cycles through different
# sets of accounts (e.g. L30). Each set is defined at runtime, and is
# (currently) used to separate regular accounts from L30 accounts.
# TODO: Migrate the old account Queue to a real AccountScheduler, preferably
# handled globally via database instead of per instance.
# TODO: Accounts in the AccountSet are exempt from things like the
# account recycler thread. We could've hardcoded support into it, but that
# would have added to the amount of ugly code. Instead, we keep it as is
# until we have a proper account manager.
class AccountSet(object):

    def __init__(self, kph):
        self.sets = {}

        # Scanning limits.
        self.kph = kph

        # Thread safety.
        self.next_lock = Lock()

    # Set manipulation.
    def create_set(self, name, values=[]):
        if name in self.sets:
            raise Exception('Account set ' + name + ' is being created twice.')

        self.sets[name] = values

    # Release an account back to the pool after it was used.
    def release(self, account):
        if 'in_use' not in account:
            log.error('Released account %s back to the AccountSet,'
                      + " but it wasn't locked.",
                      account['username'])
        else:
            account['in_use'] = False

    # Get next account that is ready to be used for scanning.
    def next(self, set_name, coords_to_scan):
        # Yay for thread safety.
        with self.next_lock:
            # Readability.
            account_set = self.sets[set_name]

            # Loop all accounts for a good one.
            now = default_timer()
            max_speed_kmph = self.kph

            for i in range(len(account_set)):
                account = account_set[i]

                # Make sure it's not in use.
                if account.get('in_use', False):
                    continue

                # Make sure it's not captcha'd.
                if account.get('captcha', False):
                    continue

                # Check if we're below speed limit for account.
                last_scanned = account.get('last_scanned', False)

                if last_scanned:
                    seconds_passed = now - last_scanned
                    old_coords = account.get('last_coords', coords_to_scan)

                    distance_km = equi_rect_distance(
                        old_coords,
                        coords_to_scan)
                    cooldown_time_sec = distance_km / max_speed_kmph * 3600

                    # Not enough time has passed for this one.
                    if seconds_passed < cooldown_time_sec:
                        continue

                # We've found an account that's ready.
                account['last_scanned'] = now
                account['last_coords'] = coords_to_scan
                account['in_use'] = True

                return account

        # TODO: Instead of returning False, return the amount of min. seconds
        # the instance needs to wait until the first account becomes available,
        # so it doesn't need to keep asking if we know we need to wait.
        return False

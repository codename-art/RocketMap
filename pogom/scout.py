import logging
from base64 import b64decode
from threading import Lock, Thread

import time

import sys

import datetime
from pgoapi import PGoApi

from pogom import schedulers
from pogom.account import check_login, get_player_level, TooManyLoginAttempts
from pogom.proxy import get_new_proxy, check_proxies, proxies_refresher
from pogom.transform import jitter_location
from pogom.utils import get_args, get_pokemon_name

from collections import deque
from queue import Queue
from .captcha import handle_captcha

log = logging.getLogger(__name__)

args = get_args()
api = None
key_scheduler = schedulers.KeyScheduler(args.hash_key)

scoutLock = Lock()
last_scout_timestamp = None
encounter_cache = {}
accounts = []

# Create a list for failed accounts.
account_failures = []
# Create a double-ended queue for captcha'd accounts
account_captchas = deque()
wh_updates_queue = Queue()

threadStatus = {
    'type': 'Worker',
    'message': 'Creating thread...',
    'success': 0,
    'fail': 0,
    'noitems': 0,
    'skip': 0,
    'captcha': 0,
    'username': '',
    # 'proxy_display': proxy_display,
    # 'proxy_url': proxy_url,
}


def scout_init():
    global accounts
    accounts = []
    if args.scout_account_username is not None:
        accounts.append({
            'username': args.scout_account_username,
            'password': args.scout_account_password,
            'auth_service': args.scout_account_auth,
            'last_used': None,
            'in_use': False})
    if args.scout_accounts_file:
        parse_csv(accounts)

    # Processing proxies if set (load from file, check and overwrite old
    # args.proxy with new working list)
    args.proxy = check_proxies(args)

    # Run periodical proxy refresh thread
    if (args.proxy_file is not None) and (args.proxy_refresh > 0):
        t = Thread(target=proxies_refresher,
                   name='proxy-refresh', args=(args,))
        t.daemon = True
        t.start()
    else:
        log.info('Periodical proxies refresh disabled.')


def encounter_request(encounter_id, spawnpoint_id, latitude, longitude):
    req = api.create_request()
    encounter_result = req.encounter(
        encounter_id=encounter_id,
        spawn_point_id=spawnpoint_id,
        player_latitude=latitude,
        player_longitude=longitude)
    encounter_result = req.check_challenge()
    encounter_result = req.get_hatched_eggs()
    encounter_result = req.get_inventory()
    encounter_result = req.check_awarded_badges()
    encounter_result = req.download_settings()
    encounter_result = req.get_buddy_walked()
    return req.call()


def has_captcha(request_result):
    captcha_url = request_result['responses']['CHECK_CHALLENGE']['challenge_url']
    return len(captcha_url) > 1


def calc_pokemon_level(pokemon_info):
    cpm = pokemon_info["cp_multiplier"]
    if cpm < 0.734:
        level = 58.35178527 * cpm * cpm - 2.838007664 * cpm + 0.8539209906
    else:
        level = 171.0112688 * cpm - 95.20425243
    level = (round(level) * 2) / 2.0
    return level


def scout_error(error_msg):
    log.error(error_msg)
    return {"msg": error_msg}


def parse_scout_result(request_result, encounter_id, pokemon_name, step_location, account):
    global encounter_cache

    wait_secs = request_result.get("wait", 0)
    if wait_secs > 0:
        return scout_error("Scout is busy. Waiting {} more seconds before next scout use.".format(round(wait_secs)))

    if has_captcha(request_result):
        captcha = handle_captcha(args, threadStatus, api, account,
                                 account_failures,
                                 account_captchas, wh_updates_queue,
                                 request_result, step_location)
        return scout_error("Failure: Scout account captcha'd.")

    if request_result is None:
        return scout_error("Unknown failure")

    encounter_result = request_result.get('responses', {}).get('ENCOUNTER', {})

    if encounter_result.get('status', None) == 3:
        return scout_error("Failure: Pokemon already despawned.")

    if 'wild_pokemon' not in encounter_result:
        return scout_error("No wild pokemon info found")

    pokemon_info = encounter_result['wild_pokemon']['pokemon_data']
    cp = pokemon_info["cp"]
    level = calc_pokemon_level(pokemon_info)
    trainer_level = get_player_level(request_result)
    response = {
        'cp': cp,
        'level': level,
        'trainer_level': trainer_level,
        'individual_attack': pokemon_info.get(
            'individual_attack', 0),
        'individual_defense': pokemon_info.get(
            'individual_defense', 0),
        'individual_stamina': pokemon_info.get(
            'individual_stamina', 0),
        'move_1': pokemon_info['move_1'],
        'move_2': pokemon_info['move_2']
    }
    log.info(u"Found level {} {} with CP {} for trainer level {} by {}.".format(level, pokemon_name, cp, trainer_level,
                                                                                account['username']))

    if 'capture_probability' in encounter_result:
        probs = encounter_result['capture_probability']['capture_probability']
        response['prob_red'] = "{:.1f}".format(probs[0] * 100)
        response['prob_blue'] = "{:.1f}".format(probs[1] * 100)
        response['prob_yellow'] = "{:.1f}".format(probs[2] * 100)
    else:
        log.warning("No capture_probability info found")

    encounter_cache[encounter_id] = response
    return response


def perform_scout(p):
    global api, last_scout_timestamp, encounter_cache

    if not args.scout:
        return {"msg": "Scouting disabled"}

    if len(accounts) == 0:
        return {"msg": "No scout account configured."}

    pokemon_name = get_pokemon_name(p.pokemon_id)

    # Check cache once in a non-blocking way
    if p.encounter_id in encounter_cache:
        result = encounter_cache[p.encounter_id]
        log.info(u"Cached scout-result: level {} {} with CP {}.".format(result["level"], pokemon_name, result["cp"]))
        return result

    step_location = []
    scoutLock.acquire()
    try:
        now = time.time()
        account = None
        wait_secs = args.scout_cooldown_delay
        for acc in accounts:
            if account is None:
                last_scout_timestamp = acc["last_used"]
                if acc['in_use']:
                    continue
                elif last_scout_timestamp is not None \
                    and now < last_scout_timestamp + args.scout_cooldown_delay:
                    wait_secs = min(last_scout_timestamp + args.scout_cooldown_delay - now, wait_secs)
                else:
                    account = acc
                    account["last_used"] = now
                    acc['in_use'] = True
    finally:
        scoutLock.release()

    if account is None:
        log.info("Waiting {} more seconds before next scout use.".format(wait_secs))
        # time.sleep(wait_secs)
        request_result = {}
        request_result["wait"] = wait_secs
    else:
        # Check cache again after mutually exclusive access
        if p.encounter_id in encounter_cache:
            result = encounter_cache[p.encounter_id]
            log.info(
                u"Cached scout-result: level {} {} with CP {}.".format(result["level"], pokemon_name, result["cp"]))
            return result

        # Delay scouting

        if last_scout_timestamp is not None and now < last_scout_timestamp + args.scout_cooldown_delay:
            wait_secs = last_scout_timestamp + args.scout_cooldown_delay - now
            log.info("Waiting {} more seconds before next scout use.".format(wait_secs))
            # time.sleep(wait_secs)
            request_result = {}
            request_result["wait"] = wait_secs
        else:
            log.info(u"Scouting a {} at {}, {}".format(pokemon_name, p.latitude, p.longitude))
            step_location = jitter_location([p.latitude, p.longitude, 42])

            if api is None:
                # instantiate pgoapi
                api = PGoApi()

            api.set_position(*step_location)
            proxy_num, proxy_url = get_new_proxy(args)
            if proxy_url:
                log.debug('Using proxy %s', proxy_url)
                api.set_proxy({'http': proxy_url, 'https': proxy_url})

            try:
                check_login(args, account, api, None, proxy_url)
                if args.hash_key:
                    key = key_scheduler.next()
                    log.debug('Using key {} for this scout use.'.format(key))
                    api.activate_hash_server(key)

                request_result = encounter_request(
                    long(b64decode(p.encounter_id)),
                    p.spawnpoint_id,
                    p.latitude,
                    p.longitude)

                # Update last timestamp
                account['last_used'] = time.time()
            except TooManyLoginAttempts:
                log.error("{} failed to login, going to sleep for 600 seconds".format(account['username']))
                account['last_used'] = time.mktime((datetime.datetime.now() + datetime.timedelta(seconds=600)).timetuple())
                account['in_use'] = False
                return {"msg": "Scout can't login"}
            finally:
                account['in_use'] = False


    return parse_scout_result(request_result, p.encounter_id, pokemon_name, step_location, account)


def parse_csv(accounts):
    # If using a CSV file, add the data where needed into the username,
    # password and auth_service arguments.
    # CSV file should have lines like "ptc,username,password",
    # "username,password" or "username".
    # Giving num_fields something it would usually not get.
    num_fields = -1
    usernames = []
    auth_service = []
    passwords = []
    with open(args.scout_accounts_file, 'r') as f:
        for num, line in enumerate(f, 1):

            fields = []

            # First time around populate num_fields with current field
            # count.
            if num_fields < 0:
                num_fields = line.count(',') + 1

            csv_input = []
            csv_input.append('')
            csv_input.append('<username>')
            csv_input.append('<username>,<password>')
            csv_input.append('<ptc/google>,<username>,<password>')

            # If the number of fields is differend this is not a CSV.
            if num_fields != line.count(',') + 1:
                print(sys.argv[0] +
                      ": Error parsing CSV file on line " + str(num) +
                      ". Your file started with the following " +
                      "input, '" + csv_input[num_fields] +
                      "' but now you gave us '" +
                      csv_input[line.count(',') + 1] + "'.")
                sys.exit(1)

            field_error = ''
            line = line.strip()

            # Ignore blank lines and comment lines.
            if len(line) == 0 or line.startswith('#'):
                continue

            # If number of fields is more than 1 split the line into
            # fields and strip them.
            if num_fields > 1:
                fields = line.split(",")
                fields = map(str.strip, fields)

            # If the number of fields is one then assume this is
            # "username". As requested.
            if num_fields == 1:
                # Empty lines are already ignored.
                usernames.append(line)

            # If the number of fields is two then assume this is
            # "username,password". As requested.
            if num_fields == 2:
                # If field length is not longer than 0 something is
                # wrong!
                if len(fields[0]) > 0:
                    usernames.append(fields[0])
                else:
                    field_error = 'username'

                # If field length is not longer than 0 something is
                # wrong!
                if len(fields[1]) > 0:
                    passwords.append(fields[1])
                else:
                    field_error = 'password'

            # If the number of fields is three then assume this is
            # "ptc,username,password". As requested.
            if num_fields == 3:
                # If field 0 is not ptc or google something is wrong!
                if (fields[0].lower() == 'ptc' or
                            fields[0].lower() == 'google'):
                    auth_service.append(fields[0])
                else:
                    field_error = 'method'

                # If field length is not longer then 0 something is
                # wrong!
                if len(fields[1]) > 0:
                    usernames.append(fields[1])
                else:
                    field_error = 'username'

                # If field length is not longer then 0 something is
                # wrong!
                if len(fields[2]) > 0:
                    passwords.append(fields[2])
                else:
                    field_error = 'password'

            if num_fields > 3:
                print(('Too many fields in accounts file: max ' +
                       'supported are 3 fields. ' +
                       'Found {} fields').format(num_fields))
                sys.exit(1)

            # If something is wrong display error.
            if field_error != '':
                type_error = 'empty!'
                if field_error == 'method':
                    type_error = (
                        'not ptc or google instead we got \'' +
                        fields[0] + '\'!')
                print(sys.argv[0] +
                      ": Error parsing CSV file on line " + str(num) +
                      ". We found " + str(num_fields) + " fields, " +
                      "so your input should have looked like '" +
                      csv_input[num_fields] + "'\nBut you gave us '" +
                      line + "', your " + field_error +
                      " was " + type_error)
                sys.exit(1)

                # Make the accounts list.
    for i, username in enumerate(usernames):
        accounts.append({'username': username,
                         'password': passwords[i],
                         'auth_service': auth_service[i],
                         'last_used': None,
                         'in_use': False})

    return accounts

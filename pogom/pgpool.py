import logging
import requests
import time
import json

log = logging.getLogger(__name__)
args = None


def pgpool_init(global_args):
    global args
    args = global_args


def pgpool_enabled():
    if args.pgpool_url is None:
        return False
    else:
        return True


def pgpool_request_accounts(init_args, count=None, highlvl=False, initial=False):
    global args
    if args is None:
        args = init_args

    if count is None:
        count = init_args.highlvl_workers if highlvl else init_args.workers
    request = {
        'system_id': init_args.status_name,
        'count': count,
        'min_level': 30 if highlvl else 1,
        'max_level': 40 if highlvl else 29,
        'include_already_assigned': initial,
        'banned_or_new': init_args.pgpool_new,
        'shadow': init_args.pgpool_shadow_banned
    }

    r = requests.get("{}/account/request".format(init_args.pgpool_url), params=request)
    return r.json()


def pgpool_release_account(account, status, api=None, reason=None):
    if 'from_pgpool' in account:
        pgpool_update(account, status, api, release=True, reason=reason)
    else:
        log.error("Could not release account {} to PGPool. No POGOAccount found!".format(account['username']))


def pgpool_update(account, status, api=None, release=False, reason=None):
    data = {
        'username': account['username'],
        'password': account['password'],
        'auth_service': account['auth_service'],
        'system_id': None if release else args.status_name
    }
    if status is not None:
        data.update({
            'latitude': status['latitude'],
            'longitude': status['longitude']
        })
    # After login we know whether we've got a captcha
    if 'captcha' in account:
        data.update({
            'captcha': account['captcha']
        })
    if 'missed' in status:
        data['rareless_scans'] = status['missed']
        if status['missed'] > args.max_missed:
            data['shadowbanned'] = True
        else:
            data['shadowbanned'] = False
    if 'banned' in account:
        data['banned'] = account['banned']
    else:
        data['banned'] = False

    if 'warning' in account:
        data.update({
            'warn': account['warning'],
            # 'banned': account.is_banned(),
            # 'ban_flag': account.get_state('banned')
            # 'tutorial_state': data.get('tutorial_state'),
        })
    if 'level' in account:
        data.update({
            'level': account['level'],
            # 'xp': account.get_stats('experience'),
            # 'encounters': account.get_stats('pokemons_encountered'),
            # 'balls_thrown': account.get_stats('pokeballs_thrown'),
            # 'captures': account.get_stats('pokemons_captured'),
            'spins': account['spins'],
            'walked': account['walked']
        })
    if 'items' in account:
        data.update({
            'balls': 0,
            'total_items': len(account['items']),
            'pokemon': len(account['pokemons']),
            'eggs': len(account['eggs']),
            'incubators': len(account['incubators'])
        })
    # if account.inbox:
    #     data.update({
    #         'email': account.inbox.get('EMAIL'),
    #         'team': account.inbox.get('TEAM'),
    #         'coins': account.inbox.get('POKECOIN_BALANCE'),
    #         'stardust': account.inbox.get('STARDUST_BALANCE')
    #     })
    if release and reason:
        data['_release_reason'] = reason
    try:
        cmd = 'release' if release else 'update'
        url = '{}/account/{}'.format(args.pgpool_url, cmd)
        r = requests.post(url, data=json.dumps(data))
        if r.status_code == 200:
            log.info("Successfully {}d PGPool account.".format(cmd))
        else:
            log.warning("Got status code {} from PGPool while updating account.".format(r.status_code))
    except Exception as e:
        log.error("Could not update PGPool account: {}".format(repr(e)))
    # account._last_pgpool_update = time.time()

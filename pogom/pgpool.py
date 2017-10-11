import logging
import requests
import time
import json

log = logging.getLogger(__name__)


def pgpool_request_accounts(args, count=None, highlvl=False, initial=False):
    if count is None:
        count = args.highlvl_workers if highlvl else args.workers
    request = {
        'system_id': args.status_name,
        'count': count,
        'min_level': 30 if highlvl else 1,
        'max_level': 40 if highlvl else 29,
        'include_already_assigned': initial
    }

    r = requests.get("{}/account/request".format(args.pgpool_url), params=request)
    return r.json()


def pgpool_release_account(args, account, status, api, reason):
    if 'pgacc' in account:
        update_pgpool(args, account['pgacc'], status, api, release=True, reason=reason)
    else:
        log.error("Could not release account {} to PGPool. No POGOAccount found!".format(account['username']))


def update_pgpool(args, account, status, api, release=False, reason=None):
    data = {
        'username': account.username,
        'password': account.password,
        'auth_service': account.auth_service,
        'system_id': None if release else args.status_name,
        'latitude': status.latitude,
        'longitude': status.longitude
    }
    # After login we know whether we've got a captcha
    if api.is_logged_in():
        data.update({
            'captcha': account.has_captcha()
        })
    if status.missed is not None:
        data['rareless_scans'] = status.missed
    if status.missed > args.max_missed:
        data['shadowbanned'] = True
    if account['banned']:
        data['banned'] = True
    if account['warning']:
        data.update({
            'warn': account['warning'],
            # 'banned': account.is_banned(),
            # 'ban_flag': account.get_state('banned')
            #'tutorial_state': data.get('tutorial_state'),
        })
    if account['level']:
        data.update({
            'level': account['level'],
            # 'xp': account.get_stats('experience'),
            # 'encounters': account.get_stats('pokemons_encountered'),
            # 'balls_thrown': account.get_stats('pokeballs_thrown'),
            # 'captures': account.get_stats('pokemons_captured'),
            'spins': account['spins'],
            'walked': account['walked']
        })
    if account.items:
        data.update({
            'balls': 0,
            'total_items': account.items,
            'pokemon': len(account.pokemon),
            'eggs': len(account.eggs),
            'incubators': len(account.incubators)
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
        url = '{}/account/{}'.format(account.cfg['pgpool_url'], cmd)
        r = requests.post(url, data=json.dumps(data))
        if r.status_code == 200:
            account.log_info("Successfully {}d PGPool account.".format(cmd))
        else:
            account.log_warning("Got status code {} from PGPool while updating account.".format(r.status_code))
    except Exception as e:
        account.log_error("Could not update PGPool account: {}".format(repr(e)))
    account._last_pgpool_update = time.time()

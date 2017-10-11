import logging
import requests

log = logging.getLogger(__name__)


def pgpool_request_accounts(args, count, highlvl=False, initial=False):
    request = {
        'system_id': args.status_name,
        'count': count,
        'min_level': 30 if highlvl else 1,
        'max_level': 40 if highlvl else 29,
        'include_already_assigned': initial
    }

    r = requests.get("{}/account/request".format(args.pgpool_url), params=request)
    return r.json()


def pgpool_release_account(account):
    if 'pgacc' in account:
        account['pgacc'].update_pgpool(release=True)
    else:
        log.error("Could not release account {} to PGPool. No POGOAccount found!".format(account['username']))

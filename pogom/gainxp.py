#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import random
import time

from pgoapi.protos.pogoprotos.inventory.item.item_id_pb2 import *

from pogom.account import log, spin_pokestop_request, \
    encounter_pokemon_request
from pogom.utils import get_pokemon_name, in_radius

log = logging.getLogger(__name__)


DROP_BALLS = 50

DITTO_POKEDEX_ID = 132

ITEM_NAMES = {
    ITEM_POKE_BALL: u"Poké Ball",
    ITEM_GREAT_BALL: u"Great Ball",
    ITEM_ULTRA_BALL: u"Ultra Ball",
    ITEM_POTION: u"Potion",
    ITEM_SUPER_POTION: u"Super Potion",
    ITEM_HYPER_POTION: u"Hyper Potion",
    ITEM_MAX_POTION: u"Max Potion",
    ITEM_REVIVE: u"Revive",
    ITEM_MAX_REVIVE: u"Max Revive",
    ITEM_BLUK_BERRY: u"Bluk Berry",
    ITEM_NANAB_BERRY: u"Nanab Berry",
    ITEM_WEPAR_BERRY: u"Wepar Berry",
    ITEM_PINAP_BERRY: u"Pinap Berry",
    ITEM_RAZZ_BERRY: u"Razz Berry"
}


def is_ditto(args, pgacc, p):
    pokemon_id = p['pokemon_data']['pokemon_id']
    pokemon_name = get_pokemon_name(pokemon_id)
    captured_pokemon_name = pokemon_name
    log.info(u'{} may be a Ditto. Triggering catch logic!'.format(pokemon_name))

    # Encounter Pokemon.
    time.sleep(args.encounter_delay)
    encounter_pokemon_request(pgacc, p['encounter_id'],
                              p['spawn_point_id'],
                              [p['latitude'], p['longitude']])

    # Now try to catch it.
    got_ditto = False
    catch_result = catch(pgacc, p['encounter_id'], p['spawn_point_id'])
    if catch_result['catch_status'] == 'success':
        if int(catch_result['pid']) == DITTO_POKEDEX_ID:
            logmsg = u'Successfully caught a Ditto disguised as {}! Needed {} attempts.'
            captured_pokemon_name = get_pokemon_name(DITTO_POKEDEX_ID)
            got_ditto = True
        else:
            logmsg = u'Successfully caught a regular {} after {} attempts.'
        log.info(logmsg.format(pokemon_name, catch_result['attempts']))
        # Release the Pokemon in any case
        time.sleep(random.uniform(7, 10))
        if release(pgacc, catch_result['capture_id']):
            log.info(u'Successfully released {}.'.format(captured_pokemon_name))
    else:
        log.info("Failed catching {}: {} Attempts: {}".format(pokemon_name, catch_result['reason'], catch_result['attempts']))
    return got_ditto

def catch(pgacc, encounter_id, spawn_point_id):
    # Try to catch pokemon, but don't get stuck.
    rv = {
        'catch_status': 'fail',
        'reason': "Unknown reason.",
        'attempts': 1
    }
    while rv['attempts'] < 3:
        time.sleep(random.uniform(2, 3))
        try:
            # Randomize throwing parameters. Some stuff to read:
            # https://pokemongo.gamepress.gg/catch-mechanics
            # https://www.reddit.com/r/pokemongodev/comments/4vlnwj/pokemon_go_catch_mechanicsformula_discussion/
            normalized_reticle_size = 1.1 + 0.70 * random.random()
            spin_modifier = 0.4 + 0.4 * random.random()

            # Determine best ball - we know for sure that we have at least one
            inventory = pgacc.inventory
            ball = ITEM_ULTRA_BALL if inventory.get(ITEM_ULTRA_BALL, 0) > 0 else (
                ITEM_GREAT_BALL if inventory.get(ITEM_GREAT_BALL, 0) > 0 else ITEM_POKE_BALL)

            catch_result = pgacc.req_catch_pokemon(
                encounter_id,
                spawn_point_id,
                ball,
                normalized_reticle_size,
                spin_modifier)

            if (catch_result is not None and 'CATCH_POKEMON' in catch_result):
                catch_status = catch_result['CATCH_POKEMON']['status']

                # Success!
                if catch_status == 1:
                    # Check inventory for caught Pokemon
                    capture_id = catch_result['CATCH_POKEMON']['captured_pokemon_id']
                    pid = get_captured_pokemon_id_from_inventory(capture_id, catch_result)
                    if pid:
                        # Set ID of caught Pokemon
                        rv['catch_status'] = 'success'
                        rv['pid'] = pid
                        rv['capture_id'] = capture_id
                    else:
                        rv['reason'] = "Could not find caught Pokemon in inventory."
                    return rv

                # Broke free!
                if catch_status == 2:
                    log.debug('Catch attempt %s failed. It broke free!', rv['attempts'])

                # Ran away!
                if catch_status == 3:
                    rv['reason'] = "Pokemon ran away!"
                    return rv

                # Dodged!
                if catch_status == 4:
                    log.debug('Catch attempt %s failed. It dodged the ball!', rv['attempts'])

            else:
                log.error('Catch attempt %s failed. The api response was empty!', rv['attempts'])

        except Exception as e:
            log.error('Catch attempt %s failed. API exception: %s', rv['attempts'], repr(e))

        rv['attempts'] += 1

    if rv['attempts'] >= 3:
        rv['attempts'] -= 1
        rv['reason'] = "Giving up."

    return rv


def get_captured_pokemon_id_from_inventory(capture_id, response):
    if 'GET_INVENTORY' not in response:
        log.warning(
            "CAPTURED_PKM_ID: No inventory in responses. Got {}".format(
                response.keys()))
        return None

    iitems = response['GET_INVENTORY']['inventory_delta'][
        'inventory_items']
    for item in iitems:
        iidata = item['inventory_item_data']
        if 'pokemon_data' in iidata and iidata['pokemon_data']['id'] == capture_id:
            return iidata['pokemon_data']['pokemon_id']
    return None


def release(pgacc, cpid):
    try:
        release_result = pgacc.req_release_pokemon(cpid)

        if (release_result is not None and 'RELEASE_POKEMON' in release_result):
            release_result = release_result['RELEASE_POKEMON']['result']
            if int(release_result) == 1:
                return True
            else:
                log.error('Failed to release Pokemon with result code: %s.', release_result)

    except Exception as e:
        log.error('Exception while releasing Pokemon. Error: %s', repr(e))

    return False


def pokestop_spinnable(fort, step_location):
    spinning_radius = 0.04
    in_range = in_radius((fort['latitude'], fort['longitude']), step_location,
                         spinning_radius)
    now = time.time()
    needs_cooldown = "cooldown_complete_timestamp_ms" in fort and fort["cooldown_complete_timestamp_ms"] / 1000 > now
    return in_range and not needs_cooldown


def spin_pokestop_update_inventory(pgacc, fort, step_location):
    time.sleep(random.uniform(0.8, 1.8))  # Do not let Niantic throttle
    spin_response = spin_pokestop_request(pgacc, fort, step_location)
    if not spin_response:
        return False

    time.sleep(random.uniform(2, 4))  # Do not let Niantic throttle

    # Check for Captcha
    if pgacc.has_captcha():
        log.debug('Account encountered a reCaptcha.')
        return False

    spin_result = spin_response['FORT_SEARCH']['result']
    if spin_result is 1:
        awards = get_awarded_items(spin_response['FORT_SEARCH']['items_awarded'])
        log.info('Got {} items ({} balls) from Pokestop.'.format(awards['total'], awards['balls']))
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


def get_awarded_items(items_awarded):
    awards = {}
    total = 0
    balls = 0
    for item in items_awarded:
        item_id = item['item_id']
        count = item['item_count']
        total += count
        if item_id in (ITEM_POKE_BALL, ITEM_GREAT_BALL, ITEM_ULTRA_BALL, ITEM_MASTER_BALL):
            balls += count
        awards[item_id] = awards.get(item_id, 0) + count
    awards['total'] = total
    awards['balls'] = balls
    return awards


def cleanup_inventory(pgacc):
    drop_stats = {}
    # Just need to make room for more items
    if pgacc.inventory_total >= 350:
        drop_items(pgacc, ITEM_POTION, drop_stats)
        drop_items(pgacc, ITEM_SUPER_POTION, drop_stats)
        drop_items(pgacc, ITEM_HYPER_POTION, drop_stats)
        drop_items(pgacc, ITEM_MAX_POTION, drop_stats)
        drop_items(pgacc, ITEM_REVIVE, drop_stats)
        drop_items(pgacc, ITEM_MAX_REVIVE, drop_stats)
        drop_items(pgacc, ITEM_BLUK_BERRY, drop_stats)
        drop_items(pgacc, ITEM_NANAB_BERRY, drop_stats)
        drop_items(pgacc, ITEM_WEPAR_BERRY, drop_stats)
        drop_items(pgacc, ITEM_PINAP_BERRY, drop_stats)
        drop_items(pgacc, ITEM_RAZZ_BERRY, drop_stats)

        # Throw away balls if necessary
        if pgacc.inventory_total >= 350:
            need_to_drop = pgacc.inventory_total - 350 + DROP_BALLS
            items_dropped = drop_items(pgacc, ITEM_POKE_BALL, drop_stats, need_to_drop)
            if items_dropped < need_to_drop:
                need_to_drop -= items_dropped
                items_dropped = drop_items(pgacc, ITEM_GREAT_BALL, drop_stats, need_to_drop)
                if items_dropped < need_to_drop:
                    need_to_drop -= items_dropped
                    drop_items(pgacc, ITEM_ULTRA_BALL, drop_stats, need_to_drop)

        # Log what was dropped
        drops = []
        for item_id in sorted(drop_stats):
            dropped = drop_stats[item_id]
            drops.append(u"{} {}s".format(dropped, ITEM_NAMES[item_id]))
        log.info(u"Items dropped: {}".format(u", ".join(drops)))


def drop_items(pgacc, item_id, drop_stats, drop_count=-1):
    item_count = pgacc.inventory.get(item_id, 0)
    drop_count = item_count if drop_count == -1 else min(item_count, drop_count)
    if drop_count > 0:
        result = drop_items_request(pgacc, item_id, drop_count)
        if result == 1:
            drop_stats[item_id] = drop_count
            return drop_count
        else:
            log.warning(u"Failed dropping {} {}s.".format(drop_count, ITEM_NAMES[item_id]))
    return 0


def drop_items_request(pgacc, item_id, amount):
    time.sleep(random.uniform(2, 4))
    try:
        response_dict = pgacc.req_recycle_inventory_item(item_id, amount)
        if ('RECYCLE_INVENTORY_ITEM' in response_dict):
            drop_details = response_dict['RECYCLE_INVENTORY_ITEM']
            return drop_details.get('result', -1)
    except Exception as e:
        log.warning('Exception while dropping items: %s', repr(e))
        return False


# Send LevelUpRewards request to check for and accept level up rewards.
# @Returns
# 0: UNSET
# 1: SUCCESS
# 2: AWARDED_ALREADY
def level_up_rewards_request(pgacc, level):
    time.sleep(random.uniform(2, 3))
    try:
        rewards_response = pgacc.req_level_up_rewards(level)

        if 'LEVEL_UP_REWARDS' in rewards_response:
            reward_details = rewards_response['LEVEL_UP_REWARDS']
            return reward_details.get('result', -1)

    except Exception as e:
        log.error('Exception while requesting level up rewards: %s', repr(e))

    return False

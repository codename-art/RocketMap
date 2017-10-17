#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time

from pogom.pgpool import pgpool_enabled
from .pgorequestwrapper import PGoRequestWrapper

log = logging.getLogger(__name__)


class PGoApiWrapper:
    def __init__(self, api):
        log.debug('Wrapped PGoApi.')
        self.api = api
        self._pgpool_auto_update_enabled = pgpool_enabled()
        self._last_pgpool_update = 0

    def __getattr__(self, attr):
        orig_attr = getattr(self.api, attr)

        if callable(orig_attr):
            def hooked(*args, **kwargs):
                result = orig_attr(*args, **kwargs)
                # Prevent wrapped class from becoming unwrapped.
                if result == self.api:
                    return self
                return result
            return hooked
        else:
            return orig_attr

    def create_request(self, *args, **kwargs):
        request = self.api.create_request(*args, **kwargs)
        self._last_pgpool_update = time.time()
        return PGoRequestWrapper(request, self.needs_pgpool_update())

    def is_logged_in(self):
        # Logged in? Enough time left? Cool!
        if self.api.get_auth_provider() and self.api.get_auth_provider().has_ticket():
            remaining_time = self.api.get_auth_provider()._ticket_expire / 1000 - time.time()
            return remaining_time > 60
        return False

    def is_banned(self):
        return self._bad_request_ban or self._player_state.get('banned', False)

    def needs_pgpool_update(self):
        return self._pgpool_auto_update_enabled and (
            time.time() - self._last_pgpool_update >= 60)

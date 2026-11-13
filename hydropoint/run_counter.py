# run counter kept in an Upstash Redis database (REST API).
# needs [upstash] url and token in the Streamlit secrets, or the environment variables
# UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN. Without them no count is shown

import os

import requests

RUN_KEY = 'hydropoint_run_count'
TIMEOUT_SECONDS = 5


def _config():
    # (url, token), or None if not set
    url = os.environ.get('UPSTASH_REDIS_REST_URL')
    token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    if not (url and token):
        try:
            import streamlit as st
            url = st.secrets['upstash']['url']
            token = st.secrets['upstash']['token']
        except Exception:
            return None
    if not (url and token):
        return None
    return url.rstrip('/'), token


def _command(*parts):
    # one REST command, returns its result
    config = _config()
    if config is None:
        raise RuntimeError('run counter is not configured')
    url, token = config
    endpoint = url + '/' + '/'.join(str(p) for p in parts)
    response = requests.get(endpoint, headers={'Authorization': f'Bearer {token}'},
                            timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get('result')


def increment_runs(key=RUN_KEY):
    # add one and return the new total, or None
    try:
        result = _command('incr', key)
        return int(result) if result is not None else None
    except Exception:
        return None


def get_runs(key=RUN_KEY):
    # current total (0 if never set), or None if the counter is unavailable
    try:
        result = _command('get', key)
    except Exception:
        return None
    return int(result) if result not in (None, '') else 0

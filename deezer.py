import logging
import requests
from data import config

logger = logging.getLogger('DeezerSync')

deezer_request = None

def get_deezer_request():
    global deezer_request
    if deezer_request is None:
        deezer_request = requests.Session()
    
    return deezer_request

def get_playlists():
    request = get_deezer_request().get('https://api.deezer.com/user/{}/playlists'.format(config['deezer']['user_id']))

    if request.status_code == 200:
        contents = request.json()
        return contents['data']
    else:
        logger.error('Failed to load contents from Deezer')
        return []

def get_playlist_isrcs(tracklist_url):
    has_next = True
    isrcs = {}

    while has_next:
        #logger.debug('Loading from tracklist [%s]', tracklist_url)

        tracklist_request = get_deezer_request().get(tracklist_url)
        if tracklist_request.status_code == 200:
            tracklist = tracklist_request.json()

            if 'next' in tracklist:
                tracklist_url = tracklist['next']
            else:
                has_next = False
                
            for track in tracklist['data']:
                if 'artist' in track and 'title' in track['artist']:
                    isrcs[track['isrc']] = '{0} / {1}'.format(track['title'], track['artist']['title'])
                else:
                    isrcs[track['isrc']] = '{0}'.format(track['title'])
        else:
            logger.error('Failed to load track list from playlist')

    return isrcs


def get_favorite_isrcs():
    # Get favorite playlists
    request = get_deezer_request().get('https://api.deezer.com/user/{}/playlists'.format(config['deezer']['user_id']))
    isrcs = {}

    if request.status_code == 200:
        contents = request.json()

        # Iterate over playlists to find the favorites
        loved_playlist_id = None
        tracklist_url = None
        for playlist in contents['data']:
            logger.debug('Found playlist [{}] - [{}]'.format(playlist['title'], playlist['id']))
            if playlist['is_loved_track'] and loved_playlist_id is None:
                loved_playlist_id = playlist['id']
                tracklist_url = playlist['tracklist']
        
        logger.info('Found loved playlist [%s]', loved_playlist_id)
        if loved_playlist_id is not None:
            has_next = True

            while has_next:
                #logger.debug('Loading from tracklist [%s]', tracklist_url)

                tracklist_request = get_deezer_request().get(tracklist_url)
                if tracklist_request.status_code == 200:
                    tracklist = tracklist_request.json()

                    if 'next' in tracklist:
                        tracklist_url = tracklist['next']
                    else:
                        has_next = False
                        
                    for track in tracklist['data']:
                        if 'artist' in track and 'title' in track['artist']:
                            isrcs[track['isrc']] = '{0} / {1}'.format(track['title'], track['artist']['title'])
                        else:
                            isrcs[track['isrc']] = '{0}'.format(track['title'])
                else:
                    logger.error('Failed to load track list from playlist')
        else:
            logger.error('Couldn\'t find Deezer loved playlist')
    else:
        logger.error('Failed to load contents from Deezer')

    return isrcs
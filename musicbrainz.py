import requests
import time
import logging

logger = logging.getLogger('MusicBrainz')

musicbrainz_request = None
def get_musicbrainz_request():
    global musicbrainz_request
    if musicbrainz_request is None:
        musicbrainz_request = requests.Session()
        musicbrainz_request.headers.update({'Accept': 'application/json', 'User-Agent': 'Deezer-Jellyfin-Sync/0.0.1 ( deezer-jellyfin@pendracast.fr )'})
    
    return musicbrainz_request

def get_musicbrainz_recording(isrc):
    time.sleep(1)
    mb_recording_request = get_musicbrainz_request().get('https://musicbrainz.org/ws/2/recording?query=isrc:{}'.format(isrc))
    recording = None

    if mb_recording_request.status_code == 200:
        mb_recording_response = mb_recording_request.json()
        if mb_recording_response['count'] >= 1:
            recording = {}
            mb_recording = mb_recording_response['recordings'][0]
            logger.debug('Found match for isrc [%s] corresponding to recording [%s]', isrc, mb_recording['id'])
            recording['id'] = mb_recording['id']
            # Fill in artist credit, only consider first artist for now
            recording['artist'] = mb_recording['artist-credit'][0]['artist']['id']
            # Get to know every album / track ID in which the recording is
            recording['releases'] = []
            for mb_release in mb_recording['releases']:
                # Simplify as much as possible, get the first track of the first media found
                release = {
                    'id': mb_release['id'],
                    'group-id': mb_release['release-group']['id'],
                    'track': mb_release['media'][0]['track'][0]['id']
                }
                recording['releases'].append(release)
    else:
        logger.error('Failed to perform request to MusicBrainz')

    return recording

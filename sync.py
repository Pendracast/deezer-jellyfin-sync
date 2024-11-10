import jellyfin
import deezer
import musicbrainz
import lidarr
import logging
import sys
from data import config, mapping, persist_mapping

def init_logger(logLevel):
    root = logging.getLogger()

    if (logLevel >= 1):
        root.setLevel(logging.DEBUG)
    else:
        root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[ %(levelname)s ] %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

def consolidate_isrc(isrc, track_info):
    if isrc not in mapping or (isrc in mapping and 'jellyfin_id' not in mapping[isrc]):
        logger.info('[%s] (%s) not mapped', isrc, track_info)

        if isrc not in mapping:
            mapping[isrc] = {}
        
        # Define if we need to resolve the recording
        if 'musicbrainz' not in mapping[isrc]:
            recording = musicbrainz.get_musicbrainz_recording(isrc)
            if recording is not None:
                mapping[isrc]['musicbrainz'] = recording
                persist_mapping()
        
        if 'musicbrainz' in mapping[isrc]:
            recording = mapping[isrc]['musicbrainz']
            if recording['artist'] in jellyfin_artists:
                logger.debug('Artist [%s] exists for isrc [%s]', recording['artist'], isrc)

                for release in recording['releases']:
                    logger.debug('Checking release %s ; track %s', release['id'], release['track'])
                    track = jellyfin.get_jellyfin_track(jellyfin_artists[recording['artist']], release['track'])
                    if track is not None:
                        logger.info('Found correlation between isrc [%s] and track [%s] (%s)', isrc, track, track_info)
                        mapping[isrc]['jellyfin_id'] = track
                        # We'll still re-save at the end, but it can be interesting to have an intermediate save here
                        # so that any cancelling doesn't screw up the whole mapping
                        persist_mapping()
                        return True
                if isrc not in mapping:
                    logger.error('Track for isrc [%s] (%s) not found in Jellyfin', isrc, track_info)
            else:
                logger.error('Artist for isrc [%s] (%s) not found in Jellyfin', isrc, track_info)

            # At this point we have not found any mapping, let's try through Lidarr
            lidarr.request_releases(recording, track_info)

        else:
            logger.error('Couldn\'t find MusicBrainz track for isrc [%s] (%s)', isrc, track_info)
    else:
        logger.info('[%s] already mapped', track_info)
        return True
    
    return False

def synchronize_playlist(playlist, tracklist_url):
    logger.info('Synchronizing playlist [{}] to [{}] ...'.format(playlist['deezer_name'], playlist['jellyfin_name']))
    isrcs = deezer.get_playlist_isrcs(tracklist_url)
    playlist_tracks = []

    logger.info('Matching each track with a corresponding record in Jellyfin ...')
    for isrc in isrcs.keys():
        if consolidate_isrc(isrc, isrcs[isrc]):
            playlist_tracks.append(mapping[isrc]['jellyfin_id'])
        #if not consolidate_isrc(isrc):
        #    musicbrainz.get_musicbrainz_recording(isrc)
    #logger.info("Got the following tracks :")
    #for track in playlist_tracks:
    #    logger.info(track)

    jellyfin.create_or_update_playlist(playlist['jellyfin_name'], playlist_tracks)
    persist_mapping()

init_logger(0)

logger = logging.getLogger('Sync')

logger.info('Loading known artists in Jellyfin ...')
jellyfin_artists = jellyfin.get_jellyfin_artists()

logger.info('Loading known playlists ...')
known_deezer_playlists = {}
for playlist in config['playlists']:
    known_deezer_playlists[playlist['deezer_name']] = playlist

logger.info('Loading Deezer playlists ...')
for playlist in deezer.get_playlists():
    if playlist['title'] in known_deezer_playlists:
        synchronize_playlist(known_deezer_playlists[playlist['title']], playlist['tracklist'])
    else:
        logger.info('Ignoring playlist [{}] as it is not mapped'.format(playlist['title']))
import logging
import requests
import sys
import json
from data import config

logger = logging.getLogger('JellyfinSync')

# Define a map containing a list fo known albums for a given artist in Jellyfin
# this allows to limit the number of queries made (we only request the list of albums for a given artist once per sync)
known_artist_albums = {}
# Similar cache for albums
known_album_tracks = {}

# Cache for playlists
known_playlists = None

jellyfin_authorization_header = 'MediaBrowser Token="{}", Client="Jellyfin Sync"'.format(config['jellyfin']['token'])
jellyfin_request_headers = {'Authorization': jellyfin_authorization_header}
jellyfin_request = None

def get_jellyfin_request():
    global jellyfin_request
    if jellyfin_request is None:
        jellyfin_request = requests.Session()
        jellyfin_request.headers.update(jellyfin_request_headers)

    return jellyfin_request

def get_jellyfin_artists():
    artists_request = get_jellyfin_request().get(
        '{0}/Artists?fields=ExtraIds&enableImages=false&enableTotalRecordCount=false&fields=ProviderIds'.format(config['jellyfin']['url']))

    artists_mapping = {}

    if artists_request.status_code == 200:
        artists = artists_request.json()
        for artist in artists['Items']:
            if 'MusicBrainzArtist' in artist['ProviderIds']:
                musicbrainz_id = artist['ProviderIds']['MusicBrainzArtist']
                #logger.debug('ID:%s\tMBID:%s\tName:%s', artist['Id'], musicbrainz_id, artist['Name'])
                artists_mapping[musicbrainz_id] = artist['Id']
            else:
                logger.error('Unknown MBID for artist [%s]', artist['Name'])
    else:
        logger.error('Failed to perform request to Jellyfin')
    
    return artists_mapping

def get_jellyfin_track(artist_id, track_mb_id):
    jellyfin_albums = []

    if artist_id in known_artist_albums:
        jellyfin_albums = known_artist_albums[artist_id]
    else:
        logger.debug('Loading albums for artist [%s]', artist_id)
        albums_request = get_jellyfin_request().get(
            '{0}/Items?IncludeItemTypes=MusicAlbum&Recursive=true&CollapseBoxSetItems=false&AlbumArtistIds={1}'.format(config['jellyfin']['url'], artist_id))

        if albums_request.status_code == 200:
            albums = albums_request.json()
            for album in albums['Items']:
                jellyfin_albums.append(album['Id'])
            known_artist_albums[artist_id] = jellyfin_albums
        else:
            logger.error('Failed to communicate with Jellyfin : [%s]', albums_request.status_code)
        
    logger.debug('Known albums for artist [%s] : [%s]', artist_id, jellyfin_albums)
    
    for jellyfin_album in jellyfin_albums:
        if jellyfin_album in known_album_tracks:
            tracks = known_album_tracks[jellyfin_album]
        else:
            tracks = get_tracks_from_parent(jellyfin_album)
            known_album_tracks[jellyfin_album] = tracks

        if tracks is not None:
            for track in tracks:
                if track['mb_id'] == track_mb_id:
                    logger.debug('Found correlation for track %s', track['id'])
                    return track['id']
        
    return None

def get_tracks_from_parent(parent_id, tracks = []):
    contents_request = get_jellyfin_request().get(
        '{0}/Items?SortBy=ParentIndexNumber,IndexNumber,SortName&fields=ProviderIds&ParentId={1}'.format(config['jellyfin']['url'], parent_id),
        headers=jellyfin_request_headers)
        
    if contents_request.status_code == 200:
        contents = contents_request.json()
        #logger.debug('Track request : [%s]', contents_request.text)
        for content in contents['Items']:
            if content['IsFolder']:
                get_tracks_from_parent(content['Id'], tracks)
            elif 'ProviderIds' in content and 'MusicBrainzTrack' in content['ProviderIds']:
                tracks.append({
                    'mb_id': content['ProviderIds']['MusicBrainzTrack'],
                    'id': content['Id']
                })
    return tracks

def load_playlists_mapping():
    global known_playlists

    playlists_request = get_jellyfin_request().get(
        '{}/Items?IncludeItemTypes=Playlist&Recursive=true'.format(config['jellyfin']['url']),
        headers = jellyfin_request_headers)
    
    if playlists_request.status_code == 200:
        playlists = playlists_request.json()
        known_playlists = {}

        for playlist in playlists['Items']:
            known_playlists[playlist['Name']] = playlist['Id']

def create_or_update_playlist(playlist_name, tracks):
    if known_playlists is None:
        load_playlists_mapping()

    if (playlist_name in known_playlists.keys()):
        get_jellyfin_request().delete('{}/Items/{}'.format(config['jellyfin']['url'], known_playlists[playlist_name]), headers = jellyfin_request_headers)
        load_playlists_mapping()

    logger.debug(jellyfin_request.headers)
    get_jellyfin_request().post(
        '{}/Playlists'.format(config['jellyfin']['url']),
        data = json.dumps({
            'Name': playlist_name,
            'Ids': tracks,
            'UserId': config['jellyfin']['user_id'],
            'MediaType': 'Audio'
        }),
        headers = {
            'Content-Type': 'application/json',
            'Authorization': jellyfin_authorization_header
        }
    )

import requests
import logging
import json
from data import config
from tabulate import tabulate

logger = logging.getLogger('Lidarr')


lidarr_request_header = {'X-Api-Key': config['lidarr']['token'], 'Content-Type': 'application/json'}
lidarr_request = None

def get_lidarr_request():
    global lidarr_request
    if lidarr_request is None:
        lidarr_request = requests.Session()
        lidarr_request.headers.update(lidarr_request_header)
    return lidarr_request

def request_releases(recording, track_info):
    # Check if any of the releases is already being monitored
    release_monitored = None
    release_groups_already_checked = []
    logger.debug('Checking if one release is already monitored for recording [%s] (artist [%s])', recording['id'], recording['artist'])
    for mb_release in recording['releases']:
        if release_monitored is None and mb_release['group-id'] not in release_groups_already_checked:
            release_response = get_lidarr_request().get('{0}/api/v1/album?foreignAlbumId={1}&includeAllArtistAlbums=false'.format(config['lidarr']['url'], mb_release['group-id']))
            if release_response.status_code == 200 and len(release_response.json()) > 0:
                release_monitored = mb_release
            elif release_response.status_code != 200:
                logger.error('Failed to fetch release information from Lidarr, status code [%s]', release_response.status_code)
            release_groups_already_checked.append(mb_release['group-id'])
    
    if release_monitored is None:
        logger.debug('No release monitored, displaying options ...')
        available_release_groups = []
        available_release_groups_display = []
        release_group_counter = 0
        # We'll need to provide information to choose which album to download
        for release_group_id in release_groups_already_checked:
            logger.debug('Fetching details for release group [%s]', release_group_id)
            # In all theory this should yield only one release group
            lookup_response = get_lidarr_request().get('{0}/api/v1/album/lookup?term=lidarr:{1}'.format(config['lidarr']['url'], release_group_id))
            if lookup_response.status_code == 200:
                if len(lookup_response.json()) > 1:
                    logger.error('[%s] release groups found instead of 1 for [%s]', len(lookup_response.json()), release_group_id)
                elif len(lookup_response.json()) == 0:
                    logger.error('No release group found for [%s]', release_group_id)
                else:
                    release_group = lookup_response.json()[0]
                    available_release_groups.append(release_group)
                    available_release_groups_display.append([
                        release_group_counter,
                        release_group['title'],
                        release_group['disambiguation'],
                        release_group['monitored'],
                        release_group['anyReleaseOk'],
                        release_group['albumType']
                    ])
                    release_group_counter += 1
        
        if len(available_release_groups) == 1:
            logger.info('Only one release group available for this track, requesting it ...')
            monitor_release_group(available_release_groups[0])
        else:
            print('Available release groups for [{0}]'.format(track_info))
            print(tabulate(available_release_groups_display))
            selection = int(input('Selected release group (between 0 and {0}) ; use any number out of range to cancel : '.format(len(available_release_groups)-1)))
            if selection >= 0 and selection < len(available_release_groups):
                print('Monitoring release group [{0}]'.format(selection))
                monitor_release_group(available_release_groups[selection])
    else:
        logger.debug('Release [%s] is already monitored, skipping as download may already be in progress ...', release_monitored)

def monitor_release_group(release_group):
    # Update the release group to have additional album options
    release_group['addOptions'] = {
        'addType': 'automatic',
        'searchForNewAlbum': False
    }
    release_group['monitored'] = True
    release_group['artist']['monitored'] = True
    release_group['artist']['monitorNewItems'] = 'none'
    release_group['artist']['qualityProfileId'] = config['lidarr']['quality_profile_id']
    release_group['artist']['metadataProfileId'] = config['lidarr']['metadata_profile_id']
    release_group['artist']['addOptions'] = {
        'monitor': 'existing',
        'searchForMissingAlbums': True
    }
    if 'folder' not in release_group['artist']:
        release_group['artist']['folder'] = release_group['artist']['artistName']
    if 'rootFolderPath' not in release_group['artist']:
        release_group['artist']['rootFolderPath'] = config['lidarr']['root_folder_path']

    logger.debug('Release group sent to the Lidarr : [%s]', json.dumps(release_group))
    monitor_request = get_lidarr_request().post('{0}/api/v1/album'.format(config['lidarr']['url']), data=json.dumps(release_group))
    if monitor_request.status_code == 200 or monitor_request.status_code == 201:
        logger.info('Started monitoring release group [%s]', release_group['title'])
        monitor_put_request = get_lidarr_request().put('{0}/api/v1/album/monitor'.format(config['lidarr']['url']), data=json.dumps({
            'albumIds': [
                monitor_request.json()['id']
            ],
            'monitored': True
        }))
        # Next step is to send a PUT request to monitor the album ID
        if monitor_put_request.status_code == 202:
            logger.info('Success !')
        else:
            logger.info('Error')
            logger.debug('Response text : [%s]', monitor_put_request.text)

    else:
        logger.error('Incorrect monitor response code : [%s]', monitor_request.status_code)


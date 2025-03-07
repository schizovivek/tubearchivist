# TubeArchivist API
Documentation of available API endpoints.  
**Note: This is very early alpha and will change!**

## Authentication
API token will get automatically created, accessible on the settings page. Token needs to be passed as an authorization header with every request. Additionally session based authentication is enabled too: When you are logged into your TubeArchivist instance, you'll have access to the api in the browser for testing.

Curl example:
```shell
curl -v /api/video/<video-id>/ \
    -H "Authorization: Token xxxxxxxxxx"
```

Python requests example:
```python
import requests

url = "/api/video/<video-id>/"
headers = {"Authorization": "Token xxxxxxxxxx"}
response = requests.get(url, headers=headers)
```

## Video Item View
/api/video/\<video_id>/

## Channel List View
/api/channel/

### Subscribe to a list of channels
POST /api/channel/
```json
{
    "data": [
        {"channel_id": "UC9-y-6csu5WGm29I7JiwpnA", "channel_subscribed": true}
    ]
}
```

## Channel Item View
/api/channel/\<channel_id>/

## Playlists Item View
/api/playlist/\<playlist_id>/

## Download Queue List View
/api/download/

### Add list of videos to download queue
POST /api/download/
```json
{
    "data": [
        {"youtube_id": "NYj3DnI81AQ", "status": "pending"}
    ]
}
```

## Download Queue Item View
/api/download/\<video_id>/

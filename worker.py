import json
import os
import requests
from pymongo import ReadPreference
from boto.s3.connection import S3Connection
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.key import Key
import datetime
import random
import tweepy
import oauthlib
from time import sleep
import traceback
from models import Photo
from mongoengine import connect

TAGS = ['ifeelnaked']
INSTAGRAM_ENDPOINT = 'https://api.instagram.com/v1/tags/ifeelnaked/media/recent'

# connect to the database
connect(
    os.environ.get('MONGODB_NAME'),
    host=os.environ.get('MONGODB_HOST'),
    port=int(os.environ.get('MONGODB_PORT')),
    username=os.environ.get('MONGODB_USERNAME'),
    password=os.environ.get('MONGODB_PASSWORD'),
    read_preference=ReadPreference.PRIMARY
)

# connect to Amazon S3
conn = S3Connection(os.environ.get('AWS_ACCESS_KEY'), 
                    os.environ.get('AWS_SECRET_KEY'),
                    calling_format=OrdinaryCallingFormat())
bucket = conn.get_bucket(os.environ.get('AWS_S3_BUCKET'))
bucket_url = "https://%s" % os.environ.get('AWS_S3_BUCKET')

def populate_from_instagram(tag):
    """
    Pulls in posts for a given tag from Instagram API and enters into the db.
    Either exhausts the MAX_API_CALLS limit or stops when it reaches a post that
    already exists in the db.
    """
    print "----------------------------------------------------------------"
    print "Calling Instagram API..."

    params = {'client_id': os.environ.get('INSTAGRAM_CLIENT_ID')}
    r = requests.get(INSTAGRAM_ENDPOINT, params=params).json()
    
    if not r.get('pagination') or not r.get('pagination').get('min_tag_id'):
        print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        print "INSTAGRAM API FAILURE: %s" % r
        print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        send_failure_message("Instagram API failure: %r" % r)
        return

    for item in r.get('data'):
        print "  - id: %s" % item.get('id')

        username    = item.get('user').get('username')
        user_id     = item.get('user').get('id')
        user_avatar = item.get('user').get('profile_picture')
        photo_id    = str(item.get('id'))
        photo_url = item.get('images').get('standard_resolution').get('url')

        # bail if we reach a photo that already exists in the database.
        existing = Photo.objects(source='instagram', source_id=photo_id)
        if len(existing):
            print "    --- Ran into an image we already have. Ending :) ---"
            return

        # save avatar to s3
        avatar = requests.get(user_avatar).content
        k = Key(bucket)
        k.key = "avatars/%s.jpg" % user_id
        k.delete()
        k.set_metadata('Content-Type', 'image/jpeg')
        k.set_contents_from_string(avatar)
        k.set_acl('public-read')
        user_avatar_s3 = "%s/avatars/%s.jpg" % (bucket_url, user_id)

        # save photo to s3
        photo = requests.get(photo_url).content
        k = Key(bucket)
        k.key = "photos/%s.jpg" % photo_id
        k.delete()
        k.set_metadata('Content-Type', 'image/jpeg')
        k.set_contents_from_string(photo)
        k.set_acl('public-read')
        photo_url_s3 = "%s/photos/%s.jpg" % (bucket_url, photo_id)

        photo = Photo(
            source          = 'instagram',
            source_id       = photo_id,
            username        = username,
            user_avatar     = user_avatar,
            user_avatar_s3  = user_avatar_s3,
            photo_url       = photo_url,
            photo_url_s3    = photo_url_s3,
            original_url    = item.get('link'),
            caption         = item.get('caption').get('text'),
            visible         = False,
            priority        = 0,
            random_index    = random.randint(0, 2147483647),
            created         = datetime.datetime.now()
            )
        photo.save()
        

def populate_from_twitter(tag):
    """
    Pulls in posts for a given tag from Instagram API and enters into the db.
    Either exhausts the MAX_API_CALLS limit or stops when it reaches a post that
    already exists in the db.
    """
    print "----------------------------------------------------------------"
    print "Calling Twitter API..."

    client = oauthlib.oauth1.Client(os.environ.get('TWITTER_API_KEY'),
        client_secret=os.environ.get('TWITTER_API_SECRET'),
        resource_owner_key=os.environ.get('TWITTER_TOKEN'),
        resource_owner_secret=os.environ.get('TWITTER_TOKEN_SECRET')
    )
    u = 'https://api.twitter.com/1.1/search/tweets.json?q=%%23%s&count=100'% tag
    uri, headers, body = client.sign(u)

    try:
        response = requests.get(uri, headers=headers)

    except:
        print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        print "TWITTER API FAILURE: %s" % response.content
        print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        raise
        return

    response = response.json()

    if not response.get('statuses'):
        print "No results :("
        return

    i = 0

    for item in response.get('statuses'):

        if not (item.get('entities') and item.get('entities').get('media') and \
                len(item.get('entities').get('media')) and \
                item.get('entities').get('media')[0].get('type') == 'photo'):
            print "  - (skipping)"
            continue

        if item.get('retweeted_status'):
            print '  - (skipping retweet)'
            continue

        print "  - id: %s" % item.get('id')

        username    = item.get('user').get('screen_name')
        user_id     = item.get('user').get('id')
        user_avatar = item.get('user').get('profile_image_url')
        photo_id    = str(item.get('id'))
        photo_url   = item.get('entities').get('media')[0].get('media_url')
        display_url = item.get('entities').get('media')[0].get('display_url')

        # bail if we reach a photo that already exists in the database.
        existing = Photo.objects(source='twitter', source_id=photo_id)
        if len(existing):
            print "    --- Ran into an image we already have. Ending :) ---"
            break

        # save avatar to s3
        avatar = requests.get(user_avatar).content
        k = Key(bucket)
        k.key = "avatars/%s.jpg" % user_id
        k.delete()
        k.set_metadata('Content-Type', 'image/jpeg')
        k.set_contents_from_string(avatar)
        k.set_acl('public-read')
        user_avatar_s3 = "%s/avatars/%s.jpg" % (bucket_url, user_id)

        # save photo to s3
        photo = requests.get(photo_url).content
        k = Key(bucket)
        k.key = "photos/%s.jpg" % photo_id
        k.delete()
        k.set_metadata('Content-Type', 'image/jpeg')
        k.set_contents_from_string(photo)
        k.set_acl('public-read')
        photo_url_s3 = "%s/photos/%s.jpg" % (bucket_url, photo_id)

        photo = Photo(
            source            = 'twitter',
            source_id         = photo_id,
            username          = username,
            user_avatar       = user_avatar,
            user_avatar_s3    = user_avatar_s3,
            photo_url         = photo_url,
            photo_url_s3      = photo_url_s3,
            photo_display_url = display_url,
            original_url      = 'https://twitter.com/%s/status/%s' % (username,
                                photo_id),
            caption           = item.get('text'),
            visible           = False,
            priority          = 0,
            random_index      = random.randint(0, 2147483647),
            created           = datetime.datetime.now()
            )
        photo.save()
        i = i + 1
        if i == 14:
            send_failure_message("Twitter API spider is overloaded.","OVERLOAD")

def send_failure_message(message, subject="#ifeelnaked scraper error"):
    data = {
        "to": "jeff@fightforthefuture.org",
        "subject": subject,
        "text": message,
        "from": "jeff@fightforthefuture.org",
        "fromname": "#ifeelnaked",
        "api_user": os.environ.get('SENDGRID_USERNAME').strip(),
        "api_key": os.environ.get('SENDGRID_PASSWORD').strip()
    }
    # requests.post('https://api.sendgrid.com/api/mail.send.json', data=data)

def spider():
    for tag in TAGS:
        try:
            populate_from_instagram(tag)
        except Exception, err:
            send_failure_message("Instagram fail: %r" % traceback.format_exc())
            print traceback.format_exc()

        try:
            populate_from_twitter(tag)
        except Exception, err:
            send_failure_message("Twitter API fail: %r" %traceback.format_exc())
            print traceback.format_exc()

    print "Sleep, Data."
    sleep(len(TAGS)*5)
    spider()

spider()



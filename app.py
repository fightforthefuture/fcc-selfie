# handle imports
import os, time
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash, jsonify, Response, send_from_directory
from access_control_decorator import crossdomain
from pymongo import ReadPreference
from mongoengine import connect
from models import Selfie
import random

# create flask application
app = Flask(__name__)
app.config.from_object(__name__)
app.config.update(dict(
    JSON_AS_ASCII=False
))
app.config.from_object('config.Config')

# connect to the database
connect(
    os.environ.get('MONGODB_NAME'),
    host=os.environ.get('MONGODB_HOST'),
    port=int(os.environ.get('MONGODB_PORT')),
    username=os.environ.get('MONGODB_USERNAME'),
    password=os.environ.get('MONGODB_PASSWORD'),
    read_preference=ReadPreference.PRIMARY
)

def fix_ip(ip_address):
    """Fixes an ugly, broken IP address string that came from Heroku"""

    if "," in ip_address:
        ips = ip_address.split(", ")
        ip_address = ips[0]

    return ip_address

@app.route('/')
def index():
    """Render the main site"""

    return render_template('index.html', FB_IMAGE_URL=get_facebook_image(),
                LOAD_PHOTO='');

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/photo/<permalink_slug>')
def photo(permalink_slug):
    """Render the main site with a special photo for Facebook's scraper"""

    override_image = get_facebook_image()

    try:
        photo = Selfie.objects.get(permalink_slug=permalink_slug)
        override_image = photo.photo_url_s3

        if request.values.get('return') == 'json':
            return photo.to_json();
    except:
        if request.values.get('return') == 'json':
            return '{"error": true}'
    
    return render_template('index.html', FB_IMAGE_URL=override_image,
                LOAD_PHOTO=permalink_slug);


@app.route('/base64', methods=['POST', 'GET'])
@crossdomain(origin='*')
def report():
    """Add a base64 image"""

    import base64
    import uuid
    import PIL
    from PIL import Image, ExifTags
    import tweepy
    import json
    from boto.s3.connection import S3Connection
    from boto.s3.connection import OrdinaryCallingFormat
    from boto.s3.key import Key
    import datetime
    import requests

    img_data = request.values.get('img_data')

    # try:
    decoded = base64.b64decode(img_data)

    filename = ("%s" % uuid.uuid4())[0:8]

    with open("/tmp/%s.png" % filename, 'wb') as f:
        f.write(decoded)

    im      = Image.open("/tmp/%s.png" % filename)

    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation]=='Orientation':
                break
        exif=dict(im._getexif().items())

        if exif[orientation] == 3:
            im=im.rotate(180, expand=True)
        elif exif[orientation] == 6:
            im=im.rotate(270, expand=True)
        elif exif[orientation] == 8:
            im=im.rotate(90, expand=True)

    except (AttributeError, KeyError, IndexError):
        # cases: image don't have getexif
        pass


    maxsize = (float(620), float(620))
    size    = (float(im.size[0]), float(im.size[1]))
    scale   = "down"

    if size[0] < maxsize[0] or size[1] < maxsize[1]:
        scale = "up"
    
    if size[0] < size[1]:
        newsize = (maxsize[0], maxsize[1] * (size[1]/size[0]))
    else:
        newsize = (maxsize[0] * (size[0]/size[1]), maxsize[1])

    crop = (
            int((newsize[0] - maxsize[0])/2),
            int((newsize[1] - maxsize[1])/2),
            int((newsize[0] + maxsize[0])/2),
            int((newsize[1] + maxsize[1])/2)
           )

    newsize = (int(newsize[0]), int(newsize[1]))

    im = im.resize(newsize, PIL.Image.ANTIALIAS)
    im = im.crop(crop)

    img_overlay_file = "images/transparent.png"
    tweet_string = '#IVOTED'

    foreground = Image.open(img_overlay_file)
    im.paste(foreground, (0, 0), foreground)

    im.save("/tmp/%s.png" % filename)

    auth = tweepy.OAuthHandler(os.environ.get('TWITTER_API_KEY'),
            os.environ.get('TWITTER_API_SECRET'))
    auth.set_access_token(os.environ.get('TWITTER_TOKEN'), 
            os.environ.get('TWITTER_TOKEN_SECRET'))

    api = tweepy.API(auth)
    r = api.update_with_media("/tmp/%s.png"%filename, (u"#NetNeutrality is not "
        u"a partisan issue. We still need Title II to stop ISPs from censoring "
        u"the Internet!"))

    item = r._json

    conn = S3Connection(os.environ.get('AWS_ACCESS_KEY'), 
                    os.environ.get('AWS_SECRET_KEY'),
                    calling_format=OrdinaryCallingFormat())
    bucket = conn.get_bucket(os.environ.get('AWS_S3_BUCKET'))
    bucket_url = "https://%s.s3.amazonaws.com" % os.environ.get('AWS_S3_BUCKET')

    username       = item.get('user').get('screen_name')
    user_id        = item.get('user').get('id')
    user_avatar    = item.get('user').get('profile_image_url')
    photo_id       = str(item.get('id'))
    photo_url      = item.get('entities').get('media')[0].get('media_url')
    display_url    = item.get('entities').get('media')[0].get('display_url')
    user_avatar_s3 = "%s/avatars/%s.jpg" % (bucket_url, user_id)
    photo_url_s3   = "%s/photos/%s.png" % (bucket_url, photo_id)

    photo = Selfie(
        source              = 'twitter',
        source_id           = photo_id,
        username            = username,
        user_avatar         = user_avatar,
        user_avatar_s3      = user_avatar_s3,
        photo_url           = photo_url,
        photo_url_s3        = photo_url_s3,
        photo_display_url   = display_url,
        original_url        = 'https://twitter.com/%s/status/%s' %(username,
                              photo_id),
        caption             = item.get('text'),
        visible             = False,
        priority            = 0,
        random_index        = random.randint(0, 2147483647),
        permalink_slug      = filename,
        created             = datetime.datetime.now()
        )
    photo.save()

    # save avatar to s3
    avatar = requests.get(user_avatar).content
    k = Key(bucket)
    k.key = "avatars/%s.jpg" % user_id
    k.delete()
    k.set_metadata('Content-Type', 'image/jpeg')
    k.set_contents_from_string(avatar)
    k.set_acl('public-read')
    
    # save photo to s3
    k = Key(bucket)
    k.key = "photos/%s.png" % photo_id
    k.delete()
    k.set_metadata('Content-Type', 'image/png')
    k.set_contents_from_filename("/tmp/%s.png" % filename)
    k.set_acl('public-read')
    # except:
    #     return '{"error": true}'


    return photo.to_json()

def get_facebook_image():
    return os.environ.get('SITE_URL')+'/static/images/laila.jpg'
    
if __name__ == '__main__':
    if app.config['DEBUG'] == True:
        print 'Debug mode active'
        app.run('0.0.0.0', 9001)
    else:
        app.run()

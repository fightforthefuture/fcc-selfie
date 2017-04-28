from mongoengine import connect, Document, StringField, BooleanField, IntField,\
                        DateTimeField

# define our database model
class Selfie(Document):
    source              = StringField()
    source_id           = StringField()
    username            = StringField()
    user_avatar         = StringField()
    user_avatar_s3      = StringField()
    photo_url           = StringField()
    photo_url_s3        = StringField()
    photo_display_url   = StringField()
    original_url        = StringField()
    caption             = StringField()
    permalink_slug      = StringField()
    visible             = BooleanField(required=True, default=False)
    priority            = IntField(required=True, default=0)
    random_index        = IntField(required=True, default=0)
    created             = DateTimeField()
    meta = {
        'indexes': [
            {
                'fields': ['source', '-source_id'],
            },
            {
                'fields': ['visible', '-priority'],
            },
            {
                'fields': ['random_index'],
            },
            {
                'fields': ['permalink_slug'],
            },
        ]
    }
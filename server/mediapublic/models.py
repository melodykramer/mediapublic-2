import six
from uuid import uuid4

import sqlalchemy.exc as sql_exc
from sqlalchemy.sql import func
from sqlalchemy_utils import UUIDType
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    UnicodeText,
    DateTime,
)

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    relationship,
    scoped_session,
    sessionmaker,
)

from zope.sqlalchemy import ZopeTransactionExtension
import transaction

DBSession = scoped_session(sessionmaker(
    extension=ZopeTransactionExtension(),
    expire_on_commit=False))
Base = declarative_base()


class TimeStampMixin(object):
    creation_datetime = Column(DateTime, server_default=func.now())
    modified_datetime = Column(DateTime, server_default=func.now())


class CreationMixin():
    @classmethod
    def add(cls, **kwargs):
        with transaction.manager:
            thing = cls(**kwargs)
            if thing.id is None:
                thing.id = uuid4()
            DBSession.add(thing)
            transaction.commit()
        return thing

    @classmethod
    def get_all(cls):
        with transaction.manager:
            things = DBSession.query(
                cls,
            ).all()
        return things

    @classmethod
    def get_by_id(cls, id):
        with transaction.manager:
            try:
                thing = DBSession.query(
                    cls,
                ).filter(
                    cls.id == id,
                ).first()
            except sql_exc.StatementError as e:
                if isinstance(e.orig, (ValueError,)):
                    raise e.orig
                six.reraise(*sys.exc_info())
        return thing

    @classmethod
    def delete_by_id(cls, id):
        with transaction.manager:
            thing = cls.get_by_id(id)
            if thing is not None:
                DBSession.delete(thing)
            transaction.commit()
        return thing

    @classmethod
    def update_by_id(cls, id, **kwargs):
        with transaction.manager:
            keys = set(cls.__dict__)
            thing = cls.get_by_id(id)
            if thing is not None:
                for k in kwargs:
                    if k in keys:
                        setattr(thing, k, kwargs[k])
                DBSession.add(thing)
                transaction.commit()
        return thing

    @classmethod
    def reqkeys(cls):
        keys = []
        for key in cls.__table__.columns:
            if '__required__' in type(key).__dict__:
                keys.append(str(key).split('.')[1])
        return keys

    def to_dict(self):
        return {
            'id': str(self.id),
            'creation_datetime': str(self.creation_datetime),
        }


class UserTypes(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'user_types'

    id = Column(UUIDType(binary=False), primary_key=True)
    name = Column(UnicodeText, nullable=False)
    description = Column(UnicodeText, nullable=False)
    value = Column(Integer, nullable=False)

    def to_dict(self):
        resp = super(UserTypes, self).to_dict()
        resp.update(
            name=self.name,
            description=self.description,
            value=self.value,
        )
        return resp


class Users(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'users'

    id = Column(UUIDType(binary=False), primary_key=True)
    display_name = Column(UnicodeText, nullable=False)
    email = Column(UnicodeText, nullable=False)
    last_longin_datetime = Column(DateTime, server_default=func.now())

    signup_date = Column(DateTime, server_default=func.now())

    twitter_handle = Column(UnicodeText, unique=True)
    twitter_user_id = Column(UnicodeText, unique=True)
    twitter_auth_token = Column(UnicodeText)
    twitter_auth_secret = Column(UnicodeText)
    profile_photo_url = Column(UnicodeText)

    user_type_id = Column(ForeignKey('user_types.id'))
    organization_id = Column(ForeignKey('organizations.id'))

    @classmethod
    def update_social_login(cls, social_uname, auth_info, provider='twitter'):
        try:
            user = Users.add(
                email="%s@%s.social.auth" % (social_uname, provider),
                display_name=auth_info["profile"]["name"]["formatted"],
                twitter_handle=str(social_uname),
                profile_photo_url=auth_info["profile"]["photos"][0]["value"],
                twitter_auth_secret=auth_info[
                    "credentials"]["oauthAccessTokenSecret"],
                twitter_auth_token=auth_info[
                    "credentials"]["oauthAccessToken"],
                twitter_user_id=auth_info["profile"]["accounts"][0]['userid'],
            )
        except sql_exc.IntegrityError:
            with transaction.manager:
                DBSession.query(cls).filter(
                    cls.twitter_handle == str(social_uname),
                ).update(
                    values=dict(
                        twitter_auth_secret=auth_info[
                            "credentials"]["oauthAccessTokenSecret"],
                        twitter_auth_token=auth_info[
                            "credentials"]["oauthAccessToken"],
                        twitter_user_id=auth_info[
                            "profile"]["accounts"][0]['userid'],
                    )
                )
                user = DBSession.query(cls).filter(
                    cls.twitter_handle == str(social_uname)
                ).first()
            return True, user.id

        return False, user.id

    def to_dict(self):
        resp = super(Users, self).to_dict()
        resp.update(
            display_name=self.display_name,
            twitter_handle=self.twitter_handle,
            email=self.email,
            user_type=self.user_type_id,
            organization_id=self.organization_id,
        )
        return resp


class Comments(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'comments'

    id = Column(UUIDType(binary=False), primary_key=True)
    subject = Column(UnicodeText, nullable=False)
    contents = Column(UnicodeText, nullable=False)

    parent_comment_id = Column(ForeignKey('comments.id'), nullable=False)

    author_id = Column(ForeignKey('users.id'), nullable=False)

    organization_id = Column(ForeignKey('organizations.id'), nullable=True)
    people_id = Column(ForeignKey('people.id'), nullable=True)
    recording_id = Column(ForeignKey('recordings.id'), nullable=True)
    howto_id = Column(ForeignKey('howtos.id'), nullable=True)
    blog_id = Column(ForeignKey('blogs.id'), nullable=True)

    def to_dict(self):
        resp = super(Comments, self).to_dict()
        resp.update(
            subject=self.subject,
            contents=self.contents,
            parent_comment_id=self.parent_comment_id,
            author_id=self.author_id,
        )
        return resp

    @classmethod
    def get_by_organization_id(cls, id):
        with transaction.manager:
            comments = DBSession.query(
                Comments,
            ).filter(
                Comments.organization_id == id,
            ).all()
        return comments

    @classmethod
    def get_by_people_id(cls, id):
        with transaction.manager:
            comments = DBSession.query(
                Comments,
            ).filter(
                Comments.people_id == id,
            ).all()
        return comments

    @classmethod
    def get_by_recording_id(cls, id):
        with transaction.manager:
            comments = DBSession.query(
                Comments,
            ).filter(
                Comments.recording_id == id,
            ).all()
        return comments

    @classmethod
    def get_by_howto_id(cls, id):
        with transaction.manager:
            comments = DBSession.query(
                Comments,
            ).filter(
                Comments.howto_id == id,
            ).all()
        return comments

    @classmethod
    def get_by_blog_id(cls, id):
        with transaction.manager:
            comments = DBSession.query(
                Comments,
            ).filter(
                Comments.blog_id == id,
            ).all()
        return comments


class Organizations(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'organizations'

    id = Column(UUIDType(binary=False), primary_key=True)
    short_name = Column(UnicodeText, nullable=False)
    long_name = Column(UnicodeText, nullable=False)
    short_description = Column(UnicodeText, nullable=False)
    long_description = Column(UnicodeText, nullable=False)

    address_0 = Column(UnicodeText, nullable=False)
    address_1 = Column(UnicodeText, nullable=False)
    city = Column(UnicodeText, nullable=False)
    state = Column(UnicodeText, nullable=False)
    zipcode = Column(UnicodeText, nullable=False)

    phone = Column(UnicodeText, nullable=False)
    fax = Column(UnicodeText, nullable=False)
    primary_website = Column(UnicodeText, nullable=False)
    secondary_website = Column(UnicodeText, nullable=False)

    def to_dict(self):
        resp = super(Organizations, self).to_dict()
        resp.update(
            short_name=self.short_name,
            long_name=self.long_name,
            short_description=self.short_description,
            long_description=self.long_description,
            address_0=self.address_0,
            address_1=self.address_1,
            city=self.city,
            state=self.state,
            zipcode=self.zipcode,
            phone=self.phone,
            fax=self.fax,
            primary_website=self.primary_website,
            secondary_website=self.secondary_website,
        )
        return resp


class PlaylistAssignments(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'playlist_assignments'

    id = Column(UUIDType(binary=False), primary_key=True)
    playlist_id = Column(ForeignKey('playlists.id'))
    recording_id = Column(ForeignKey('recordings.id'), nullable=False)

    @classmethod
    def delete_by_playlist_id_and_recording_id(cls, pid, rid):
        success = False
        with transaction.manager:
            playlist = DBSession.query(
                PlaylistAssignments,
            ).filter(
                PlaylistAssignments.playlist_id == pid,
                PlaylistAssignments.recording_id == rid,
            ).first()
            if playlist is not None:
                DBSession.remove(playlist)
                transaction.commit()
                success = True
        return success

    def to_dict(self):
        resp = super(PlaylistAssignments, self).to_dict()
        resp.update(
            playlist_id=self.playlist_id,
            recording_id=self.recording_id,
        )
        return resp


class Playlists(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'playlists'

    id = Column(UUIDType(binary=False), primary_key=True)
    author_id = Column(ForeignKey('people.id'))
    title = Column(UnicodeText, nullable=False)
    description = Column(UnicodeText, nullable=False)

    recordings = relationship(
        "Recordings",
        secondary=PlaylistAssignments.__table__,
        backref="playlists",
    )

    @classmethod
    def get_by_owner_id(cls, id):
        with transaction.manager:
            playlists = DBSession.query(
                Playlists,
            ).filter(
                Playlists.author_id == id,
            ).all()
        return playlists

    @classmethod
    def remove_recording_ny_id(cls, pid, rid):
        with transaction.manager:
            assignment = DBSession.query(
                PlaylistAssignments,
            ).filter(
                PlaylistAssignments.playlist_id == pid,
                PlaylistAssignments.recording_id == rid,
            ).first()
            DBSession.delete(assignment)

    @classmethod
    def get_recordings_by_playlist_id(self, id):
        with transaction.manager:
            recordings = DBSession.query(
                Recordings,
            ).join(
                PlaylistAssignments,
            ).filter(
                PlaylistAssignments.playlist_id == id,
            ).all()
            if recordings is None:
                recordings = []
            if not isinstance(recordings, list):
                recordings = [recordings]
        return recordings

    def to_dict(self):
        resp = super(Playlists, self).to_dict()
        resp.update(
            author_id=self.author_id,
            title=self.title,
            # This should cause a LEFT JOIN against the many-to-many
            # recording_assignments table, and get the recordings
            # that are associated with the playlist
            # recordings = [r.to_dict() for r in self.recordings]
            recordings=[r.to_dict() for r in
                        Playlists.get_recordings_by_playlist_id(self.id)],
        )
        return resp


class People(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'people'

    id = Column(UUIDType(binary=False), primary_key=True)
    first = Column(UnicodeText, nullable=False)
    last = Column(UnicodeText, nullable=False)
    address_0 = Column(UnicodeText, nullable=False)
    address_1 = Column(UnicodeText, nullable=False)
    city = Column(UnicodeText, nullable=False)
    state = Column(UnicodeText, nullable=False)
    zipcode = Column(UnicodeText, nullable=False)
    phone = Column(UnicodeText, nullable=False)
    fax = Column(UnicodeText, nullable=False)
    primary_website = Column(UnicodeText, nullable=False)
    secondary_website = Column(UnicodeText, nullable=False)

    # these should probably be brough out into a seperate table as
    # many to one so we don't have to keep adding columns ...
    twitter = Column(UnicodeText, nullable=False)
    facebook = Column(UnicodeText, nullable=False)
    instagram = Column(UnicodeText, nullable=False)
    periscope = Column(UnicodeText, nullable=False)

    user_id = Column(ForeignKey('users.id'), nullable=False)

    organization_id = Column(ForeignKey('organizations.id'), nullable=True)

    def to_dict(self):
        resp = super(People, self).to_dict()
        resp.update(
            first=self.first,
            address_0=self.address_0,
            address_1=self.address_1,
            city=self.city,
            state=self.state,
            zipcode=self.zipcode,
            phone=self.phone,
            fax=self.fax,
            primary_website=self.primary_website,
            secondary_website=self.secondary_website,

            # see note on definitions
            twitter=self.twitter,
            facebook=self.facebook,
            instagram=self.instagram,
            periscope=self.periscope,
            user_id=str(self.user_id),
            organization_id=str(self.organization_id),
        )
        return resp

    @classmethod
    def get_by_organization_id(cls, id):
        with transaction.manager:
            people = DBSession.query(
                People,
            ).filter(
                People.organization_id == id,
            ).all()
        return people


class Recordings(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'recordings'

    id = Column(UUIDType(binary=False), primary_key=True)
    title = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    recorded_datetime = Column(DateTime)

    organization_id = Column(ForeignKey('organizations.id'))

    def to_dict(self):
        resp = super(Recordings, self).to_dict()
        resp.update(
            title=self.title,
            url=self.url,
            recorded_datetime=str(self.recorded_datetime),
            organization_id=self.organization_id,
        )
        return resp

    @classmethod
    def get_by_organization_id(cls, id):
        with transaction.manager:
            recordings = DBSession.query(
                Recordings,
            ).filter(
                Recordings.organization_id == id,
            ).all()
        return recordings


class RecordingCategories(Base, CreationMixin, TimeStampMixin):

    __tablename__ = 'recording_categories'

    id = Column(UUIDType(binary=False), primary_key=True)
    name = Column(UnicodeText, nullable=False)
    short_description = Column(UnicodeText, nullable=False)
    long_description = Column(UnicodeText, nullable=False)

    def to_dict(self):
        resp = super(RecordingCategories, self).to_dict()
        resp.update(
            name=self.name,
            short_description=self.short_description,
            long_description=self.long_description,
        )
        return resp


class RecordingCategoryAssignments(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'recording_category_assignments'

    id = Column(UUIDType(binary=False), primary_key=True)
    recording_category_id = Column(ForeignKey('recording_categories.id'),
                                   nullable=False)
    recording_id = Column(ForeignKey('recordings.id'), nullable=False)

    def to_dict(self):
        resp = super(RecordingCategoryAssignments, self).to_dict()
        resp.update(
            recording_category_id=self.recording_category_id,
            recording_id=self.recording_id,
        )
        return resp


class Howtos(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'howtos'

    id = Column(UUIDType(binary=False), primary_key=True)
    title = Column(UnicodeText, nullable=False)
    contents = Column(UnicodeText, nullable=False)
    edit_datetime = Column(DateTime)
    tags = Column(UnicodeText, nullable=False)

    def to_dict(self):
        resp = super(Howtos, self).to_dict()
        resp.update(
            title=self.title,
            contents=self.contents,
            edit_datetime=self.edit_datetime,
            tags=self.tags,
        )
        return resp


class HowtoCategories(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'howto_categories'

    id = Column(UUIDType(binary=False), primary_key=True)
    name = Column(UnicodeText, nullable=False)
    short_description = Column(UnicodeText, nullable=False)
    long_description = Column(UnicodeText, nullable=False)

    def to_dict(self):
        resp = super(HowtoCategories, self).to_dict()
        resp.update(
            name=self.name,
            short_description=self.short_description,
            long_description=self.long_description,
        )
        return resp


class HowtoCategoryAssignments(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'howto_category_assignments'

    id = Column(UUIDType(binary=False), primary_key=True)
    howto_category_id = Column(ForeignKey('howto_categories.id'),
                               nullable=False)
    howto_id = Column(ForeignKey('howtos.id'), nullable=False)

    def to_dict(self):
        resp = super(HowtoCategoryAssignments, self).to_dict()
        resp.update(
            howto_category_id=self.howto_category_id,
            howto_id=self.howto_id,
        )
        return resp


class Blogs(Base, CreationMixin, TimeStampMixin):
    __tablename__ = 'blogs'

    id = Column(UUIDType(binary=False), primary_key=True)
    title = Column(UnicodeText, nullable=False)
    contents = Column(UnicodeText, nullable=False)
    edit_datetime = Column(DateTime)
    tags = Column(UnicodeText, nullable=False)

    author_id = Column(ForeignKey('users.id'))

    def to_dict(self):
        resp = super(Blogs, self).to_dict()
        resp.update(
            title=self.title,
            contents=self.contents,
            edit_datetime=self.edit_datetime,
            tags=self.tags,
            author_id=self.author_id,
        )
        return resp

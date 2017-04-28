from app import db as database
from sqlalchemy.orm import relationship
from datetime import datetime


class Item(database.Model):
    __tablename__ = 'items'
    id = database.Column(database.Integer, primary_key=True)
    name = database.Column(database.String())
    url = database.Column(database.String())
    ref_id = database.Column(database.String())
    createdOn = database.Column(database.DateTime, default=datetime.now())

    """docstring for Items"""
    def __init__(self, name, url, ref_id):
        self.name = name
        self.url = url
        self.ref_id = ref_id,


    def __repr__(self):
        return '<id {}>'.format(self.id)




class Review(database.Model):
    __tablename__ = "reviews"
    id = database.Column(database.Integer, primary_key=True)
    user_name = database.Column(database.String)
    review = database.Column(database.String)
    url = database.Column(database.String)
    item_id =  database.Column(database.Integer, database.ForeignKey('items.id'))
    createdOn = database.Column(database.DateTime, default = datetime.now())
    date = database.Column(database.DateTime, default=datetime.now())
    item = relationship(Item)
    star_rating = database.Column(database.String)


    def __init__(self, user_name, review, url, date, star_rating, item_id  ):
        self.user_name = user_name
        self.review = review
        self.url = url
        self.date = date
        self.star_rating =  star_rating,
        self.item_id = item_id

    @property
    def serialize(self):
         """Return object data in easily serializeable format"""
         return {
         "user_name" : self.user_name,
         "review": self.review,
         "date": self.date,
         "star_rating":self.star_rating,
          "url":self.url
         }

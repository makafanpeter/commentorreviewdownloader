from app import db
from sqlalchemy.orm import relationship
from datetime import datetime


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String())
    url = db.Column(db.String())
    ref_id = db.Column(db.String())
    createdOn = db.Column(db.DateTime, default=datetime.now())

    """docstring for Items"""
    def __init__(self, name, url, ref_id):
        self.name = name
        self.url = url
        self.ref_id = ref_id,


    def __repr__(self):
        return '<id {}>'.format(self.id)




class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String)
    review = db.Column(db.String)
    url = db.Column(db.String)
    item_id =  db.Column(db.Integer,db.ForeignKey('items.id'))
    createdOn = db.Column(db.DateTime, default = datetime.now())
    date = db.Column(db.DateTime, default=datetime.now())
    item = relationship(Item)
    star_rating = db.Column(db.String)


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

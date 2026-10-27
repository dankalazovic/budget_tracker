from app import db


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    color = db.Column(db.String(7), nullable=False)

    __table_args__ = (
        db.Index("uq_category_name_lower", db.func.lower(name), unique=True),
    )

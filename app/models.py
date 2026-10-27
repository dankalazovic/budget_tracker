from app import db


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    color = db.Column(db.String(7), nullable=False)

    transactions = db.relationship(
        "Transaction", back_populates="category", passive_deletes="all"
    )

    __table_args__ = (
        db.Index("uq_category_name_lower", db.func.lower(name), unique=True),
    )


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Numeric(9, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("category.id", name="fk_transaction_category", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    category = db.relationship("Category", back_populates="transactions")

    __table_args__ = (
        db.CheckConstraint("type IN ('income', 'expense')", name="ck_transaction_type"),
        db.CheckConstraint(
            "amount > 0 AND amount <= 1000000", name="ck_transaction_amount"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": format(self.amount, ".2f"),
            "date": self.date.isoformat(),
            "description": self.description,
            "category_id": self.category_id,
        }

from extensions import db


class ClassRecording(db.Model):
    __tablename__ = "class_recordings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(1000), nullable=True)
    video_url = db.Column(db.String(500), nullable=False)
    tute_url = db.Column(db.String(500), nullable=False)
    type = db.Column(
        db.Enum("topik", "spoken", "eps-topik", name="class_recording_type"),
        nullable=False,
    )
    is_expired = db.Column(db.Boolean, default=False, nullable=False)
    date = db.Column(db.Date, nullable=False)

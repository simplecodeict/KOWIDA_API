from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
import logging

from extensions import db
from models.class_recording import ClassRecording
from models.user import User
from schemas import ClassRecordingCreateSchema, ClassRecordingUpdateSchema

logger = logging.getLogger(__name__)

class_recording_bp = Blueprint("class_recording", __name__)


@class_recording_bp.route("/class-recordings", methods=["POST"])
def create_class_recording():
    """
    Create a new class recording
    """
    schema = ClassRecordingCreateSchema()
    try:
        try:
            data = schema.load(request.get_json())
        except ValidationError as e:
            return jsonify(
                {
                    "status": "error",
                    "message": "Validation error",
                    "errors": e.messages,
                    "error_code": "VALIDATION_ERROR",
                }
            ), 400

        class_recording = ClassRecording(
            name=data.get("name"),
            description=data.get("description"),
            video_url=data["video_url"],
            tute_url=data["tute_url"],
            type=data["type"],
            is_expired=data.get("is_expired", False),
            date=data["date"],
        )

        db.session.add(class_recording)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Class recording created successfully",
                "data": {
                    "class_recording": {
                        "id": class_recording.id,
                        "name": class_recording.name,
                        "description": class_recording.description,
                        "video_url": class_recording.video_url,
                        "tute_url": class_recording.tute_url,
                        "type": class_recording.type,
                        "is_expired": class_recording.is_expired,
                        "date": class_recording.date.isoformat() if class_recording.date else None,
                    }
                },
            }
        ), 201
    except Exception as e:
        logger.error(f"Unexpected error during class recording creation: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred during class recording creation",
                "error_code": "CLASS_RECORDING_CREATION_ERROR",
            }
        ), 500


@class_recording_bp.route("/class-recordings", methods=["GET"])
def get_class_recordings():
    """
    Get class recordings based on user access, with filters and pagination.
    Required query param: user_id
    Optional query params: type, date, page
    """
    try:
        user_id = request.args.get("user_id", type=int)
        if not user_id:
            return jsonify(
                {
                    "status": "error",
                    "message": "user_id is required",
                    "error_code": "MISSING_USER_ID",
                }
            ), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify(
                {
                    "status": "error",
                    "message": "Unauthorized: user not found",
                    "error_code": "UNAUTHORIZED",
                }
            ), 401

        if not user.have_recording_access:
            return jsonify(
                {
                    "status": "error",
                    "message": "User does not have recording access",
                    "error_code": "NO_RECORDING_ACCESS",
                }
            ), 403

        allowed_types = []
        if user.is_topik:
            allowed_types.append("topik")
        if user.is_spoken:
            allowed_types.append("spoken")

        if not allowed_types:
            return jsonify(
                {
                    "status": "error",
                    "message": "User does not have any recording type access",
                    "error_code": "NO_RECORDING_TYPE_ACCESS",
                }
            ), 403

        query = ClassRecording.query.filter(ClassRecording.type.in_(allowed_types))

        requested_type = request.args.get("type", type=str)
        if requested_type:
            if requested_type not in ["topik", "spoken", "eps-topik"]:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Invalid type filter. Allowed: topik, spoken, eps-topik",
                        "error_code": "INVALID_TYPE_FILTER",
                    }
                ), 400

            if requested_type not in allowed_types:
                return jsonify(
                    {
                        "status": "error",
                        "message": "User does not have access to requested recording type",
                        "error_code": "TYPE_ACCESS_DENIED",
                    }
                ), 403
            query = query.filter(ClassRecording.type == requested_type)

        requested_date = request.args.get("date", type=str)
        if requested_date:
            try:
                from datetime import datetime

                filter_date = datetime.strptime(requested_date, "%Y-%m-%d").date()
                query = query.filter(ClassRecording.date == filter_date)
            except ValueError:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Invalid date format. Use YYYY-MM-DD",
                        "error_code": "INVALID_DATE_FILTER",
                    }
                ), 400

        page = request.args.get("page", 1, type=int)
        if not page or page < 1:
            page = 1
        per_page = 10

        pagination = query.order_by(ClassRecording.date.asc(), ClassRecording.id.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        recordings = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "video_url": item.video_url,
                "tute_url": item.tute_url,
                "type": item.type,
                "is_expired": item.is_expired,
                "date": item.date.isoformat() if item.date else None,
            }
            for item in pagination.items
        ]

        return jsonify(
            {
                "status": "success",
                "data": {
                    "recordings": recordings,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": pagination.total,
                        "pages": pagination.pages,
                        "has_next": pagination.has_next,
                        "has_prev": pagination.has_prev,
                        "next_page": pagination.next_num if pagination.has_next else None,
                        "prev_page": pagination.prev_num if pagination.has_prev else None,
                    },
                    "filters": {
                        "user_id": user_id,
                        "type": requested_type,
                        "date": requested_date,
                        "allowed_types": allowed_types,
                    },
                },
            }
        ), 200
    except Exception as e:
        logger.error(f"Unexpected error during class recordings fetch: {str(e)}", exc_info=True)
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred during class recordings fetch",
                "error_code": "CLASS_RECORDINGS_FETCH_ERROR",
            }
        ), 500


@class_recording_bp.route("/class-recordings/<int:recording_id>", methods=["PUT"])
def update_class_recording(recording_id):
    """
    Update a class recording
    """
    schema = ClassRecordingUpdateSchema()
    try:
        class_recording = ClassRecording.query.get(recording_id)
        if not class_recording:
            return jsonify(
                {
                    "status": "error",
                    "message": "Class recording not found",
                    "error_code": "CLASS_RECORDING_NOT_FOUND",
                }
            ), 404

        try:
            data = schema.load(request.get_json() or {})
        except ValidationError as e:
            return jsonify(
                {
                    "status": "error",
                    "message": "Validation error",
                    "errors": e.messages,
                    "error_code": "VALIDATION_ERROR",
                }
            ), 400

        if not data:
            return jsonify(
                {
                    "status": "error",
                    "message": "No valid fields provided for update",
                    "error_code": "NO_UPDATE_FIELDS",
                }
            ), 400

        for field, value in data.items():
            setattr(class_recording, field, value)

        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Class recording updated successfully",
                "data": {
                    "class_recording": {
                        "id": class_recording.id,
                        "name": class_recording.name,
                        "description": class_recording.description,
                        "video_url": class_recording.video_url,
                        "tute_url": class_recording.tute_url,
                        "type": class_recording.type,
                        "is_expired": class_recording.is_expired,
                        "date": class_recording.date.isoformat() if class_recording.date else None,
                    }
                },
            }
        ), 200
    except Exception as e:
        logger.error(f"Unexpected error during class recording update: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred during class recording update",
                "error_code": "CLASS_RECORDING_UPDATE_ERROR",
            }
        ), 500


@class_recording_bp.route("/class-recordings/<int:recording_id>", methods=["DELETE"])
def delete_class_recording(recording_id):
    """
    Delete a class recording
    """
    try:
        class_recording = ClassRecording.query.get(recording_id)
        if not class_recording:
            return jsonify(
                {
                    "status": "error",
                    "message": "Class recording not found",
                    "error_code": "CLASS_RECORDING_NOT_FOUND",
                }
            ), 404

        db.session.delete(class_recording)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Class recording deleted successfully",
                "data": {"id": recording_id},
            }
        ), 200
    except Exception as e:
        logger.error(f"Unexpected error during class recording deletion: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred during class recording deletion",
                "error_code": "CLASS_RECORDING_DELETE_ERROR",
            }
        ), 500





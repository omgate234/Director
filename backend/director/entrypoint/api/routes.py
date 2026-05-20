import os

from flask import Blueprint, request, current_app as app
from werkzeug.utils import secure_filename

from director.db import load_db
from director.handler import ChatHandler, SessionHandler, VideoDBHandler, ConfigHandler, LLMHandler


agent_bp = Blueprint("agent", __name__, url_prefix="/agent")
session_bp = Blueprint("session", __name__, url_prefix="/session")
videodb_bp = Blueprint("videodb", __name__, url_prefix="/videodb")
config_bp = Blueprint("config", __name__, url_prefix="/config")
llm_bp = Blueprint("llm", __name__, url_prefix="/llm")


@agent_bp.route("/", methods=["GET"], strict_slashes=False)
def agent():
    """
    Handle the agent request
    """
    chat_handler = ChatHandler(
        db=load_db(os.getenv("SERVER_DB_TYPE", app.config["DB_TYPE"]))
    )
    return chat_handler.agents_list()


@session_bp.route("/", methods=["GET"], strict_slashes=False)
def get_sessions():
    """
    Get all the sessions
    """
    session_handler = SessionHandler(
        db=load_db(os.getenv("SERVER_DB_TYPE", app.config["DB_TYPE"]))
    )
    return session_handler.get_sessions()


@session_bp.route("/<session_id>", methods=["GET", "DELETE"])
def get_session(session_id):
    """
    Get or delete the session details
    """
    if not session_id:
        return {"message": f"Please provide {session_id}."}, 400

    session_handler = SessionHandler(
        db=load_db(os.getenv("SERVER_DB_TYPE", app.config["DB_TYPE"]))
    )
    session = session_handler.get_session(session_id)
    if not session:
        return {"message": "Session not found."}, 404

    if request.method == "GET":
        return session
    elif request.method == "DELETE":
        success, failed_components = session_handler.delete_session(session_id)
        if success:
            return {"message": "Session deleted successfully."}, 200
        else:
            return {
                "message": f"Failed to delete the entry for following components: {', '.join(failed_components)}"
            }, 500


@videodb_bp.route("/collection", defaults={"collection_id": None}, methods=["GET"])
@videodb_bp.route("/collection/<collection_id>", methods=["GET"])
def get_collection_or_all(collection_id):
    """Get a collection by ID or all collections."""
    videodb = VideoDBHandler(collection_id)
    if collection_id:
        return videodb.get_collection()
    else:
        return videodb.get_collections()


@videodb_bp.route("/collection", methods=["POST"])
def create_collection():
    try:
        data = request.get_json()

        if not data or not data.get("name"):
            return {"message": "Collection name is required"}, 400

        if not data.get("description"):
            return {"message": "Collection description is required"}, 400

        collection_name = data["name"]
        description = data["description"]

        videodb = VideoDBHandler()
        result = videodb.create_collection(collection_name, description)

        if result.get("success"):
            return {"message": "Collection created successfully", "data": result}, 201
        else:
            return {
                "message": "Failed to create collection",
                "error": result.get("error"),
            }, 400
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route("/collection/<collection_id>", methods=["DELETE"])
def delete_collection(collection_id):
    try:
        if not collection_id:
            return {"message": "Collection ID is required"}, 400

        videodb = VideoDBHandler(collection_id)
        result = videodb.delete_collection()
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route(
    "/collection/<collection_id>/video", defaults={"video_id": None}, methods=["GET"]
)
@videodb_bp.route("/collection/<collection_id>/video/<video_id>", methods=["GET"])
def get_video_or_all(collection_id, video_id):
    """Get a video by ID or all videos in a collection."""
    videodb = VideoDBHandler(collection_id)
    if video_id:
        return videodb.get_video(video_id)
    else:
        return videodb.get_videos()
    
@videodb_bp.route(
    "/collection/<collection_id>/audio", defaults={"audio_id": None}, methods=["GET"]
)
@videodb_bp.route("/collection/<collection_id>/audio/<audio_id>", methods=["GET"])
def get_audio_or_all(collection_id, audio_id, **kwargs):
    """Get a video by ID or all videos in a collection."""
    videodb = VideoDBHandler(collection_id)
    if audio_id:
        return videodb.get_audio(audio_id)
    else:
        return videodb.get_audios()


@videodb_bp.route(
    "/collection/<collection_id>/image", defaults={"image_id": None}, methods=["GET"]
)
@videodb_bp.route("/collection/<collection_id>/image/<image_id>", methods=["GET"])
def get_image_or_all(collection_id, image_id, **kwargs):
    """Get a video by ID or all videos in a collection."""
    videodb = VideoDBHandler(collection_id)
    if image_id:
        return videodb.get_image(image_id)
    else:
        return videodb.get_images()



@videodb_bp.route("/collection/<collection_id>/video/<video_id>", methods=["DELETE"])
def delete_video(collection_id, video_id):
    """Delete a video by ID from a specific collection."""
    try:
        if not video_id:
            return {"message": "Video ID is required"}, 400
        videodb = VideoDBHandler(collection_id)
        result = videodb.delete_video(video_id)
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route("/collection/<collection_id>/audio/<audio_id>", methods=["DELETE"])
def delete_audio(collection_id, audio_id):
    """Delete a audio by ID from a specific collection."""
    try:
        if not audio_id:
            return {"message": "Video ID is required"}, 400
        videodb = VideoDBHandler(collection_id)
        result = videodb.delete_audio(audio_id)
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route("/collection/<collection_id>/image/<image_id>", methods=["DELETE"])
def delete_image(collection_id, image_id):
    """Delete a image by ID from a specific collection."""
    try:
        if not image_id:
            return {"message": "Video ID is required"}, 400
        videodb = VideoDBHandler(collection_id)
        result = videodb.delete_image(image_id)
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route(
    "/collection/<collection_id>/image/<image_id>/generate_url", methods=["GET"]
)
def generate_image_url(collection_id, image_id):
    try:
        if not collection_id:
            return {"message": "Collection ID is required"}, 400

        if not image_id:
            return {"message": "Image ID is required"}, 400

        videodb = VideoDBHandler(collection_id)
        result = videodb.generate_image_url(image_id)
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500

@videodb_bp.route(
    "/collection/<collection_id>/audio/<audio_id>/generate_url", methods=["GET"]
)
def generate_audio_url(collection_id, audio_id):
    try:
        if not collection_id:
            return {"message": "Collection ID is required"}, 400

        if not audio_id:
            return {"message": "Audio ID is required"}, 400

        videodb = VideoDBHandler(collection_id)
        result = videodb.generate_audio_url(audio_id)
        return result, 200
    except Exception as e:
        return {"message": str(e)}, 500

@videodb_bp.route("/collection/<collection_id>/upload", methods=["POST"])
def upload_video(collection_id):
    """Upload a video to a collection."""
    try:
        videodb = VideoDBHandler(collection_id)

        if "file" in request.files:
            file = request.files["file"]
            file_bytes = file.read()
            safe_filename = secure_filename(file.filename)
            if not safe_filename:
                return {"message": "Invalid filename"}, 400
            file_name = os.path.splitext(safe_filename)[0]
            media_type = file.content_type.split("/")[0]
            return videodb.upload(
                source=file_bytes,
                source_type="file",
                media_type=media_type,
                name=file_name,
            )
        elif "source" in request.json:
            source = request.json["source"]
            source_type = request.json["source_type"]
            return videodb.upload(source=source, source_type=source_type)
        else:
            return {"message": "No valid source provided"}, 400
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route(
    "/collection/<collection_id>/video/<video_id>/transcript", methods=["GET"]
)
def get_video_transcript(collection_id, video_id):
    """Fetch a video's transcript, indexing spoken words first if needed."""
    try:
        videodb = VideoDBHandler(collection_id)
        return videodb.get_transcript(video_id)
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route(
    "/collection/<collection_id>/video/<video_id>/timeline-edit", methods=["POST"]
)
def timeline_edit_video(collection_id, video_id):
    """Generate a stream URL by keeping only the given timeline ranges of a video."""
    try:
        if not collection_id:
            return {"message": "Collection ID is required"}, 400
        if not video_id:
            return {"message": "Video ID is required"}, 400

        body = request.get_json(silent=True) or {}
        timeline = body.get("timeline")

        if not isinstance(timeline, list) or not timeline:
            return {"message": "timeline must be a non-empty list"}, 400
        for pair in timeline:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in pair)
                or pair[0] >= pair[1]
            ):
                return {"message": f"invalid timeline range: {pair}"}, 400

        videodb = VideoDBHandler(collection_id)
        return videodb.generate_video_stream(video_id, timeline), 200
    except Exception as e:
        return {"message": str(e)}, 500


@videodb_bp.route("/collection/<collection_id>/chat_video_upload", methods=["POST"])
def upload_chat_video(collection_id):
    """Upload a stream URL from a chat VideoContent and hydrate the stored output message."""
    try:
        body = request.json or {}
        session_id = body["session_id"]
        msg_id = body["msg_id"]
        content_index = body["content_index"]
        stream_url = body["stream_url"]
        name = body.get("name")

        videodb = VideoDBHandler(collection_id)
        media = videodb.upload(
            source=stream_url, source_type="url", media_type="video", name=name,
        )

        db = load_db(os.getenv("SERVER_DB_TYPE", os.getenv("DB_TYPE", "sqlite")))
        msg = next(
            (m for m in db.get_conversations(session_id) if m["msg_id"] == msg_id),
            None,
        )
        if msg is None:
            return {"message": "message not found"}, 404

        msg["content"][content_index]["video"].update({
            "id": media["id"],
            "collection_id": media["collection_id"],
            "name": media["name"],
            "stream_url": media["stream_url"],
            "player_url": media.get("player_url"),
            "thumbnail_url": media.get("thumbnail_url"),
            "length": media.get("length"),
            "description": media.get("description"),
        })
        db.add_or_update_msg_to_conv(**msg)
        return media
    except KeyError as e:
        return {"message": f"missing field: {e.args[0]}"}, 400
    except Exception as e:
        return {"message": str(e)}, 500


@config_bp.route("/check", methods=["GET"])
def config_check():
    config_handler = ConfigHandler()
    return config_handler.check()


@llm_bp.route("/models", methods=["GET"], strict_slashes=False)
def get_models():
    """Get available LLM models."""
    try:
        llm_handler = LLMHandler()
        return llm_handler.get_models()
    except Exception as e:
        return {"message": str(e)}, 500

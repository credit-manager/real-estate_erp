"""Advanced DMS — OCR + Full-text search + Versioning."""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import os
import hashlib

from database import db
from models import DocumentFolder, Document, DocumentAnnotation, DocumentShare
from permissions import require_api
from auditlog import log_action

dms_bp = Blueprint("dms", __name__, url_prefix="/api/dms")

# إعدادات الرفع
ALLOWED_MIME = {
    'application/pdf',
    'image/jpeg', 'image/png', 'image/webp', 'image/tiff',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'dms')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==================== Folders ====================

@dms_bp.route("/folders", methods=["GET"])
@require_api("realestate", "view")
def list_folders():
    q = DocumentFolder.query.filter(DocumentFolder.deleted_at.is_(None))
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    if entity_id:
        q = q.filter_by(entity_id=entity_id)
    parent_id = request.args.get("parent_id", type=int)
    if parent_id:
        q = q.filter_by(parent_id=parent_id)
    else:
        q = q.filter(DocumentFolder.parent_id.is_(None))
    return jsonify([f.to_dict() for f in q.order_by(DocumentFolder.name).all()])


@dms_bp.route("/folders/tree", methods=["GET"])
@require_api("realestate", "view")
def folder_tree():
    """شجرة المجلدات الكاملة."""
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    q = DocumentFolder.query.filter(DocumentFolder.deleted_at.is_(None))
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    if entity_id:
        q = q.filter_by(entity_id=entity_id)
    folders = q.all()
    # بناء الشجرة
    folder_map = {f.id: {**f.to_dict(), "children": []} for f in folders}
    roots = []
    for f in folders:
        if f.parent_id and f.parent_id in folder_map:
            folder_map[f.parent_id]["children"].append(folder_map[f.id])
        else:
            roots.append(folder_map[f.id])
    return jsonify(roots)


@dms_bp.route("/folders", methods=["POST"])
@require_api("realestate", "create")
def create_folder():
    data = request.get_json() or {}
    if not data.get("name"):
        return jsonify({"message": "اسم المجلد مطلوب"}), 400
    folder = DocumentFolder(
        parent_id=data.get("parent_id"),
        name=data["name"],
        description=data.get("description"),
        entity_type=data.get("entity_type"),
        entity_id=data.get("entity_id"),
        created_by=request.environ.get("user_id"),
    )
    db.session.add(folder)
    db.session.commit()
    log_action("create", "document_folder", folder.id, folder.name)
    return jsonify(folder.to_dict()), 201


@dms_bp.route("/folders/<int:fid>", methods=["PUT"])
@require_api("realestate", "edit")
def update_folder(fid):
    folder = db.session.get(DocumentFolder, fid)
    if not folder or folder.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("name", "description"):
        if field in data:
            setattr(folder, field, data[field])
    db.session.commit()
    log_action("update", "document_folder", folder.id, folder.name)
    return jsonify(folder.to_dict())


@dms_bp.route("/folders/<int:fid>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_folder(fid):
    folder = db.session.get(DocumentFolder, fid)
    if not folder or folder.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    if folder.children:
        return jsonify({"message": "لا يمكن حذف مجلد به مجلدات فرعية"}), 400
    if folder.documents:
        return jsonify({"message": "لا يمكن حذف مجلد به مستندات"}), 400
    folder.deleted_at = datetime.now()
    db.session.commit()
    log_action("delete", "document_folder", fid, folder.name)
    return jsonify({"success": True})


# ==================== Documents ====================

@dms_bp.route("/documents", methods=["GET"])
@require_api("realestate", "view")
def list_documents():
    q = Document.query.filter(Document.deleted_at.is_(None), Document.is_latest == True)
    folder_id = request.args.get("folder_id", type=int)
    if folder_id:
        q = q.filter_by(folder_id=folder_id)
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    if entity_id:
        q = q.filter_by(entity_id=entity_id)
    q_param = request.args.get("q")
    if q_param:
        # بحث نصي بسيط (يمكن تحسينه بـ PostgreSQL tsvector)
        like = f"%{q_param}%"
        q = q.filter(db.or_(
            Document.title.ilike(like),
            Document.description.ilike(like),
            Document.ocr_text.ilike(like)
        ))
    ocr_status = request.args.get("ocr_status")
    if ocr_status:
        q = q.filter_by(ocr_status=ocr_status)
    return jsonify([d.to_dict() for d in q.order_by(Document.id.desc()).all()])


@dms_bp.route("/documents", methods=["POST"])
@require_api("realestate", "create")
def create_document():
    """رفع مستند جديد (مع ملف)."""
    # التعامل مع multipart/form-data
    if 'file' not in request.files:
        return jsonify({"message": "ملف مطلوب"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "ملف مطلوب"}), 400

    # تحقق من الحجم
    file.seek(0, 2)
    fsize = file.tell()
    file.seek(0)
    if fsize > MAX_FILE_SIZE:
        return jsonify({"message": "حجم الملف كبير جداً (الحد 50MB)"}), 413

    # تحقق من النوع
    if file.mimetype not in ALLOWED_MIME:
        return jsonify({"message": "نوع الملف غير مدعوم"}), 400

    # بيانات النموذج
    title = request.form.get("title") or file.filename
    description = request.form.get("description")
    folder_id = request.form.get("folder_id", type=int)
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id", type=int)
    tags = request.form.get("tags")
    ocr_language = request.form.get("ocr_language", "ara")

    # حفظ الملف
    filename = secure_filename(file.filename)
    file_hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)

    # تحقق من التكرار
    existing = Document.query.filter_by(file_hash=file_hash, deleted_at=None).first()
    if existing:
        return jsonify({"message": "ملف مكرر (نفس المحتوى)", "existing_id": existing.id}), 409

    # حفظ على القرص
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{hashlib.md5(f'{datetime.now().isoformat()}{file.filename}'.encode()).hexdigest()}{ext}"
    stored_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(stored_path)
    fsize = os.path.getsize(stored_path)

    # تحديد نوع MIME
    mime_type = file.mimetype

    # إنشاء السجل
    doc = Document(
        folder_id=folder_id,
        title=title,
        description=description,
        file_path=stored_path,
        file_name=file.filename,
        file_size=fsize,
        mime_type=mime_type,
        file_hash=file_hash,
        version=1,
        is_latest=True,
        entity_type=entity_type,
        entity_id=entity_id,
        tags=tags,
        ocr_language=ocr_language,
        ocr_status='pending',
        uploaded_by=request.environ.get("user_id"),
    )
    db.session.add(doc)
    db.session.commit()

    # جدولة OCR (في الإنتاج: مهمة خلفية)
    # TODO: استخدام Celery/RQ لمعالجة OCR في الخلفية
    _schedule_ocr(doc.id)

    log_action("create", "document", doc.id, doc.title)
    return jsonify(doc.to_dict()), 201


def _schedule_ocr(doc_id):
    """جدولة معالجة OCR (مبسط — في الإنتاج استخدم طابور مهام)."""
    # هنا نضع علامة المعالجة، والمعالجة الفعلية تتم في مهمة خلفية
    doc = db.session.get(Document, doc_id)
    if doc:
        doc.ocr_status = 'processing'
        db.session.commit()


@dms_bp.route("/documents/<int:doc_id>/ocr", methods=["POST"])
@require_api("realestate", "edit")
def trigger_ocr(doc_id):
    """تشغيل OCR يدوياً."""
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    doc.ocr_status = 'pending'
    _schedule_ocr(doc_id)
    db.session.commit()
    return jsonify({"message": "تمت جدولة OCR", "status": "pending"})


@dms_bp.route("/documents/<int:doc_id>/ocr-result", methods=["POST"])
def ocr_callback(doc_id):
    """callback من خدمة OCR (مثل Tesseract أو Azure Form Recognizer)."""
    data = request.get_json() or {}
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"message": "غير موجود"}), 404
    success = data.get("success", False)
    if success:
        doc.ocr_text = data.get("text", "")
        doc.ocr_confidence = data.get("confidence", 0)
        doc.ocr_status = 'completed'
        doc.ocr_processed_at = datetime.now()
    else:
        doc.ocr_status = 'failed'
    db.session.commit()
    return jsonify({"success": True})


@dms_bp.route("/documents/search", methods=["GET"])
@require_api("realestate", "view")
def search_documents():
    """بحث نصي كامل في المستندات."""
    q_param = request.args.get("q", "").strip()
    if not q_param:
        return jsonify([])

    # بحث بسيط — في الإنتاج استخدم PostgreSQL tsvector
    like = f"%{q_param}%"
    docs = Document.query.filter(
        Document.deleted_at.is_(None),
        Document.is_latest == True,
        db.or_(
            Document.title.ilike(f"%{q_param}%"),
            Document.description.ilike(f"%{q_param}%"),
            Document.ocr_text.ilike(f"%{q_param}%")
        )
    ).limit(50).all()
    return jsonify([d.to_dict() for d in docs])


@dms_bp.route("/documents/<int:doc_id>", methods=["GET"])
@require_api("realestate", "view")
def get_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    return jsonify(doc.to_dict())


@dms_bp.route("/documents/<int:doc_id>/download", methods=["GET"])
@require_api("realestate", "view")
def download_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    if not os.path.exists(doc.file_path):
        return jsonify({"message": "الملف غير موجود على القرص"}), 404
    return send_file(doc.file_path, as_attachment=True, download_name=doc.file_name)


@dms_bp.route("/documents/<int:doc_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("title", "description", "tags", "entity_type", "entity_id"):
        if field in data:
            setattr(doc, field, data[field])
    if "folder_id" in data:
        doc.folder_id = data["folder_id"]
    doc.updated_at = datetime.now()
    db.session.commit()
    log_action("update", "document", doc.id, doc.title)
    return jsonify(doc.to_dict())


@dms_bp.route("/documents/<int:doc_id>/new-version", methods=["POST"])
@require_api("realestate", "create")
def new_version(doc_id):
    """إنشاء إصدار جديد من المستند."""
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    if not doc.is_latest:
        return jsonify({"message": "يمكن إنشاء إصدار جديد فقط لأحدث إصدار"}), 400

    if 'file' not in request.files:
        return jsonify({"message": "ملف مطلوب"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "ملف مطلوب"}), 400

    file.seek(0, 2)
    fsize = file.tell()
    file.seek(0)
    if fsize > MAX_FILE_SIZE:
        return jsonify({"message": "حجم الملف كبير جداً"}), 413
    if file.mimetype not in ALLOWED_MIME:
        return jsonify({"message": "نوع الملف غير مدعوم"}), 400

    filename = secure_filename(file.filename)
    file_hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)

    existing = Document.query.filter_by(file_hash=file_hash, deleted_at=None).first()
    if existing:
        return jsonify({"message": "ملف مكرر", "existing_id": existing.id}), 409

    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{hashlib.md5(f'{datetime.now().isoformat()}{file.filename}'.encode()).hexdigest()}{os.path.splitext(file.filename)[1]}"
    stored_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(stored_path)
    fsize = os.path.getsize(stored_path)
    mime_type = file.mimetype

    # إنشاء الإصدار الجديد
    new_doc = doc.create_new_version(stored_path, file.filename, fsize, mime_type, request.environ.get("user_id"))
    new_doc.file_hash = file_hash
    new_doc.mime_type = mime_type
    new_doc.ocr_language = doc.ocr_language
    db.session.add(new_doc)
    db.session.commit()

    _schedule_ocr(new_doc.id)
    log_action("create", "document_version", new_doc.id, f"Version {new_doc.version} of {doc.title}")
    return jsonify(new_doc.to_dict()), 201


@dms_bp.route("/documents/<int:doc_id>/versions", methods=["GET"])
@require_api("realestate", "view")
def document_versions(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    # جلب كل الإصدارات
    versions = Document.query.filter(
        db.or_(Document.id == doc_id, Document.previous_version_id == doc_id)
    ).order_by(Document.version).all()
    return jsonify([v.to_dict() for v in versions])


@dms_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "غير موجود"}), 404
    doc.deleted_at = datetime.now()
    db.session.commit()
    log_action("delete", "document", doc_id, doc.title)
    return jsonify({"success": True})


@dms_bp.route("/documents/<int:doc_id>/download-version/<int:version>", methods=["GET"])
@require_api("realestate", "view")
def download_version(doc_id, version):
    doc = Document.query.filter_by(previous_version_id=doc_id, version=version).first()
    if not doc:
        doc = db.session.get(Document, doc_id)
        if not doc or doc.version != version:
            return jsonify({"message": "إصدار غير موجود"}), 404
    if not os.path.exists(doc.file_path):
        return jsonify({"message": "الملف غير موجود"}), 404
    return send_file(doc.file_path, as_attachment=True, download_name=f"v{version}_{doc.file_name}")


# ==================== Annotations ====================

@dms_bp.route("/documents/<int:doc_id>/annotations", methods=["GET"])
@require_api("realestate", "view")
def list_annotations(doc_id):
    anns = DocumentAnnotation.query.filter_by(document_id=doc_id).order_by(DocumentAnnotation.page_number, DocumentAnnotation.id).all()
    return jsonify([a.to_dict() for a in anns])


@dms_bp.route("/documents/<int:doc_id>/annotations", methods=["POST"])
@require_api("realestate", "create")
def create_annotation(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "المستند غير موجود"}), 404
    data = request.get_json() or {}
    required = ("annotation_type", "content")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    ann = DocumentAnnotation(
        document_id=doc_id,
        page_number=data.get("page_number"),
        x=data.get("x"), y=data.get("y"),
        width=data.get("width"), height=data.get("height"),
        annotation_type=data["annotation_type"],
        content=data["content"],
        color=data.get("color", "#fef08a"),
        created_by=request.environ.get("user_id"),
    )
    db.session.add(ann)
    db.session.commit()
    return jsonify(ann.to_dict()), 201


@dms_bp.route("/annotations/<int:aid>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_annotation(aid):
    ann = db.session.get(DocumentAnnotation, aid)
    if not ann:
        return jsonify({"message": "غير موجود"}), 404
    db.session.delete(ann)
    db.session.commit()
    return jsonify({"success": True})


# ==================== Shares ====================

@dms_bp.route("/documents/<int:doc_id>/shares", methods=["GET"])
@require_api("realestate", "view")
def list_shares(doc_id):
    shares = DocumentShare.query.filter_by(document_id=doc_id).all()
    return jsonify([s.to_dict() for s in shares])


@dms_bp.route("/documents/<int:doc_id>/shares", methods=["POST"])
@require_api("realestate", "create")
def create_share(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc or doc.deleted_at:
        return jsonify({"message": "المستند غير موجود"}), 404
    data = request.get_json() or {}
    if not data.get("shared_with_user") and not data.get("shared_with_role"):
        return jsonify({"message": "مستخدم أو دور مطلوب"}), 400
    share = DocumentShare(
        document_id=doc_id,
        shared_with_user=data.get("shared_with_user"),
        shared_with_role=data.get("shared_with_role"),
        permission=data.get("permission", "view"),
        shared_by=request.environ.get("user_id"),
        expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
    )
    db.session.add(share)
    db.session.commit()
    return jsonify(share.to_dict()), 201


@dms_bp.route("/shares/<int:sid>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_share(sid):
    share = db.session.get(DocumentShare, sid)
    if not share:
        return jsonify({"message": "غير موجود"}), 404
    db.session.delete(share)
    db.session.commit()
    return jsonify({"success": True})


# ==================== OCR Processing Helper ====================

def process_ocr_background(doc_id):
    """معالجة OCR في الخلفية (لتشغيلها كـ background job)."""
    # هذا الدالة تُستدعى من نظام طابور المهام (Celery/RQ)
    # هنا مجرد هيكل — التنفيذ الفعلي يعتمد على خدمة OCR المستخدمة
    pass
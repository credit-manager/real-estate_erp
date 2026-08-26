"""Advanced DMS — OCR + Full-text search + Document versioning."""
from database import db
from sqlalchemy import event


class DocumentFolder(db.Model):
    """مجلدات المستندات — هيكل هرمي."""
    __tablename__ = "document_folders"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("document_folders.id"), index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    entity_type = db.Column(db.String(30), index=True)  # project, unit, customer, contract, etc.
    entity_id = db.Column(db.Integer, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    parent = db.relationship("DocumentFolder", remote_side=[id], backref="children")
    documents = db.relationship("Document", backref="dms_folder", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Document(db.Model):
    """مستند — مع دعم OCR والبحث الكامل والإصدارات."""
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("document_folders.id"), index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(300))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    file_hash = db.Column(db.String(64), index=True)  # SHA256 للكشف عن التكرار
    version = db.Column(db.Integer, default=1, nullable=False)
    is_latest = db.Column(db.Boolean, default=True, index=True)
    previous_version_id = db.Column(db.Integer, db.ForeignKey("documents.id"), index=True)

    # OCR & Search
    ocr_text = db.Column(db.Text)  # النص المستخرج بـ OCR
    ocr_language = db.Column(db.String(10), default='ara')  # ara, eng, ara+eng
    ocr_status = db.Column(db.String(20), default='pending', index=True)  # pending, processing, completed, failed
    ocr_confidence = db.Column(db.Float)  # متوسط ثقة OCR
    ocr_processed_at = db.Column(db.DateTime)
    search_vector = db.Column(db.Text)  # للنص الكامل (PostgreSQL tsvector)

    # Metadata
    entity_type = db.Column(db.String(30), index=True)  # project, unit, customer, contract, etc.
    entity_id = db.Column(db.Integer, index=True)
    tags = db.Column(db.Text)  # JSON array of tags
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationships
    versions = db.relationship("Document", backref=db.backref("previous_version", remote_side=[id]))
    annotations = db.relationship("DocumentAnnotation", backref="document", cascade="all, delete-orphan")
    shares = db.relationship("DocumentShare", backref="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "folder_id": self.folder_id,
            "folder_name": self.folder.name if self.folder else None,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "file_hash": self.file_hash,
            "version": self.version,
            "is_latest": self.is_latest,
            "ocr_status": self.ocr_status,
            "ocr_language": self.ocr_language,
            "ocr_confidence": self.ocr_confidence,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_latest_version(self):
        """الحصول على أحدث إصدار."""
        if self.is_latest:
            return self
        return Document.query.filter_by(previous_version_id=self.id, is_latest=True).first()

    def create_new_version(self, file_path, file_name, file_size, mime_type, uploaded_by):
        """إنشاء إصدار جديد من المستند."""
        # وضع الإصدار الحالي كقديم
        self.is_latest = False

        # إنشاء الإصدار الجديد
        new_version = Document(
            folder_id=self.folder_id,
            title=self.title,
            description=self.description,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash="",  # سيتم حسابه لاحقاً
            version=self.version + 1,
            is_latest=True,
            previous_version_id=self.id,
            ocr_language=self.ocr_language,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            tags=self.tags,
            uploaded_by=uploaded_by,
        )
        db.session.add(new_version)
        db.session.flush()
        return new_version


class DocumentAnnotation(db.Model):
    """تعليقات/تمييزات على المستند."""
    __tablename__ = "document_annotations"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    page_number = db.Column(db.Integer)
    x = db.Column(db.Float)  # نسبة من عرض الصفحة
    y = db.Column(db.Float)  # نسبة من ارتفاع الصفحة
    width = db.Column(db.Float)
    height = db.Column(db.Float)
    annotation_type = db.Column(db.String(20), default='highlight')  # highlight, note, rectangle, text
    content = db.Column(db.Text)  # نص التعليق
    color = db.Column(db.String(20), default='#fef08a')  # لون التمييز
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "x": self.x, "y": self.y, "width": self.width, "height": self.height,
            "annotation_type": self.annotation_type,
            "content": self.content,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentShare(db.Model):
    """مشاركة المستند مع مستخدمين/فرق."""
    __tablename__ = "document_shares"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    shared_with_user = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    shared_with_role = db.Column(db.String(50), index=True)  # للفرق/الأدوار
    permission = db.Column(db.String(20), default='view')  # view, comment, edit, admin
    shared_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "shared_with_user": self.shared_with_user,
            "shared_with_role": self.shared_with_role,
            "permission": self.permission,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Event listener لحساب hash الملف تلقائياً
@event.listens_for(Document, 'before_insert')
@event.listens_for(Document, 'before_update')
def compute_file_hash(mapper, connection, target):
    if target.file_path and not target.file_hash:
        import hashlib, os
        try:
            if os.path.exists(target.file_path):
                with open(target.file_path, 'rb') as f:
                    target.file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass
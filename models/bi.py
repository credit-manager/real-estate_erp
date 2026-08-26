"""BI Embedded — Superset/Metabase integration for embedded dashboards."""
from database import db


class BIProvider(db.Model):
    """مزود BI — Superset أو Metabase."""
    __tablename__ = "bi_providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)  # superset, metabase
    display_name = db.Column(db.String(100), nullable=False)
    base_url = db.Column(db.String(255), nullable=False)  # http://superset:8088 أو http://metabase:3000
    api_key = db.Column(db.Text)  # مشفر
    secret_key = db.Column(db.Text)  # مشفر
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    config_json = db.Column(db.Text)  # إعدادات إضافية (مثل database_id للـ Metabase)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    dashboards = db.relationship("BIDashboard", backref="provider", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "base_url": self.base_url,
            "is_active": self.is_active,
            "is_default": self.is_default,
        }


class BIDashboard(db.Model):
    """لوحة معلومات BI."""
    __tablename__ = "bi_dashboards"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("bi_providers.id"), nullable=False, index=True)
    external_id = db.Column(db.String(100), nullable=False)  # dashboard_id في Superset/Metabase
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)  # sales, finance, realestate, hr, projects
    is_public = db.Column(db.Boolean, default=False)  # قابلة للعرض دون تسجيل دخول
    allowed_roles = db.Column(db.Text)  # JSON array of role names
    iframe_width = db.Column(db.String(20), default="100%")
    iframe_height = db.Column(db.String(20), default="600px")
    filter_params = db.Column(db.Text)  # JSON للفلاتر الافتراضية
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "provider_name": self.provider.display_name if self.provider else None,
            "external_id": self.external_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "is_public": self.is_public,
            "allowed_roles": self.allowed_roles,
            "iframe_width": self.iframe_width,
            "iframe_height": self.iframe_height,
            "filter_params": self.filter_params,
            "is_active": self.is_active,
            "embed_url": self.get_embed_url(),
        }

    def get_embed_url(self):
        """توليد رابط التضمين (iframe) للوحة."""
        if not self.provider:
            return None
        base = self.provider.base_url.rstrip('/')
        if self.provider.name == 'superset':
            return f"{base}/superset/dashboard/{self.external_id}/?standalone=true"
        elif self.provider.name == 'metabase':
            return f"{base}/embed/dashboard/{self.external_id}#bordered=true&titled=true"
        return f"{base}/embed/{self.external_id}"


class BIFilterTemplate(db.Model):
    """قالب فلتر BI — فلاتر قابلة لإعادة الاستخدام."""
    __tablename__ = "bi_filter_templates"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("bi_providers.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    filter_key = db.Column(db.String(50), nullable=False)  # مفتاح الفلتر في BI (مثل project_id, date_range)
    filter_type = db.Column(db.String(20), default="select")  # select, date_range, multi_select, number
    label = db.Column(db.String(100))
    default_value = db.Column(db.Text)
    options_json = db.Column(db.Text)  # للخيارات: [{"value": 1, "label": "مشروع أ"}]
    is_required = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "filter_key": self.filter_key,
            "filter_type": self.filter_type,
            "label": self.label,
            "default_value": self.default_value,
            "options": self.options_json,
            "is_required": self.is_required,
        }
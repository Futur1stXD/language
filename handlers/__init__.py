from .common import router as common_router
from .survey import router as survey_router
from .admin import router as admin_router

__all__ = ["common_router", "survey_router", "admin_router"]

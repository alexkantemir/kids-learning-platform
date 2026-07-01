from fastapi import APIRouter

from app.api.endpoints import auth, children, subjects, lessons, quizzes, progress, parent, achievements, plans

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(children.router, prefix="/children", tags=["children"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(parent.router, prefix="/parent", tags=["parent"])
api_router.include_router(achievements.router, prefix="/achievements", tags=["achievements"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])

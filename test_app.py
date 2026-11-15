"""Mini serveur pour tester la route avec l'interface Swagger, sans le reste du backend :
    uvicorn test_app:app --reload
puis ouvrir http://localhost:8000/docs"""
from fastapi import FastAPI

from controllers.extraction_controller import router

app = FastAPI(title="Test extracteur")
app.include_router(router, prefix="/api")

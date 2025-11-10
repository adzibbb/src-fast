from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import user as user_crud
from app.schemas.user import UserLeaderboard


router = APIRouter()


@router.get("/", response_model=list[UserLeaderboard])
def get_leaderboard(db: Session = Depends(get_db)):
    return user_crud.get_leaderboard(db)

